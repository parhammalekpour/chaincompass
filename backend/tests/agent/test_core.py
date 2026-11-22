from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import tools
from app.agent.grounding import find_ungrounded_numbers, normalize_digits
from app.agent.guardrails import (
    MessageTooLongError,
    check_output,
    classify_input,
    detect_language,
    refusal_text,
    validate_message_length,
)
from app.agent.providers.base import ProviderError, ProviderResponse, ToolCall
from app.agent.providers.fake import FakeProvider
from app.agent.providers.openai_compatible import OpenAICompatibleProvider


def test_grounding_accepts_exact_rounded_percentage_and_structural_numbers() -> None:
    result = {
        "score": "85.25",
        "return": "0.8500",
        "as_of": "2026-03-15",
        "horizon": 30,
    }
    answer = (
        "Score 85.3, a return of 85%, and the 30-day p10 view (/100), as of 2026-03-15."
    )

    assert find_ungrounded_numbers(answer, [result]) == []
    assert normalize_digits("امتیاز ۸۵٫۳ و ١٢") == "امتیاز 85.3 و 12"


def test_grounding_flags_bare_90_but_ignores_90_day_window() -> None:
    findings = find_ungrounded_numbers("90 and 90 days", [])

    assert [finding.value for finding in findings] == ["90"]


def test_grounding_currently_accepts_half_up_rounding_from_34_70_to_35() -> None:
    # This pins the documented comparison at the answer's displayed precision.
    assert find_ungrounded_numbers("Score 35.", [{"score": "34.70"}]) == []


def test_grounding_reports_unmatched_numbers_with_positions() -> None:
    findings = find_ungrounded_numbers(
        "Score 55.5 and 88.",
        [{"score": "55.5"}],
    )

    assert len(findings) == 1
    assert findings[0].value == "88"
    assert "88" == "Score 55.5 and 88."[findings[0].start : findings[0].end]


def test_grounding_normalizes_persian_answer_digits_and_ignores_dates() -> None:
    findings = find_ungrounded_numbers(
        "امتیاز ۸۵٫۲۵ در ۲۰۲۶-۰۳-۱۵",
        [{"score": Decimal("85.25"), "as_of": "2026-03-15"}],
    )

    assert findings == []


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Should I buy this asset?", "advice"),
        ("Give me a price target", "target"),
        ("Predict the price next month", "future_claim"),
        ("برای من خرید یا فروش را مشخص کن", "restricted_financial_request"),
    ],
)
def test_guardrails_classify_restricted_requests(text: str, intent: str) -> None:
    assert classify_input(text) == intent


def test_guardrails_allow_analysis_and_detect_banned_output() -> None:
    assert classify_input("Summarize BTC score history") is None
    result = check_output("The prediction is 88.", [{"score": "55"}])
    assert result.banned_words == ("prediction",)
    assert [item.value for item in result.ungrounded_numbers] == ["88"]


def test_language_refusal_and_length_rules() -> None:
    assert detect_language("What is the score?") == "en"
    assert detect_language("وضعیت شبکه چیست؟") == "fa"
    assert "historical" in refusal_text("en")
    assert "داده‌های تاریخی" in refusal_text("fa")
    validate_message_length("x" * 2000)
    with pytest.raises(MessageTooLongError):
        validate_message_length("x" * 2001)


@pytest.mark.asyncio
async def test_fake_provider_records_requests_and_returns_scripted_response() -> None:
    expected = ProviderResponse(content="Available values are in the data.")
    provider = FakeProvider([expected])

    actual = await provider.chat(
        [{"role": "user", "content": "Summarize the data"}],
        [],
        timeout=1,
    )

    assert actual is expected
    assert provider.requests[0][0][0]["role"] == "user"


@pytest.mark.asyncio
async def test_openai_compatible_provider_retries_server_error_once() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "list_chains",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        api_key="test-key",
        model="test-model",
        client=client,
    )
    result = await provider.chat([], [], timeout=10)

    assert len(requests) == 2
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert result.tool_calls == (ToolCall("call-1", "list_chains", "{}"),)
    assert result.usage is not None
    assert result.usage.prompt_tokens == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_compatible_provider_retries_timeout_once() -> None:
    attempts = 0

    def timeout(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timeout")

    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        api_key="test-key",
        model="test-model",
        client=client,
    )
    with pytest.raises(ProviderError, match="provider_timeout"):
        await provider.chat([], [], timeout=10)
    assert attempts == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_provider_does_not_log_key_or_message_body(caplog) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Done."}}],
                },
            )
        )
    )
    provider = OpenAICompatibleProvider(
        base_url="https://provider.test/v1",
        api_key="private-test-key",
        model="test-model",
        client=client,
    )
    await provider.chat(
        [{"role": "user", "content": "private prompt body"}],
        [],
        timeout=1,
    )
    assert "private-test-key" not in caplog.text
    assert "private prompt body" not in caplog.text
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("get_chain_snapshot", {"slug": "doge"}),
        ("get_fundamental_report", {"slug": "doge"}),
        ("get_score_history_summary", {"slug": "btc", "days": 3651}),
        ("get_regime_history", {"slug": "btc", "limit": True}),
        ("unknown", {}),
    ],
)
async def test_tool_bad_arguments_return_tool_errors(
    name: str,
    arguments: object,
) -> None:
    result = await tools.execute_tool(name, arguments, cast(AsyncSession, None))
    assert result["ok"] is False
    assert result["as_of"] is None
    assert result["analysis_only"] is True
    assert result["error"]["code"] in {"invalid_arguments", "unknown_tool"}  # type: ignore[index]


@pytest.mark.asyncio
async def test_fundamental_report_tool_uses_loader_and_builds_summary(
    monkeypatch,
) -> None:
    report = {
        "chain": "btc",
        "as_of_date": "2026-11-20",
        "health": {
            "score": "55.25",
            "change_30d": "1.25",
            "change_90d": "-2.50",
        },
        "regime": {"regime": "range"},
        "flags": [{"code": "deep_drawdown", "severity": "medium"}],
        "data_gaps": [{}, {}, {}],
    }
    received: list[tuple[object, str]] = []

    async def load(session: object, slug: str) -> dict[str, object]:
        received.append((session, slug))
        return report

    monkeypatch.setattr(tools, "load_fundamental_report", load)
    session = object()
    result = await tools.execute_tool(
        "get_fundamental_report",
        {"slug": "btc"},
        cast(AsyncSession, session),
    )

    assert received == [(session, "btc")]
    assert result["ok"] is True
    assert result["as_of"] == "2026-11-20"
    assert result["summary"] == (
        "chain=btc as_of=2026-11-20 score=55.25 change_30d=1.25 "
        "change_90d=-2.50 regime=range flags=1 data_gaps=3"
    )
    assert result["data"] is report


@pytest.mark.asyncio
async def test_chain_tool_returns_same_payload_as_public_service(monkeypatch) -> None:
    generated_at = datetime.now(UTC)
    response_data = {
        "generated_at": generated_at.isoformat(),
        "analysis_only": True,
        "slug": "btc",
        "price": {"as_of_date": "2026-11-20"},
    }
    public_response = SimpleNamespace(
        generated_at=generated_at,
        model_dump=lambda mode: response_data,
    )
    received: list[tuple[str, object, object]] = []

    async def get_chain(slug: str, as_of: object, session: object) -> object:
        received.append((slug, as_of, session))
        return public_response

    monkeypatch.setattr(tools, "public_get_chain", get_chain)
    session = object()
    result = await tools.execute_tool(
        "get_chain_snapshot",
        {"slug": "btc"},
        cast(AsyncSession, session),
    )

    assert received == [("btc", None, session)]
    assert result == {
        "ok": True,
        "as_of": "2026-11-20",
        "generated_at": generated_at.isoformat(),
        "analysis_only": True,
        "data": response_data,
    }


def test_tool_schemas_are_closed_and_limit_chains_to_supported_slugs() -> None:
    snapshot_schema = next(
        entry["function"]
        for entry in tools.TOOL_DEFINITIONS
        if entry["function"]["name"] == "get_chain_snapshot"  # type: ignore[index]
    )
    parameters = snapshot_schema["parameters"]  # type: ignore[index]
    assert parameters["additionalProperties"] is False  # type: ignore[index]
    assert parameters["properties"]["slug"]["enum"] == [  # type: ignore[index]
        "btc",
        "eth",
        "sol",
        "bnb",
    ]
    report_schema = next(
        entry["function"]
        for entry in tools.TOOL_DEFINITIONS
        if entry["function"]["name"] == "get_fundamental_report"  # type: ignore[index]
    )
    assert report_schema["parameters"]["additionalProperties"] is False  # type: ignore[index]
