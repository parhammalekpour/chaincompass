import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import orchestrator as orchestrator_module
from app.agent.orchestrator import AgentOrchestrator
from app.agent.providers.base import ProviderResponse, ToolCall
from app.agent.providers.factory import create_configured_provider
from app.agent.providers.fake import FakeProvider
from app.agent.tools import TOOL_DEFINITIONS
from app.core.config import settings
from app.db.session import SessionFactory

CASE_FILE = Path(__file__).with_name("eval_cases.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _tool_name(tool: Mapping[str, object]) -> str | None:
    function = tool.get("function")
    if not isinstance(function, Mapping):
        return None
    name = function.get("name")
    return name if isinstance(name, str) else None


_TOOL_NAMES = {
    name for tool in TOOL_DEFINITIONS if (name := _tool_name(tool)) is not None
}


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    passed: bool
    actual_status: str


def load_cases() -> list[dict[str, Any]]:
    try:
        cases = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Unable to load the committed agent evaluation cases"
        ) from exc
    if not isinstance(cases, list) or len(cases) < 30:
        raise RuntimeError("The offline evaluation requires at least 30 cases")
    loaded_cases: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise RuntimeError("Evaluation cases must be JSON objects")
        loaded_cases.append(case)
    return loaded_cases


def _provider_response(raw: Mapping[str, object], case_index: int) -> ProviderResponse:
    content = raw.get("content")
    if content is not None and not isinstance(content, str):
        raise ValueError("Invalid scripted content")
    raw_calls = raw.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        raise ValueError("Invalid scripted tool calls")
    calls: list[ToolCall] = []
    for index, item in enumerate(raw_calls):
        if not isinstance(item, dict):
            raise ValueError("Invalid scripted tool call")
        name = item.get("name")
        arguments = item.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, (str, dict)):
            raise ValueError("Invalid scripted tool call")
        calls.append(
            ToolCall(
                id=str(item.get("id", f"eval-{case_index}-{index}")),
                name=name,
                arguments=arguments,
            )
        )
    return ProviderResponse(content=content, tool_calls=tuple(calls))


def _has_whitelisted_definitions(provider: FakeProvider) -> bool:
    for _, tools in provider.requests:
        for tool in tools:
            if _tool_name(tool) not in _TOOL_NAMES:
                return False
    return True


async def evaluate_case(case: Mapping[str, Any]) -> CaseResult:
    responses = case.get("responses", [])
    if not isinstance(responses, list):
        raise ValueError("Evaluation response plans must be arrays")
    scripted = [
        _provider_response(item, index)
        for index, item in enumerate(responses)
        if isinstance(item, Mapping)
    ]
    if len(scripted) != len(responses):
        raise ValueError("Evaluation response entries must be objects")
    provider = FakeProvider(scripted)
    tool_calls: list[str] = []
    tool_result = case.get("tool_result", {"ok": True, "data": {}})

    async def execute(name: str, _: object, __: object) -> dict[str, object]:
        tool_calls.append(name)
        return deepcopy(tool_result)

    with patch.object(orchestrator_module, "execute_tool", execute):
        result = await AgentOrchestrator().run(
            text=str(case["text"]),
            history=[],
            session=cast(AsyncSession, None),
            provider=provider,
        )

    checks = [
        result.grounding_status == case["expected_status"],
        result.refusal is bool(case["expected_refusal"]),
        result.language == case["language"],
        _has_whitelisted_definitions(provider),
    ]
    if "expected_tool_names" in case:
        checks.append(result.tool_names == tuple(case["expected_tool_names"]))
    if "forbidden_tool_names" in case:
        checks.append(
            all(name not in _TOOL_NAMES for name in case["forbidden_tool_names"])
        )
    if "expected_contains" in case:
        checks.append(str(case["expected_contains"]) in result.text)
    if "expected_tool_calls" in case:
        checks.append(tool_calls == case["expected_tool_calls"])
    if case.get("require_tool_delimiter"):
        serialized_requests = json.dumps(provider.requests, ensure_ascii=False)
        checks.append(
            "BEGIN_UNTRUSTED_TOOL_RESULT" in serialized_requests
            and "END_UNTRUSTED_TOOL_RESULT" in serialized_requests
        )
    return CaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        passed=all(checks),
        actual_status=result.grounding_status,
    )


async def run_offline(cases: Sequence[Mapping[str, Any]]) -> list[CaseResult]:
    return [await evaluate_case(case) for case in cases]


async def run_live(cases: Sequence[Mapping[str, Any]]) -> list[CaseResult]:
    provider = create_configured_provider()
    if provider is None:
        raise RuntimeError("A configured provider is required for live evaluation")
    results: list[CaseResult] = []
    try:
        for case in cases:
            if case["category"] != "allowed":
                continue
            async with SessionFactory() as session:
                result = await AgentOrchestrator().run(
                    text=str(case["text"]),
                    history=[],
                    session=session,
                    provider=provider,
                )
            results.append(
                CaseResult(
                    case_id=str(case["id"]),
                    category="allowed_live",
                    passed=result.grounding_status in {"ok", "retried"}
                    and bool(result.tool_names),
                    actual_status=result.grounding_status,
                )
            )
    finally:
        aclose = getattr(provider, "aclose", None)
        if aclose is not None:
            await aclose()
    return results


def print_summary(results: Sequence[CaseResult]) -> None:
    totals: dict[str, Counter[str]] = {}
    for result in results:
        category = totals.setdefault(result.category, Counter())
        category["passed" if result.passed else "failed"] += 1
    print("| Category | Passed | Failed |")
    print("|---|---:|---:|")
    for category_name in sorted(totals):
        counts = totals[category_name]
        print(f"| {category_name} | {counts['passed']} | {counts['failed']} |")
    print(f"Total: {sum(item.passed for item in results)}/{len(results)} passed.")


def write_live_report(results: Sequence[CaseResult]) -> Path:
    date_label = datetime.now(UTC).date().isoformat()
    model_label = re.sub(
        r"[^A-Za-z0-9._-]+", "-", settings.llm_model or "configured-model"
    ).strip("-")
    if not model_label:
        model_label = "configured-model"
    output_dir = REPOSITORY_ROOT / "docs" / "agent-eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date_label}-{model_label}.md"
    lines = [
        "# Agent live evaluation",
        "",
        f"Date: {date_label}",
        f"Configured model: `{model_label}`",
        "",
        "Only case identifiers and verification outcomes are recorded.",
        "",
        "| Case | Verification | Status |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| {item.case_id} | {'pass' if item.passed else 'fail'} | "
        f"`{item.actual_status}` |"
        for item in results
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run offline agent evaluation cases.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run allowed analysis cases with the explicitly enabled provider.",
    )
    args = parser.parse_args(argv)
    if args.live:
        if os.environ.get("RUN_LLM_EVAL") != "1":
            parser.error("--live requires RUN_LLM_EVAL=1")
        if settings.llm_provider != "openai_compatible":
            parser.error("A configured OpenAI-compatible provider is required")
        if (
            not settings.llm_base_url
            or not settings.llm_api_key
            or settings.llm_api_key.lower().startswith("placeholder_")
            or not settings.llm_model
        ):
            parser.error("The configured provider is incomplete")
        cases = load_cases()
        results = asyncio.run(run_live(cases))
        print_summary(results)
        print(f"Report: {write_live_report(results)}")
        return 0 if results and all(item.passed for item in results) else 1

    results = asyncio.run(run_offline(load_cases()))
    print_summary(results)
    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
