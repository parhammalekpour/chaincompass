import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.guardrails import (
    OutputCheck,
    check_output,
    classify_input,
    detect_language,
    refusal_text,
    system_prompt,
    validate_message_length,
)
from app.agent.providers.base import LLMProvider, ProviderError, ProviderResponse
from app.agent.tools import TOOL_DEFINITIONS, execute_tool

MAX_TOOL_ITERATIONS = 4
MAX_TOOL_CALLS_PER_TURN = 4
MAX_TOOL_ARGUMENT_LENGTH = 5000
TOTAL_BUDGET_SECONDS = 60.0
_SAFE_TOOL_NAMES = {
    "list_chains",
    "get_chain_snapshot",
    "get_score_history_summary",
    "get_regime_history",
    "get_scenarios",
    "get_methodology_summary",
}
_SAFE_FIELDS = frozenset(
    {
        "slug",
        "chain",
        "as_of",
        "as_of_date",
        "score",
        "coverage",
        "coverage_max",
        "confidence_label",
        "version",
        "is_partial",
        "label",
        "days_in_regime",
        "vol_state",
        "flag",
        "severity",
        "value",
        "threshold",
        "count",
        "minimum",
        "maximum",
        "latest",
        "changes",
        "gap_days",
        "items",
        "segments",
        "regime",
        "days",
        "available",
        "low_sample",
        "n_windows",
        "n_independent",
        "quantile",
        "return",
        "return_value",
        "illustrative_price_usd",
        "close_usd",
        "price",
        "horizons",
        "scenarios",
        "name",
        "data",
        "chains",
        "symbol",
        "pillars",
        "weight",
        "components",
        "percentile_window_days",
        "minimum_score_coverage",
        "confidence_thresholds",
        "regime_rules",
        "hysteresis_days",
        "horizons_days",
        "minimum_independent_windows",
        "low_sample_below_independent_windows",
        "risk_flags",
    }
)
_SAFE_ENUM_VALUES = frozenset(
    {
        "btc",
        "eth",
        "sol",
        "bnb",
        "High",
        "Medium",
        "Low",
        "high",
        "medium",
        "low",
        "stress",
        "uptrend",
        "downtrend",
        "range",
        "normal",
        "pessimistic",
        "base",
        "optimistic",
        "p10",
        "p50",
        "p90",
        "deep_drawdown",
        "high_volatility",
        "liquidity_drying",
        "usage_decline",
        "tvl_outflow",
        "stablecoin_contraction",
        "hashrate_decline",
        "low_confidence",
    }
)
_NUMBER_OR_DATE = re.compile(r"(?:\d{4}-\d{2}-\d{2}|v\d+|[-+]?(?:\d+(?:\.\d*)?|\.\d+))")


@dataclass(frozen=True)
class ToolInvocation:
    name: str
    arguments: dict[str, object]
    result: dict[str, object]


@dataclass(frozen=True)
class AgentRun:
    text: str
    grounding_status: str
    refusal: bool
    language: str
    tool_names: tuple[str, ...]
    tool_invocations: tuple[ToolInvocation, ...]
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


@dataclass(frozen=True)
class ToolCallStarted:
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ToolResultReady:
    name: str
    ok: bool


@dataclass(frozen=True)
class AgentCompleted:
    result: AgentRun


AgentEvent = ToolCallStarted | ToolResultReady | AgentCompleted


class AgentNotConfiguredError(Exception):
    pass


class AgentOrchestrator:
    async def run(
        self,
        *,
        text: str,
        history: Sequence[Mapping[str, object]],
        session: AsyncSession,
        provider: LLMProvider | None,
    ) -> AgentRun:
        async for event in self.run_events(
            text=text,
            history=history,
            session=session,
            provider=provider,
        ):
            if isinstance(event, AgentCompleted):
                return event.result
        raise RuntimeError("The agent orchestration ended without a result")

    async def run_events(
        self,
        *,
        text: str,
        history: Sequence[Mapping[str, object]],
        session: AsyncSession,
        provider: LLMProvider | None,
    ) -> AsyncIterator[AgentEvent]:
        validate_message_length(text)
        language = detect_language(text)
        started = time.perf_counter()
        intent = classify_input(text)
        if intent is not None:
            answer = refusal_text(language)
            check = check_output(answer, [])
            if not check.passed:
                raise RuntimeError("The deterministic refusal failed output checks")
            yield AgentCompleted(
                AgentRun(
                    text=answer,
                    grounding_status="refused",
                    refusal=True,
                    language=language,
                    tool_names=(),
                    tool_invocations=(),
                    prompt_tokens=None,
                    completion_tokens=None,
                    latency_ms=_elapsed_ms(started),
                )
            )
            return
        if provider is None:
            raise AgentNotConfiguredError("llm_not_configured")

        messages: list[dict[str, object]] = [
            {"role": "system", "content": system_prompt()}
        ]
        messages.extend(dict(message) for message in history[-20:])
        messages.append({"role": "user", "content": text})
        invocations: list[ToolInvocation] = []
        tool_results: list[object] = []
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        draft: str | None = None

        try:
            async with asyncio.timeout(TOTAL_BUDGET_SECONDS):
                for _ in range(MAX_TOOL_ITERATIONS):
                    remaining = _remaining_budget(started)
                    response = await provider.chat(
                        messages,
                        TOOL_DEFINITIONS,
                        timeout=remaining,
                    )
                    prompt_tokens = _add_optional(
                        prompt_tokens,
                        response.usage.prompt_tokens if response.usage else None,
                    )
                    completion_tokens = _add_optional(
                        completion_tokens,
                        response.usage.completion_tokens if response.usage else None,
                    )
                    if not response.tool_calls:
                        draft = response.content
                        break
                    assistant_message, calls = _provider_tool_message(response)
                    messages.append(assistant_message)
                    for call, safe_name, safe_arguments, execution_arguments in calls:
                        if len(invocations) >= MAX_TOOL_CALLS_PER_TURN:
                            break
                        yield ToolCallStarted(safe_name, safe_arguments)
                        result = await execute_tool(
                            safe_name,
                            execution_arguments,
                            session,
                        )
                        invocation = ToolInvocation(
                            name=safe_name,
                            arguments=safe_arguments,
                            result=result,
                        )
                        invocations.append(invocation)
                        tool_results.append(result)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": safe_name,
                                "content": _delimit_tool_result(result),
                            }
                        )
                        yield ToolResultReady(
                            safe_name,
                            result.get("ok") is True,
                        )
                    if len(invocations) >= MAX_TOOL_CALLS_PER_TURN:
                        break
        except TimeoutError:
            raise ProviderError("provider_timeout") from None

        if draft:
            output_check = check_output(draft, tool_results)
            if output_check.passed:
                yield AgentCompleted(
                    _run_result(
                        draft,
                        "ok",
                        language,
                        invocations,
                        prompt_tokens,
                        completion_tokens,
                        started,
                    )
                )
                return
            retry = await self._retry_once(
                provider,
                messages,
                output_check,
                prompt_tokens,
                completion_tokens,
                started,
            )
            if retry is not None:
                retry_text, prompt_tokens, completion_tokens = retry
                retry_check = check_output(retry_text, tool_results)
                if retry_check.passed:
                    yield AgentCompleted(
                        _run_result(
                            retry_text,
                            "retried",
                            language,
                            invocations,
                            prompt_tokens,
                            completion_tokens,
                            started,
                        )
                    )
                    return

        fallback = _safe_fallback(invocations, language)
        if not check_output(fallback, tool_results).passed:
            fallback = (
                "داده‌ی ابزارِ تأییدشده در دسترس نیست."
                if language == "fa"
                else "No verified tool data is available."
            )
        yield AgentCompleted(
            _run_result(
                fallback,
                "failed",
                language,
                invocations,
                prompt_tokens,
                completion_tokens,
                started,
            )
        )

    async def _retry_once(
        self,
        provider: LLMProvider,
        messages: list[dict[str, object]],
        failed_check: OutputCheck,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        started: float,
    ) -> tuple[str, int | None, int | None] | None:
        feedback_parts = [
            "Revise the prior answer. Use only supported values and remove "
            "the listed terms."
        ]
        if failed_check.banned_words:
            feedback_parts.append(
                "Terms: " + ", ".join(sorted(set(failed_check.banned_words)))
            )
        if failed_check.ungrounded_numbers:
            feedback_parts.append(
                "Numbers: "
                + ", ".join(
                    sorted(
                        {finding.value for finding in failed_check.ungrounded_numbers}
                    )
                )
            )
        retry_messages: list[dict[str, object]] = [
            *messages,
            {"role": "system", "content": " ".join(feedback_parts)},
        ]
        remaining = _remaining_budget(started)
        try:
            async with asyncio.timeout(remaining):
                response = await provider.chat(retry_messages, (), timeout=remaining)
        except TimeoutError:
            raise ProviderError("provider_timeout") from None
        prompt_tokens = _add_optional(
            prompt_tokens,
            response.usage.prompt_tokens if response.usage else None,
        )
        completion_tokens = _add_optional(
            completion_tokens,
            response.usage.completion_tokens if response.usage else None,
        )
        if response.tool_calls or not response.content:
            return None
        return response.content, prompt_tokens, completion_tokens


def _provider_tool_message(
    response: ProviderResponse,
) -> tuple[dict[str, object], list[tuple[Any, str, dict[str, object], object]]]:
    calls: list[tuple[Any, str, dict[str, object], object]] = []
    provider_calls: list[dict[str, object]] = []
    for call in response.tool_calls:
        allowed = call.name in _SAFE_TOOL_NAMES
        safe_name = call.name if allowed else "unknown_tool"
        safe_arguments: dict[str, object] = {}
        execution_arguments: object = call.arguments
        try:
            serialized = (
                call.arguments
                if isinstance(call.arguments, str)
                else json.dumps(call.arguments, separators=(",", ":"))
            )
        except (TypeError, ValueError):
            serialized = ""
        if len(serialized) > MAX_TOOL_ARGUMENT_LENGTH:
            execution_arguments = {"invalid": "oversized"}
        elif allowed and isinstance(call.arguments, dict):
            safe_arguments = {
                key: value
                for key, value in call.arguments.items()
                if key in {"slug", "days", "limit"}
                and isinstance(value, (str, int))
                and not isinstance(value, bool)
            }
        elif allowed and isinstance(call.arguments, str):
            try:
                parsed = json.loads(call.arguments)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                safe_arguments = {
                    key: value
                    for key, value in parsed.items()
                    if key in {"slug", "days", "limit"}
                    and isinstance(value, (str, int))
                    and not isinstance(value, bool)
                }
        if not allowed or len(serialized) > MAX_TOOL_ARGUMENT_LENGTH:
            safe_arguments = {}
        provider_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": serialized
                    if len(serialized) <= MAX_TOOL_ARGUMENT_LENGTH
                    else "{}",
                },
            }
        )
        calls.append((call, safe_name, safe_arguments, execution_arguments))
    return (
        {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": provider_calls,
        },
        calls,
    )


def _delimit_tool_result(result: Mapping[str, object]) -> str:
    payload = json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return f"BEGIN_UNTRUSTED_TOOL_RESULT\n{payload}\nEND_UNTRUSTED_TOOL_RESULT"


def _safe_fallback(
    invocations: Sequence[ToolInvocation],
    language: str,
) -> str:
    projected = [
        {"tool": item.name, "data": _project_safe_data(item.result.get("data"))}
        for item in invocations
    ]
    projected = [item for item in projected if item["data"]]
    if not projected:
        return (
            "داده‌ی ابزارِ تأییدشده در دسترس نیست."
            if language == "fa"
            else "No verified tool data is available."
        )
    prefix = "داده‌های تأییدشده: " if language == "fa" else "Verified tool data: "
    return prefix + json.dumps(projected, ensure_ascii=False, sort_keys=True)


def _project_safe_data(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: projected
            for key, item in value.items()
            if isinstance(key, str)
            and key in _SAFE_FIELDS
            and (projected := _project_safe_data(item)) is not None
        }
    if isinstance(value, list):
        projected_list = [
            projected
            for item in value
            if (projected := _project_safe_data(item)) is not None
        ]
        return projected_list or None
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, Decimal)):
        return value
    if isinstance(value, str):
        if value in _SAFE_ENUM_VALUES or _NUMBER_OR_DATE.fullmatch(value):
            return value
    return None


def _add_optional(current: int | None, value: int | None) -> int | None:
    if current is None:
        return value
    return current + value if value is not None else current


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _remaining_budget(started: float) -> float:
    remaining = TOTAL_BUDGET_SECONDS - (time.perf_counter() - started)
    if remaining <= 0:
        raise ProviderError("provider_timeout")
    return remaining


def _run_result(
    text: str,
    status: str,
    language: str,
    invocations: Sequence[ToolInvocation],
    prompt_tokens: int | None,
    completion_tokens: int | None,
    started: float,
) -> AgentRun:
    return AgentRun(
        text=text,
        grounding_status=status,
        refusal=status == "refused",
        language=language,
        tool_names=tuple(dict.fromkeys(item.name for item in invocations)),
        tool_invocations=tuple(invocations),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=_elapsed_ms(started),
    )
