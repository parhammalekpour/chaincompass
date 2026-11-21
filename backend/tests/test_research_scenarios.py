from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.analytics.scenarios import PricePoint
from app.research.reports import json_report, scenario_markdown
from app.research.scenarios import (
    _label_v1,
    run_scenario_study,
    scenario_forecasts_at_origin,
)


def _price_series(days: int) -> tuple[PricePoint, ...]:
    start = date(2020, 1, 1)
    return tuple(
        (start + timedelta(days=index), Decimal(100 + index)) for index in range(days)
    )


def test_origin_forecast_is_unchanged_when_future_rows_are_truncated_or_changed() -> (
    None
):
    prices = _price_series(240)
    origin = prices[200][0]
    altered_future = (
        *prices[:201],
        *((day, Decimal("999999")) for day, _ in prices[201:]),
    )

    full_result = scenario_forecasts_at_origin(prices, origin)
    truncated_result = scenario_forecasts_at_origin(prices[:201], origin)
    altered_result = scenario_forecasts_at_origin(altered_future, origin)

    assert full_result == truncated_result == altered_result
    assert full_result[30].available


def test_repeated_study_rendering_is_deterministic() -> None:
    prices = {"btc": _price_series(240)}

    first = run_scenario_study(prices, protocol_commit="protocol-hash")
    second = run_scenario_study(prices, protocol_commit="protocol-hash")

    assert json_report(first) == json_report(second)
    sample = first["cells"][0]["methods"]["scenarios-v1"]["pooled"]
    assert "wilson_95" not in sample["all_origins"]["metrics"]["below_p10"]
    assert "wilson_95" in sample["non_overlapping"]["metrics"]["below_p10"]
    assert "Scenarios-v1 sample groups" in scenario_markdown(first)


def test_scenario_labels_follow_the_preregistered_interval_rule() -> None:
    def period(
        hit: list[float] | None,
        below: list[float] | None,
        above: list[float] | None,
    ) -> dict[str, object]:
        return {
            "non_overlapping": {
                "metrics": {
                    "p10_p90_hit": {"wilson_95": hit},
                    "below_p10": {"wilson_95": below},
                    "above_p90": {"wilson_95": above},
                }
            }
        }

    assert (
        _label_v1(
            period(
                [0.75, 0.85],
                [0.08, 0.12],
                [0.09, 0.11],
            )
        )
        == "well calibrated"
    )
    assert (
        _label_v1(
            period(
                [0.60, 0.70],
                [0.08, 0.12],
                [0.08, 0.12],
            )
        )
        == "miscalibrated"
    )
    assert (
        _label_v1(
            period(
                [0.75, 0.85],
                [0.01, 0.04],
                [0.08, 0.12],
            )
        )
        == "inconclusive"
    )
