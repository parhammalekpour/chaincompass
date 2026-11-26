from __future__ import annotations

import importlib.util
import math
import os
from datetime import date, timedelta
from typing import Any

import pytest


def _research_import(name: str) -> Any:
    if os.getenv("CI", "").lower() == "true" and importlib.util.find_spec(name) is None:
        pytest.fail(f"required research dependency is missing in CI: {name}")
    return pytest.importorskip(name)


np = _research_import("numpy")
_research_import("sklearn")

from app.ml.baselines import (  # noqa: E402
    conditional_probabilities,
    fit_har,
    laplace_probability,
    predict_har,
)
from app.ml.bootstrap import moving_block_samples, paired_brier_intervals  # noqa: E402
from app.ml.dataset import DatasetRow  # noqa: E402
from app.ml.metrics import compute_metrics  # noqa: E402
from app.ml.models import fit_predict_fold  # noqa: E402
from app.ml.verdict import (  # noqa: E402
    PairCriteria,
    assess_informativeness,
    assess_pair,
    decide_verdict,
)


def _row(
    index: int,
    predictors: tuple[float, float, float],
    outcome_log: float,
    q80_log: float,
    label: int = 0,
) -> DatasetRow:
    first = date(2020, 1, 1)
    return DatasetRow(
        chain="btc",
        obs_date=first + timedelta(days=index),
        y=label,
        features=(0.0, math.exp(predictors[2]), *([0.0] * 14)),
        rv7=math.exp(predictors[0]),
        rv30=math.exp(predictors[1]),
        q80=math.exp(q80_log),
        rv30_fwd=math.exp(outcome_log),
    )


def test_brier_log_loss_auc_and_equal_count_reliability() -> None:
    labels = np.asarray([0, 1, 1, 0], dtype=np.int8)
    probabilities = np.asarray([0.1, 0.8, 0.7, 0.2], dtype=np.float64)
    result = compute_metrics(labels, probabilities)
    single_class = compute_metrics(
        np.asarray([0, 0], dtype=np.int8),
        np.asarray([0.1, 0.2], dtype=np.float64),
    )
    expected_log_loss = (
        -(math.log(0.9) + math.log(0.8) + math.log(0.7) + math.log(0.8)) / 4
    )

    assert result.brier == pytest.approx(0.045)
    assert result.log_loss == pytest.approx(expected_log_loss)
    assert result.auc == pytest.approx(1.0)
    assert result.ece == pytest.approx(0.2)
    assert [entry["count"] for entry in result.reliability] == [
        1,
        1,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
    ]
    assert result.reliability[0]["mean_probability"] == pytest.approx(0.1)
    assert result.reliability[0]["observed_rate"] == pytest.approx(0.0)
    assert single_class.auc is None


def test_calibration_slope_and_constant_probability_status() -> None:
    rng = np.random.default_rng(5521)
    probabilities = rng.uniform(0.05, 0.95, size=50000)
    labels = rng.binomial(1, probabilities).astype(np.int8)
    result = compute_metrics(labels, probabilities)
    constant = compute_metrics(
        np.asarray([0, 1, 0, 1], dtype=np.int8),
        np.full(4, 0.5, dtype=np.float64),
    )

    assert result.calibration_slope == pytest.approx(1.0, abs=0.04)
    assert result.calibration_intercept == pytest.approx(0.0, abs=0.04)
    assert constant.calibration_slope is None
    assert constant.calibration_intercept is None
    assert "constant probability" in constant.calibration_status


def test_har_recovers_coefficients_and_matches_manual_erf_probability() -> None:
    rng = np.random.default_rng(881)
    predictors = rng.normal(size=(100, 3))
    design = np.column_stack((np.ones(len(predictors)), predictors))
    coefficients = np.asarray([-3.0, 0.35, -0.2, 0.5])
    raw_noise = rng.normal(size=len(predictors))
    orthogonal_noise = raw_noise.copy()
    orthogonal_noise[:80] -= (
        design[:80]
        @ np.linalg.lstsq(
            design[:80],
            raw_noise[:80],
            rcond=None,
        )[0]
    )
    outcome_logs = design @ coefficients + 0.02 * orthogonal_noise
    rows = [
        _row(
            index,
            tuple(float(value) for value in predictors[index]),
            float(outcome_logs[index]),
            float(outcome_logs[index] + 0.1),
        )
        for index in range(len(predictors))
    ]
    fit = fit_har(rows[:80])
    probabilities = predict_har(fit, rows[80:])
    test_design = np.column_stack((np.ones(20), predictors[80:]))
    manual_prediction = test_design @ np.asarray(fit.coefficients)
    manual = np.asarray(
        [
            1.0
            - 0.5
            * (
                1.0
                + math.erf(
                    (math.log(rows[index].q80) - manual_prediction[index - 80])
                    / (fit.sigma * math.sqrt(2.0))
                )
            )
            for index in range(80, 100)
        ],
        dtype=np.float64,
    )

    assert fit.coefficients == pytest.approx(tuple(coefficients), abs=1e-10)
    assert probabilities == pytest.approx(manual, abs=1e-12)


def test_laplace_smoothing_empty_cell_and_single_class_model_fallback() -> None:
    assert laplace_probability([1, 1, 0]) == pytest.approx(0.6)
    cells = conditional_probabilities(
        ["active", "active", "other"],
        [1, 0, 0],
        ["active", "unseen"],
        overall_rate=0.4,
    )
    fallback = fit_predict_fold(
        "M1",
        np.ones((5, 16), dtype=np.float64),
        np.ones(5, dtype=np.int8),
        np.ones((3, 16), dtype=np.float64),
    )

    assert cells == pytest.approx([0.5, 0.4])
    assert fallback.used_single_class_fallback
    assert fallback.probabilities == pytest.approx([6 / 7] * 3)
    assert fallback.convergence_warnings == 0


def test_moving_block_bootstrap_is_synchronized_and_paired() -> None:
    n_dates = 240
    labels = np.tile(np.asarray([0] * 30 + [1] * 30, dtype=np.int8), 4)
    date_ids = np.arange(n_dates, dtype=np.int64)
    better = np.where(labels == 1, 0.9, 0.1).astype(np.float64)
    reference = np.full(n_dates, 0.5, dtype=np.float64)
    first = moving_block_samples(n_dates, 30, resamples=300, seed=12345)
    second = moving_block_samples(n_dates, 30, resamples=300, seed=12345)

    assert np.array_equal(first.starts, second.starts)
    assert np.array_equal(first.date_indices, second.date_indices)
    for sample_index, starts in enumerate(first.starts):
        for block_index, block_start in enumerate(starts):
            offset = block_index * first.block_length
            length = min(first.block_length, n_dates - offset)
            assert 0 <= block_start <= n_dates - first.block_length
            assert first.date_indices[
                sample_index, offset : offset + length
            ] == pytest.approx(
                np.arange(block_start, block_start + length, dtype=np.int64)
            )

    intervals = paired_brier_intervals(
        labels,
        date_ids,
        {"better": better, "identical": better.copy(), "reference": reference},
        (("better", "reference"), ("identical", "better")),
        first,
    )
    assert intervals[("identical", "better")].lower == pytest.approx(0.0)
    assert intervals[("identical", "better")].upper == pytest.approx(0.0)
    assert intervals[("better", "reference")].upper < 0


def test_informativeness_tier_a_and_tier_b_verdict_logic() -> None:
    insufficient = assess_informativeness(99, {"btc": 50, "eth": 49})
    informative = assess_informativeness(
        138,
        {"btc": 38, "eth": 58, "sol": 42, "bnb": 0},
    )
    criteria4 = PairCriteria(
        ci_upper_by_length={30: -0.01, 60: -0.005},
        relative_improvement=0.03,
        improved_chain_count=3,
        informative_chain_count=4,
        lower_brier_first_half=True,
        lower_brier_second_half=True,
    )
    criteria3 = PairCriteria(
        ci_upper_by_length={30: -0.01, 60: -0.005},
        relative_improvement=0.03,
        improved_chain_count=3,
        informative_chain_count=3,
        lower_brier_first_half=True,
        lower_brier_second_half=True,
    )
    criteria3_fail = PairCriteria(
        ci_upper_by_length={30: -0.01, 60: -0.005},
        relative_improvement=0.03,
        improved_chain_count=2,
        informative_chain_count=3,
        lower_brier_first_half=True,
        lower_brier_second_half=True,
    )

    assert not insufficient.informative
    assert informative.informative
    assert len(informative.informative_chains) == 3
    assert assess_pair(criteria4).tier_a
    assert assess_pair(criteria3).tier_a
    assert not assess_pair(criteria3_fail).tier_a
    assert (
        decide_verdict(insufficient, {"M1": True}, 1.0, 0.01).label == "NOT INFORMATIVE"
    )
    assert (
        decide_verdict(
            informative, {"M1": False, "M2": False, "M3": False}, 1.0, 0.01
        ).label
        == "NEGATIVE"
    )
    assert (
        decide_verdict(
            informative, {"M1": False, "M2": True, "M3": False}, None, 0.01
        ).label
        == "TIER A MET"
    )
    assert (
        decide_verdict(
            informative, {"M1": True, "M2": False, "M3": False}, 0.9, 0.04
        ).label
        == "TIER B MET"
    )


def test_vol_state_missing_values_are_a_distinct_category() -> None:
    from app.ml.vol_state import build_vol_state_lookup

    rows = [
        _row(0, (0.0, 0.0, 0.0), -3.0, -2.0),
        _row(1, (0.0, 0.0, 0.0), -3.0, -2.0),
    ]
    lookup = build_vol_state_lookup(
        rows,
        {(rows[0].chain, rows[0].obs_date): "high"},
    )

    assert lookup.distinct_values == ("high",)
    assert lookup.by_row[(rows[0].chain, rows[0].obs_date)] == "high"
    assert lookup.by_row[(rows[1].chain, rows[1].obs_date)] == "missing"
    assert lookup.missing_eligible_rows == 1
