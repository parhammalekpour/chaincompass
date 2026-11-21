import pytest

from app.agent.guardrails import check_output
from app.agent.orchestrator import ToolInvocation, _safe_fallback

_SNAPSHOT = {
    "ok": True,
    "data": {
        "slug": "btc",
        "score": {
            "value": "55.25",
            "coverage": "0.6000",
            "coverage_max": "0.7000",
            "confidence_label": "Medium",
            "is_partial": True,
            "as_of_date": "2026-11-20",
        },
    },
}

_TOOL_RESULTS = {
    "list_chains": {
        "ok": True,
        "data": {
            "chains": [
                {
                    "slug": "btc",
                    "score": {
                        "value": "55.25",
                        "coverage": "0.6000",
                        "coverage_max": "0.7000",
                        "confidence_label": "Medium",
                        "is_partial": True,
                    },
                }
            ]
        },
    },
    "get_chain_snapshot": _SNAPSHOT,
    "get_score_history_summary": {
        "ok": True,
        "data": {
            "chain": "btc",
            "days": 30,
            "count": 3,
            "minimum": "44.0",
            "maximum": "55.25",
            "latest": {
                "score": "55.25",
                "as_of_date": "2026-11-20",
                "coverage": "0.6000",
                "confidence_label": "Medium",
                "is_partial": True,
            },
            "changes": {
                "30": {
                    "from_date": "2026-10-20",
                    "to_date": "2026-11-20",
                    "change": "1.25",
                }
            },
        },
    },
    "get_regime_history": {
        "ok": True,
        "data": {
            "chain": "btc",
            "segments": [
                {
                    "regime": "range",
                    "start_date": "2026-10-01",
                    "end_date": "2026-11-20",
                    "days": 50,
                }
            ],
            "latest_vol_state": "normal",
        },
    },
    "get_scenarios": {
        "ok": True,
        "data": {
            "chain": "btc",
            "base_price": {"close_usd": "65000.00", "date": "2026-11-20"},
            "horizons": [
                {
                    "days": 30,
                    "low_sample": False,
                    "n_independent": 8,
                    "scenarios": [
                        {
                            "quantile": "p10",
                            "return": "-0.12",
                            "illustrative_price_usd": "57200.00",
                        },
                        {
                            "quantile": "p50",
                            "return": "0.03",
                            "illustrative_price_usd": "66950.00",
                        },
                    ],
                }
            ],
            "not_a_forecast": True,
        },
    },
    "get_methodology_summary": {
        "ok": True,
        "data": {
            "percentile_window_days": 365,
            "minimum_score_coverage": "0.5000",
            "scenarios": {
                "horizons_days": [30, 90, 365],
                "minimum_independent_windows": 4,
                "low_sample_below_independent_windows": 5,
            },
        },
    },
}


def _invocation(name: str, result: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name=name, arguments={}, result=result)


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (
            "en",
            "These are verified figures from the tools because the assistant's "
            "wording could not be verified.\n"
            "BTC score: 55.25; confidence Medium; coverage 0.6000 of 0.7000; "
            "partial; as of 2026-11-20.",
        ),
        (
            "fa",
            "این رقم‌ها از ابزارها تأیید شده‌اند، چون متن دستیار قابل تأیید نبود.\n"
            "امتیاز BTC: 55.25؛ اطمینان متوسط؛ پوشش 0.6000 از 0.7000؛ ناقص؛ "
            "در تاریخ 2026-11-20.",
        ),
    ],
)
def test_snapshot_fallback_is_readable_and_localized(
    language: str,
    expected: str,
) -> None:
    assert (
        _safe_fallback(
            [_invocation("get_chain_snapshot", _SNAPSHOT)],
            language,
        )
        == expected
    )


@pytest.mark.parametrize("language", ["en", "fa"])
def test_each_tool_fallback_is_plain_text_grounded_and_banned_word_clean(
    language: str,
) -> None:
    for name, result in _TOOL_RESULTS.items():
        fallback = _safe_fallback([_invocation(name, result)], language)

        assert "{" not in fallback
        assert "[" not in fallback
        assert '"' not in fallback
        assert check_output(fallback, [result]).passed


def test_unknown_tool_and_no_result_fallbacks_remain_safe() -> None:
    unknown = _safe_fallback(
        [_invocation("mystery_tool", {"ok": False, "error": {"code": "unknown"}})],
        "en",
    )
    assert unknown.endswith("Data retrieved: mystery_tool.")
    assert "{" not in unknown
    assert "[" not in unknown
    assert '"' not in unknown

    assert _safe_fallback([], "en") == "No verified tool data is available."
    assert _safe_fallback([], "fa") == "داده‌ی ابزارِ تأییدشده در دسترس نیست."


def test_fallback_is_limited_to_twelve_lines_and_uses_latin_digits() -> None:
    data = _TOOL_RESULTS["list_chains"]["data"]
    assert isinstance(data, dict)
    chains = data["chains"]
    assert isinstance(chains, list)
    result = {"ok": True, "data": {"chains": chains * 20}}
    fallback = _safe_fallback([_invocation("list_chains", result)], "fa")

    assert len(fallback.splitlines()) <= 12
    assert all(
        character in "0123456789" for character in fallback if character.isdigit()
    )
