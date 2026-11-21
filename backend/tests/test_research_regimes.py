from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from app.analytics.scoring import FeatureRecord, compute_analytics
from app.research.regimes import RegimePoint, regime_v2

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "research_regime_v1.json"


def test_v1_matches_stored_regime_fixture() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    features: list[FeatureRecord] = []
    for row in fixture["features"]:
        first_date = date.fromisoformat(row["start"])
        for offset, value in enumerate(row["values"]):
            features.append(
                FeatureRecord(
                    chain="btc",
                    feature=row["feature"],
                    as_of_date=first_date + timedelta(days=offset),
                    value=Decimal(value),
                    source_metric="price_close_usd",
                    source="binance",
                )
            )

    result = compute_analytics("btc", features)
    actual = [
        [item.as_of_date.isoformat(), item.regime, item.raw_regime]
        for item in result.regimes
    ]

    assert actual == fixture["expected"]


def test_v2_enters_stress_immediately_and_exits_after_five_nonstress_days() -> None:
    first = date(2021, 1, 1)
    raw_labels = [
        "uptrend",
        "uptrend",
        "stress",
        "range",
        "range",
        "range",
        "range",
        "range",
    ]
    raw = tuple(
        RegimePoint(first + timedelta(days=index), label, label)
        for index, label in enumerate(raw_labels)
    )

    result = regime_v2(raw)

    assert [point.regime for point in result] == [
        "uptrend",
        "uptrend",
        "stress",
        "stress",
        "stress",
        "stress",
        "stress",
        "range",
    ]


def test_v2_gap_does_not_count_toward_five_day_stress_exit() -> None:
    first = date(2021, 1, 1)
    raw = (
        RegimePoint(first, "stress", "stress"),
        RegimePoint(first + timedelta(days=1), "range", "range"),
        RegimePoint(first + timedelta(days=2), "range", "range"),
        RegimePoint(first + timedelta(days=4), "range", "range"),
        RegimePoint(first + timedelta(days=5), "range", "range"),
        RegimePoint(first + timedelta(days=6), "range", "range"),
        RegimePoint(first + timedelta(days=7), "range", "range"),
        RegimePoint(first + timedelta(days=8), "range", "range"),
    )

    result = regime_v2(raw)

    assert [point.regime for point in result] == [
        "stress",
        "stress",
        "stress",
        "stress",
        "stress",
        "stress",
        "stress",
        "range",
    ]
