import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.public import (
    _date_range,
)
from app.api.v1.public import (
    get_chain as public_get_chain,
)
from app.api.v1.public import (
    get_chain_scenarios as public_get_scenarios,
)
from app.api.v1.public import (
    get_methodology as public_get_methodology,
)
from app.api.v1.public import (
    get_regime_segments as public_get_regime_segments,
)
from app.api.v1.public import (
    get_score_history as public_get_score_history,
)
from app.api.v1.public import (
    list_chains as public_list_chains,
)
from app.core.errors import APIError
from app.schemas.public_api import AnalysisResponse
from app.services.fundamental_report import load_fundamental_report

CHAIN_SLUGS = ("btc", "eth", "sol", "bnb")


def _slug_schema() -> dict[str, object]:
    return {"type": "string", "enum": list(CHAIN_SLUGS)}


TOOL_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "type": "function",
        "function": {
            "name": "list_chains",
            "description": "List supported chains with their latest public metrics.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chain_snapshot",
            "description": "Get a chain's latest score, regime, flags, and coverage.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"slug": _slug_schema()},
                "additionalProperties": False,
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamental_report",
            "description": "Get a deterministic report built from stored chain data.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"slug": _slug_schema()},
                "additionalProperties": False,
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_score_history_summary",
            "description": "Summarize stored score values and historical changes.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": _slug_schema(),
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 3650,
                    },
                },
                "additionalProperties": False,
                "required": ["slug", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_regime_history",
            "description": "Get recent reported regime segments for a chain.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": _slug_schema(),
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
                "required": ["slug", "limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scenarios",
            "description": "Get historical return quantiles and sample metadata.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"slug": _slug_schema()},
                "additionalProperties": False,
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_methodology_summary",
            "description": "Get score, regime, and scenario methodology metadata.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": [],
            },
        },
    },
)


def _error_result(code: str) -> dict[str, object]:
    return {
        "ok": False,
        "error": {"code": code},
        "as_of": None,
        "generated_at": datetime.now(UTC).isoformat(),
        "analysis_only": True,
    }


def _response_result(response: AnalysisResponse) -> dict[str, object]:
    data = response.model_dump(mode="json")
    return {
        "ok": True,
        "as_of": _as_of_date(data),
        "generated_at": response.generated_at.isoformat(),
        "analysis_only": True,
        "data": data,
    }


def _as_of_date(data: Mapping[str, object]) -> str | None:
    for key in ("as_of_date", "as_of"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    price = data.get("price")
    if isinstance(price, Mapping):
        value = price.get("as_of_date")
        if isinstance(value, str):
            return value
    chains = data.get("chains")
    if isinstance(chains, list):
        dates: list[str] = []
        for chain in chains:
            if not isinstance(chain, Mapping):
                continue
            price = chain.get("price")
            score = chain.get("score")
            for record in (price, score):
                if isinstance(record, Mapping):
                    value = record.get("as_of_date")
                    if isinstance(value, str):
                        dates.append(value)
        return max(dates) if dates else None
    segments = data.get("segments")
    if isinstance(segments, list):
        end_dates = [
            segment["end_date"]
            for segment in segments
            if isinstance(segment, Mapping) and isinstance(segment.get("end_date"), str)
        ]
        return max(end_dates) if end_dates else None
    return None


def _parse_arguments(
    name: str,
    arguments: object,
) -> dict[str, object]:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            raise ValueError("invalid_arguments") from None
    if not isinstance(arguments, dict) or any(
        not isinstance(key, str) for key in arguments
    ):
        raise ValueError("invalid_arguments")

    required: dict[str, tuple[str, ...]] = {
        "list_chains": (),
        "get_methodology_summary": (),
        "get_chain_snapshot": ("slug",),
        "get_fundamental_report": ("slug",),
        "get_score_history_summary": ("slug", "days"),
        "get_regime_history": ("slug", "limit"),
        "get_scenarios": ("slug",),
    }
    if name not in required:
        raise LookupError("unknown_tool")
    fields = {
        "list_chains": set(),
        "get_methodology_summary": set(),
        "get_chain_snapshot": {"slug"},
        "get_fundamental_report": {"slug"},
        "get_score_history_summary": {"slug", "days"},
        "get_regime_history": {"slug", "limit"},
        "get_scenarios": {"slug"},
    }[name]
    if set(arguments) != fields or any(
        field not in arguments for field in required[name]
    ):
        raise ValueError("invalid_arguments")
    slug = arguments.get("slug")
    if slug is not None and slug not in CHAIN_SLUGS:
        raise ValueError("invalid_arguments")
    if name == "get_score_history_summary":
        days = arguments.get("days")
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
            raise ValueError("invalid_arguments")
    if name == "get_regime_history":
        limit = arguments.get("limit")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 20
        ):
            raise ValueError("invalid_arguments")
    return arguments


def _integer_argument(arguments: Mapping[str, object], key: str) -> int:
    value = arguments[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("Validated tool argument changed type")
    return value


async def execute_tool(
    name: str,
    arguments: object,
    session: AsyncSession,
) -> dict[str, object]:
    response: AnalysisResponse
    try:
        args = _parse_arguments(name, arguments)
    except LookupError:
        return _error_result("unknown_tool")
    except ValueError:
        return _error_result("invalid_arguments")

    try:
        if name == "list_chains":
            response = await public_list_chains(session)
        elif name == "get_methodology_summary":
            response = await public_get_methodology()
        elif name == "get_chain_snapshot":
            response = await public_get_chain(str(args["slug"]), None, session)
        elif name == "get_fundamental_report":
            report = await load_fundamental_report(session, str(args["slug"]))
            if report.get("ok") is False:
                return _error_result("report_not_available")
            return _fundamental_report_result(report)
        elif name == "get_score_history_summary":
            response = await _score_history_summary(
                session,
                str(args["slug"]),
                _integer_argument(args, "days"),
            )
        elif name == "get_regime_history":
            _, latest_date = await _date_range(session, str(args["slug"]), None, None)
            start_date = latest_date - timedelta(days=3649)
            response = await public_get_regime_segments(
                str(args["slug"]), start_date, latest_date, session
            )
            data = response.model_dump(mode="json")
            data["segments"] = data["segments"][-_integer_argument(args, "limit") :]
            result = _response_result(response)
            result["data"] = data
            return result
        elif name == "get_scenarios":
            response = await public_get_scenarios(str(args["slug"]), None, session)
        else:
            return _error_result("unknown_tool")
    except APIError as exc:
        return _error_result(exc.code)
    return _response_result(response)


def _fundamental_report_result(report: dict[str, object]) -> dict[str, object]:
    chain = report.get("chain")
    as_of = report.get("as_of_date")
    health = report.get("health")
    regime = report.get("regime")
    flags = report.get("flags")
    data_gaps = report.get("data_gaps")
    if not isinstance(health, Mapping) or not isinstance(regime, Mapping):
        raise RuntimeError("The fundamental report has an invalid shape")

    def field_text(value: object) -> str:
        return value if isinstance(value, str) else "unavailable"

    summary = (
        f"chain={field_text(chain)} as_of={field_text(as_of)} "
        f"score={field_text(health.get('score'))} "
        f"change_30d={field_text(health.get('change_30d'))} "
        f"change_90d={field_text(health.get('change_90d'))} "
        f"regime={field_text(regime.get('regime'))} "
        f"flags={len(flags) if isinstance(flags, list) else 0} "
        f"data_gaps={len(data_gaps) if isinstance(data_gaps, list) else 0}"
    )
    return {
        "ok": True,
        "as_of": as_of if isinstance(as_of, str) else None,
        "generated_at": datetime.now(UTC).isoformat(),
        "analysis_only": True,
        "summary": summary,
        "data": report,
    }


async def _score_history_summary(
    session: AsyncSession,
    slug: str,
    days: int,
) -> AnalysisResponse:
    _, latest_date = await _date_range(session, slug, None, None)
    start = latest_date - timedelta(days=days - 1)
    history = await public_get_score_history(slug, start, None, session)
    items = history.items
    latest = items[-1] if items else None
    changes: dict[str, object] = {}
    if latest is not None:
        for period in (30, 90, 365):
            target_date = latest.as_of_date - timedelta(days=period)
            baseline = next(
                (item for item in reversed(items) if item.as_of_date <= target_date),
                None,
            )
            changes[str(period)] = (
                {
                    "from_date": baseline.as_of_date.isoformat(),
                    "to_date": latest.as_of_date.isoformat(),
                    "change": str(latest.score - baseline.score),
                }
                if baseline is not None
                else None
            )
    gap_days = sum(
        max(0, (current.as_of_date - previous.as_of_date).days - 1)
        for previous, current in zip(items, items[1:], strict=False)
    )
    summary = {
        "chain": slug,
        "days": days,
        "count": len(items),
        "minimum": str(min((item.score for item in items), default=Decimal(0)))
        if items
        else None,
        "maximum": str(max((item.score for item in items), default=Decimal(0)))
        if items
        else None,
        "latest": (
            {
                "score": str(latest.score),
                "as_of_date": latest.as_of_date.isoformat(),
                "coverage": str(latest.coverage),
                "confidence_label": latest.confidence_label,
                "is_partial": latest.is_partial,
            }
            if latest is not None
            else None
        ),
        "changes": changes,
        "gap_days": gap_days,
    }
    return _ToolAnalysisResponse(
        generated_at=history.generated_at,
        analysis_only=True,
        data=summary,
        as_of=latest.as_of_date.isoformat() if latest is not None else None,
    )


class _ToolAnalysisResponse(AnalysisResponse):
    data: dict[str, Any]
    as_of: str | None
