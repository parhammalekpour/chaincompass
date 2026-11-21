import asyncio
import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
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
    lines: list[str] = []
    for invocation in invocations:
        data = invocation.result.get("data")
        if invocation.name not in _SAFE_TOOL_NAMES:
            name = _safe_tool_label(invocation.name)
            lines.append(
                f"داده‌ها دریافت شد: {name}."
                if language == "fa"
                else f"Data retrieved: {name}."
            )
        elif isinstance(data, Mapping):
            lines.extend(_format_tool_data(invocation.name, data, language))

    if not lines:
        return (
            "داده‌ی ابزارِ تأییدشده در دسترس نیست."
            if language == "fa"
            else "No verified tool data is available."
        )
    header = (
        "این رقم‌ها از ابزارها تأیید شده‌اند، چون متن دستیار قابل تأیید نبود."
        if language == "fa"
        else (
            "These are verified figures from the tools because the assistant's "
            "wording could not be verified."
        )
    )
    return "\n".join([header, *lines[:11]])


def _format_tool_data(
    name: str,
    data: Mapping[str, object],
    language: str,
) -> list[str]:
    if name == "list_chains":
        chains = data.get("chains")
        if not isinstance(chains, list):
            return []
        return [
            line
            for chain in chains[:10]
            if isinstance(chain, Mapping)
            and (line := _score_line(chain.get("score"), chain.get("slug"), language))
        ]
    if name == "get_chain_snapshot":
        line = _score_line(data.get("score"), data.get("slug"), language)
        if line:
            return [line]
        return []
    if name == "get_score_history_summary":
        return _score_history_lines(data, language)
    if name == "get_regime_history":
        return _regime_lines(data, language)
    if name == "get_scenarios":
        return _scenario_lines(data, language)
    if name == "get_methodology_summary":
        return _methodology_lines(data, language)
    return []


def _score_line(
    score_value: object,
    slug_value: object,
    language: str,
) -> str | None:
    chain = _chain_label(slug_value)
    if not isinstance(score_value, Mapping):
        score = _number_text(score_value)
        if score is None:
            return None
        return (
            f"امتیاز {chain}: {score}."
            if language == "fa"
            else f"{chain} score: {score}."
        )
    score = _number_text(score_value.get("value"))
    if score is None:
        score = _number_text(score_value.get("score"))
    if score is None:
        return None
    confidence = _confidence(score_value.get("confidence_label"), language)
    coverage = _number_text(score_value.get("coverage"))
    coverage_max = _number_text(score_value.get("coverage_max"))
    partial = score_value.get("is_partial")
    as_of = _date_text(score_value.get("as_of_date"))
    if language == "fa":
        line = f"امتیاز {chain}: {score}"
        if confidence:
            line += f"؛ اطمینان {confidence}"
        if coverage and coverage_max:
            line += f"؛ پوشش {coverage} از {coverage_max}"
        if partial is True:
            line += "؛ ناقص"
        if as_of:
            line += f"؛ در تاریخ {as_of}"
        return line + "."

    line = f"{chain} score: {score}"
    if confidence:
        line += f"; confidence {confidence}"
    if coverage and coverage_max:
        line += f"; coverage {coverage} of {coverage_max}"
    if partial is True:
        line += "; partial"
    if as_of:
        line += f"; as of {as_of}"
    return line + "."


def _score_history_lines(data: Mapping[str, object], language: str) -> list[str]:
    chain = _chain_label(data.get("chain"))
    minimum = _number_text(data.get("minimum"))
    maximum = _number_text(data.get("maximum"))
    count = _number_text(data.get("count"))
    days = _number_text(data.get("days"))
    lines: list[str] = []
    if language == "fa":
        if minimum and maximum:
            lines.append(f"بازهٔ امتیاز {chain}: {minimum} تا {maximum}.")
        if count and days:
            lines.append(f"تعداد داده‌ها در {days} روز: {count}.")
    else:
        if minimum and maximum:
            lines.append(f"{chain} score range: {minimum} to {maximum}.")
        if count and days:
            lines.append(f"Records over {days} days: {count}.")

    latest = data.get("latest")
    if isinstance(latest, Mapping):
        latest_line = _score_line(latest, data.get("chain"), language)
        if latest_line:
            lines.append(latest_line)
    changes = data.get("changes")
    if isinstance(changes, Mapping):
        for period, change in changes.items():
            period_text = _number_text(period)
            if period_text is None or not isinstance(change, Mapping):
                continue
            value = _number_text(change.get("change"))
            start = _date_text(change.get("from_date"))
            end = _date_text(change.get("to_date"))
            if value is None or start is None or end is None:
                continue
            if language == "fa":
                lines.append(
                    f"تغییر امتیاز {chain} در {period_text} روز: {value}؛ "
                    f"از {start} تا {end}."
                )
            else:
                lines.append(
                    f"{chain} score change over {period_text} days: {value}; "
                    f"from {start} to {end}."
                )
    return lines


def _regime_lines(data: Mapping[str, object], language: str) -> list[str]:
    chain = _chain_label(data.get("chain"))
    segments = data.get("segments")
    lines: list[str] = []
    if isinstance(segments, list):
        for segment in segments[:9]:
            if not isinstance(segment, Mapping):
                continue
            regime = _regime_label(segment.get("regime"), language)
            start = _date_text(segment.get("start_date"))
            end = _date_text(segment.get("end_date"))
            days = _number_text(segment.get("days"))
            if not regime or not start or not end or not days:
                continue
            if language == "fa":
                lines.append(
                    f"وضعیت {chain}: {regime}؛ از {start} تا {end}؛ {days} روز."
                )
            else:
                lines.append(f"{chain} regime {regime}: {start} to {end}; {days} days.")
    volatility = _regime_label(data.get("latest_vol_state"), language)
    if volatility:
        lines.append(
            f"وضعیت نوسان کنونی {chain}: {volatility}."
            if language == "fa"
            else f"Latest volatility state for {chain}: {volatility}."
        )
    return lines


def _scenario_lines(data: Mapping[str, object], language: str) -> list[str]:
    chain = _chain_label(data.get("chain"))
    lines = [
        (
            "بازه‌های سناریوی تاریخی فقط داده‌های گذشته را توصیف می‌کنند "
            "و آینده را بیان نمی‌کنند."
        )
        if language == "fa"
        else "Historical scenario ranges, not a forecast."
    ]
    base_price = data.get("base_price")
    if isinstance(base_price, Mapping):
        price = _number_text(base_price.get("close_usd"))
        date = _date_text(base_price.get("date"))
        if price and date:
            lines.append(
                f"قیمت مبنا برای {chain}: {price} در {date}."
                if language == "fa"
                else f"{chain} base price: {price} on {date}."
            )

    horizons = data.get("horizons")
    if isinstance(horizons, list):
        for horizon in horizons[:4]:
            if not isinstance(horizon, Mapping):
                continue
            days = _number_text(horizon.get("days"))
            if days is None:
                continue
            scenarios = horizon.get("scenarios")
            values: list[str] = []
            if isinstance(scenarios, list):
                for scenario in scenarios[:3]:
                    if not isinstance(scenario, Mapping):
                        continue
                    quantile = _quantile(scenario.get("quantile"))
                    returns = _number_text(scenario.get("return"))
                    price = _number_text(scenario.get("illustrative_price_usd"))
                    if quantile and returns and price:
                        values.append(
                            f"{quantile} {returns}, value {price}"
                            if language != "fa"
                            else f"{quantile} {returns}، مقدار {price}"
                        )
            independent = _number_text(horizon.get("n_independent"))
            low_sample = horizon.get("low_sample")
            if horizon.get("available") is False:
                detail = (
                    "داده‌های تاریخی در دسترس نیستند"
                    if language == "fa"
                    else "historical values unavailable"
                )
            elif values:
                detail = "; ".join(values)
            else:
                detail = (
                    "سناریوی تاریخی گزارش نشده"
                    if language == "fa"
                    else "no historical scenario values reported"
                )
            if independent:
                detail += (
                    f"؛ تعداد پنجره‌های مستقل {independent}"
                    if language == "fa"
                    else f"; independent windows {independent}"
                )
            if low_sample is True:
                detail += "; low sample" if language != "fa" else "؛ نمونهٔ کم"
            elif low_sample is False:
                detail += "; sample adequate" if language != "fa" else "؛ نمونهٔ کافی"
            if language == "fa":
                lines.append(f"سناریوی تاریخی {chain} در {days} روز: {detail}.")
            else:
                lines.append(f"{chain} historical scenario at {days} days: {detail}.")
    return lines


def _methodology_lines(data: Mapping[str, object], language: str) -> list[str]:
    window = _number_text(data.get("percentile_window_days"))
    coverage = _number_text(data.get("minimum_score_coverage"))
    lines: list[str] = []
    if window:
        lines.append(
            f"پنجرهٔ صدک: {window} روز."
            if language == "fa"
            else f"Percentile window: {window} days."
        )
    if coverage:
        lines.append(
            f"حداقل پوشش امتیاز: {coverage}."
            if language == "fa"
            else f"Minimum score coverage: {coverage}."
        )
    scenarios = data.get("scenarios")
    if isinstance(scenarios, Mapping):
        horizons = scenarios.get("horizons_days")
        if isinstance(horizons, list):
            values = [
                value
                for item in horizons[:5]
                if (value := _number_text(item)) is not None
            ]
            if values:
                joined = ", ".join(values)
                lines.append(
                    f"افق‌های سناریو: {joined} روز."
                    if language == "fa"
                    else f"Scenario horizons: {joined} days."
                )
        minimum = _number_text(scenarios.get("minimum_independent_windows"))
        low_sample = _number_text(scenarios.get("low_sample_below_independent_windows"))
        if minimum:
            lines.append(
                f"حداقل پنجره‌های مستقل: {minimum}."
                if language == "fa"
                else f"Minimum independent windows: {minimum}."
            )
        if low_sample:
            lines.append(
                f"آستانهٔ نمونهٔ کم: کمتر از {low_sample} پنجرهٔ مستقل."
                if language == "fa"
                else f"Low-sample threshold: below {low_sample} independent windows."
            )
    return lines


def _chain_label(value: object) -> str:
    if isinstance(value, str) and value in {"btc", "eth", "sol", "bnb"}:
        return value.upper()
    return "chain"


def _number_text(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if (
        isinstance(value, str)
        and value
        and all(character in "0123456789.+-" for character in value)
    ):
        return value
    return None


def _date_text(value: object) -> str | None:
    if (
        isinstance(value, str)
        and len(value) == 10
        and value[4] == "-"
        and value[7] == "-"
        and value[:4].isdigit()
        and value[5:7].isdigit()
        and value[8:].isdigit()
    ):
        return value
    return None


def _confidence(value: object, language: str) -> str | None:
    if not isinstance(value, str):
        return None
    labels = {
        "High": "زیاد",
        "Medium": "متوسط",
        "Low": "کم",
    }
    if value in labels:
        return value if language != "fa" else labels[value]
    return None


def _regime_label(value: object, language: str) -> str | None:
    if not isinstance(value, str):
        return None
    labels = {
        "stress": "تنش",
        "uptrend": "روند صعودی",
        "downtrend": "روند نزولی",
        "range": "دامنه‌ای",
        "normal": "عادی",
        "high": "زیاد",
        "low": "کم",
    }
    if value in labels:
        return value if language != "fa" else labels[value]
    return None


def _quantile(value: object) -> str | None:
    if isinstance(value, str) and value in {"p10", "p50", "p90"}:
        return value
    return None


def _safe_tool_label(value: str) -> str:
    if len(value) <= 64 and value.isascii() and value.replace("_", "").isalnum():
        return value
    return "unknown_tool"


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
