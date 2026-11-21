from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.research.health_score import run_health_score_study
from app.research.statistics import (
    expanding_past_terciles,
    fisher_spearman_interval,
    pinball_loss,
    spearman_correlation,
    wilson_interval,
)


def test_wilson_interval_matches_known_five_of_ten_value() -> None:
    lower, upper = wilson_interval(5, 10)

    assert lower == pytest.approx(0.236593, abs=1e-6)
    assert upper == pytest.approx(0.763407, abs=1e-6)


def test_pinball_loss_matches_hand_calculated_residuals() -> None:
    assert pinball_loss(0.25, realized=2.0, forecast=1.0) == pytest.approx(0.25)
    assert pinball_loss(0.25, realized=0.0, forecast=1.0) == pytest.approx(0.75)


def test_spearman_is_one_for_a_strictly_monotone_series() -> None:
    assert spearman_correlation([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_expanding_terciles_use_only_scores_strictly_before_each_date() -> None:
    dates = [date(2020, 1, 1) + timedelta(days=index) for index in range(32)]
    values = [(as_of, Decimal(index)) for index, as_of in enumerate(dates)]
    original = expanding_past_terciles(values)
    changed_future = expanding_past_terciles(
        [*values[:-1], (dates[-1], Decimal("999999"))]
    )

    assert original[dates[29]] is None
    assert original[dates[30]] == "high"
    assert original[dates[30]] == changed_future[dates[30]]


def test_fisher_interval_uses_independent_sample_size() -> None:
    assert fisher_spearman_interval(0.0, 3) is None
    interval = fisher_spearman_interval(0.5, 40)
    assert interval is not None
    assert interval[0] < 0.5 < interval[1]


def test_health_study_samples_calendar_dates_at_non_overlapping_horizons() -> None:
    start = date(2020, 1, 1)
    prices = tuple(
        (start + timedelta(days=index), Decimal(100 + index)) for index in range(200)
    )
    scores = tuple(
        (start + timedelta(days=index), Decimal(index % 100))
        for index in range(0, 200, 15)
    )

    result = run_health_score_study(
        {"btc": scores},
        {"btc": prices},
        protocol_commit=None,
    )
    btc = result["chains"][0]

    assert btc["horizons"][0]["n_independent"] == btc["horizons"][0]["n"]
    assert btc["horizons"][1]["n_independent"] == btc["horizons"][1]["n"]


def test_iid_normal_outcomes_have_near_nominal_calibration_rates() -> None:
    from app.research.scenarios import ScenarioOrigin, calibration_metrics

    generator = random.Random(20261121)
    origins = [
        ScenarioOrigin(
            chain="btc",
            as_of_date=date(2020, 1, 1) + timedelta(days=index * 30),
            horizon_days=30,
            method="scenarios-v1",
            realized=Decimal(str(generator.gauss(0.0, 1.0))),
            forecasts={
                "p10": Decimal("-1.2815515655"),
                "p50": Decimal("0"),
                "p90": Decimal("1.2815515655"),
            },
            n_independent=10,
        )
        for index in range(10_000)
    ]

    metrics = calibration_metrics(origins, include_wilson=True)
    assert metrics["below_p10"]["share"] == pytest.approx(0.10, abs=0.015)
    assert metrics["below_p50"]["share"] == pytest.approx(0.50, abs=0.02)
    assert metrics["above_p90"]["share"] == pytest.approx(0.10, abs=0.015)
    assert metrics["p10_p90_hit"]["share"] == pytest.approx(0.80, abs=0.02)
