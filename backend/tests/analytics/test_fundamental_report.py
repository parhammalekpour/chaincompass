from datetime import date, timedelta
from decimal import Decimal

from app.analytics.fundamental_report import (
    FundamentalReportSnapshot,
    RegimePoint,
    build_fundamental_report,
)

AS_OF = date(2026, 11, 20)


def _snapshot(
    *,
    chain: str = "eth",
    scores: dict[date, Decimal] | None = None,
    regime_rows: tuple[RegimePoint, ...] | None = None,
) -> FundamentalReportSnapshot:
    if scores is None:
        scores = {
            AS_OF: Decimal("61.00"),
            AS_OF - timedelta(days=30): Decimal("59.25"),
            AS_OF - timedelta(days=90): Decimal("50.00"),
        }
    if regime_rows is None:
        regime_rows = (
            RegimePoint(AS_OF - timedelta(days=2), "range", "normal"),
            RegimePoint(AS_OF - timedelta(days=1), "range", "normal"),
            RegimePoint(AS_OF, "range", "normal"),
        )
    return FundamentalReportSnapshot(
        chain=chain,
        as_of_date=AS_OF,
        scores=scores,
        confidence="Medium",
        coverage=Decimal("0.6000"),
        regime_rows=regime_rows,
        flags=(("deep_drawdown", "medium"), ("low_confidence", "info")),
        feature_values={
            "active_addresses_chg90": Decimal("0.125000000000"),
            "tx_count_chg90": Decimal("0.050000000000"),
            "tvl_usd_chg90": Decimal("0.100000000000"),
            "stablecoin_supply_usd_chg90": Decimal("0.020000000000"),
            "dex_volume_usd_chg90": Decimal("0.075000000000"),
            "fees_usd_chg90": Decimal("0.030000000000"),
            "drawdown_365d": Decimal("-0.200000000000"),
            "realized_vol_90d": Decimal("0.450000000000"),
            "volume_ratio_30_365": Decimal("1.250000000000"),
            "price_vs_sma200": Decimal("0.150000000000"),
        },
        component_percentiles={
            "active_addresses_chg90": Decimal("55.000000000000"),
            "tx_count_chg90": Decimal("55.000000000000"),
            "tvl_usd_chg90": Decimal("55.000000000000"),
            "stablecoin_supply_usd_chg90": Decimal("55.000000000000"),
            "dex_volume_usd_chg90": Decimal("55.000000000000"),
            "fees_usd_chg90": Decimal("55.000000000000"),
            "drawdown_365d": Decimal("72.500000000000"),
            "realized_vol_90d": Decimal("55.000000000000"),
            "volume_ratio_30_365": Decimal("55.000000000000"),
            "price_vs_sma200": Decimal("55.000000000000"),
        },
    )


def _assert_no_float(value: object) -> None:
    if isinstance(value, float):
        raise AssertionError("report contains a float")
    if isinstance(value, dict):
        for key, nested in value.items():
            _assert_no_float(key)
            _assert_no_float(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_no_float(nested)


def test_full_report_is_decimal_string_only_and_deterministic() -> None:
    first = build_fundamental_report(_snapshot())
    second = build_fundamental_report(_snapshot())

    assert first == second
    assert first["chain"] == "eth"
    health = first["health"]
    assert health["score"] == "61.00"
    assert health["change_30d"] == "1.75"
    assert health["change_90d"] == "11.00"
    assert all(
        indicator["status"] == "available"
        for indicator in first["indicators"]
        if indicator["group"] != "security"
    )
    regime = first["regime"]
    assert regime["since_date"] == (AS_OF - timedelta(days=2)).isoformat()
    assert regime["days_in_regime"] == 3
    assert regime["history_gap"] is False
    assert first["flags"] == [
        {"code": "deep_drawdown", "severity": "medium"},
        {"code": "low_confidence", "severity": "info"},
    ]
    _assert_no_float(first)


def test_btc_components_mark_capital_indicators_not_applicable() -> None:
    report = build_fundamental_report(_snapshot(chain="btc"))
    indicators = report["indicators"]
    capital = [item for item in indicators if item["group"] == "capital"]
    assert len(capital) == 3
    assert all(item["status"] == "not_applicable" for item in capital)
    fees = next(item for item in indicators if item["key"] == "fees_usd_chg90")
    assert fees["group"] == "security"
    assert fees["status"] == "available"
    assert fees["value"] == "0.030000000000"


def test_missing_exact_30_day_score_has_no_change_or_substitute() -> None:
    scores = {
        AS_OF: Decimal("61.00"),
        AS_OF - timedelta(days=29): Decimal("60.00"),
        AS_OF - timedelta(days=90): Decimal("50.00"),
    }
    report = build_fundamental_report(_snapshot(scores=scores))
    health = report["health"]

    assert health["score_30d_ago"] is None
    assert health["change_30d"] is None
    assert health["score_90d_ago"] == "50.00"


def test_regime_history_gap_starts_a_new_gap_free_run() -> None:
    rows = (
        RegimePoint(AS_OF - timedelta(days=3), "range", "normal"),
        RegimePoint(AS_OF - timedelta(days=1), "range", "normal"),
        RegimePoint(AS_OF, "range", "normal"),
    )
    report = build_fundamental_report(_snapshot(regime_rows=rows))

    assert report["regime"]["since_date"] == (AS_OF - timedelta(days=1)).isoformat()
    assert report["regime"]["days_in_regime"] == 2
    assert report["regime"]["history_gap"] is True


def test_regime_history_gap_before_latest_regime_transition_is_reported() -> None:
    rows = (
        RegimePoint(AS_OF - timedelta(days=4), "stress", "high"),
        RegimePoint(AS_OF - timedelta(days=2), "stress", "high"),
        RegimePoint(AS_OF - timedelta(days=1), "range", "normal"),
        RegimePoint(AS_OF, "range", "normal"),
    )
    report = build_fundamental_report(_snapshot(regime_rows=rows))

    assert report["regime"]["since_date"] == (AS_OF - timedelta(days=1)).isoformat()
    assert report["regime"]["days_in_regime"] == 2
    assert report["regime"]["history_gap"] is True


def test_no_score_at_as_of_returns_no_data_shape_and_fixed_gaps() -> None:
    empty = _snapshot(scores={})
    assert build_fundamental_report(empty) == {
        "ok": False,
        "error": {"code": "no_data"},
    }

    report = build_fundamental_report(_snapshot())
    fixed = [
        entry
        for entry in report["data_gaps"]
        if entry["key"] in {"holder_distribution", "exchange_flows", "news_evidence"}
    ]
    assert fixed == [
        {"key": "holder_distribution", "status": "not_available_free"},
        {"key": "exchange_flows", "status": "not_available_free"},
        {"key": "news_evidence", "status": "not_available_free"},
    ]
