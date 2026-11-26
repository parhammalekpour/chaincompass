from __future__ import annotations

import importlib
import importlib.util
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

from app.ml.dataset import (  # noqa: E402
    ChainInputs,
    build_dataset,
    build_feature_frame,
    build_labels,
    dense_calendar,
    hf7_quantile,
    make_folds,
    q80_window_ends,
)
from app.ml.label_audit import reference_labels  # noqa: E402


def _garch_inputs(length: int, seed: int) -> ChainInputs:
    rng = np.random.default_rng(seed)
    shocks = rng.normal(size=length)
    returns = np.zeros(length, dtype=np.float64)
    variance = np.full(length, 0.00002, dtype=np.float64)
    for index in range(1, length):
        variance[index] = (
            0.000002 + 0.12 * returns[index - 1] ** 2 + 0.85 * variance[index - 1]
        )
        returns[index] = np.sqrt(variance[index]) * shocks[index]
    closes = 100.0 * np.exp(np.cumsum(returns))
    volumes = np.exp(12.0 + rng.normal(0.0, 0.35, size=length))
    first = date(2012, 1, 1)
    dates = tuple(first + timedelta(days=index) for index in range(length))
    return ChainInputs(
        dates=dates,
        closes=tuple(float(value) for value in closes),
        volumes=tuple(float(value) for value in volumes),
    )


@pytest.fixture(scope="module")
def pooled_inputs() -> dict[str, ChainInputs]:
    return {
        "btc": _garch_inputs(2250, 12345),
        "eth": _garch_inputs(1620, 67890),
    }


@pytest.mark.parametrize(
    ("values", "probability"),
    [
        ([2.0, 3.0, 5.0, 11.0], 0.8),
        ([8.0, -2.0, 4.0, 9.0, 3.0, 0.5], 0.2),
        ([1.0, 2.0, 2.0, 2.0, 7.0], 0.5),
    ],
)
def test_hf7_matches_numpy_linear_percentile(
    values: list[float],
    probability: float,
) -> None:
    assert hf7_quantile(values, probability) == pytest.approx(
        float(np.percentile(values, probability * 100, method="linear"))
    )


def test_dense_calendar_preserves_missing_days_as_nan() -> None:
    first = date(2020, 1, 1)
    dense_dates, closes, volumes = dense_calendar(
        [first, first + timedelta(days=2)],
        [10.0, 12.0],
        [100.0, 120.0],
    )
    assert dense_dates == (
        first,
        first + timedelta(days=1),
        first + timedelta(days=2),
    )
    assert np.isnan(closes[1])
    assert np.isnan(volumes[1])
    assert closes[0] == 10.0
    assert closes[2] == 12.0


def test_future_changes_do_not_change_any_feature_through_origin() -> None:
    inputs = _garch_inputs(1900, 1111)
    baseline = build_feature_frame(inputs.dates, inputs.closes, inputs.volumes)
    rng = np.random.default_rng(9988)
    for origin in (900, 1250, 1650):
        changed_closes = list(inputs.closes)
        changed_volumes = list(inputs.volumes)
        for index in range(origin + 1, len(changed_closes)):
            changed_closes[index] = float(rng.uniform(1.0, 100000.0))
            changed_volumes[index] = float(rng.uniform(1.0, 100000.0))
        changed = build_feature_frame(
            inputs.dates,
            changed_closes,
            changed_volumes,
        )
        end = origin + 1
        assert np.array_equal(
            baseline.features[:end],
            changed.features[:end],
            equal_nan=True,
        )
        assert np.array_equal(
            baseline.rv30[:end],
            changed.rv30[:end],
            equal_nan=True,
        )
        assert np.array_equal(
            baseline.q80[:end],
            changed.q80[:end],
            equal_nan=True,
        )


def test_q80_provenance_excludes_future_windows_and_count_matches() -> None:
    rng = np.random.default_rng(412)
    length = 1900
    returns = np.zeros(length, dtype=np.float64)
    returns[1:1050] = rng.normal(0.0, 0.002, size=1049)
    returns[1050:] = rng.normal(0.0, 0.04, size=length - 1050)
    closes = 100.0 * np.exp(np.cumsum(returns))
    volumes = np.exp(rng.normal(12.0, 0.2, size=length))
    first = date(2010, 1, 1)
    dates = tuple(first + timedelta(days=index) for index in range(length))
    frame = build_feature_frame(dates, closes, volumes)

    for origin in (400, 800, 1000, 1500):
        ends = q80_window_ends(frame, origin)
        expected = tuple(
            index for index in range(origin + 1) if np.isfinite(frame.rv30[index])
        )
        assert ends == expected
        assert all(end <= origin for end in ends)
        assert len(ends) == int(np.count_nonzero(np.isfinite(frame.rv30[: origin + 1])))

    origin = 1000
    future_ends = tuple(
        index for index in range(origin + 301) if np.isfinite(frame.rv30[index])
    )
    wrong_q80 = hf7_quantile(
        [float(frame.rv30[index]) for index in future_ends],
        0.8,
    )
    assert np.isfinite(frame.q80[origin])
    assert not np.isclose(frame.q80[origin], wrong_q80)


def test_missing_close_invalidates_windows_without_filling() -> None:
    inputs = _garch_inputs(1700, 7766)
    missing_index = 1100
    closes = list(inputs.closes)
    closes[missing_index] = None
    frame = build_feature_frame(inputs.dates, closes, inputs.volumes)

    assert np.isnan(frame.closes[missing_index])
    assert np.isnan(frame.rv30[missing_index : missing_index + 31]).all()
    assert np.isfinite(frame.rv30[missing_index - 1])
    assert np.isfinite(frame.rv30[missing_index + 31])
    labels = build_labels(frame, inputs.dates[-1])
    assert np.isnan(labels.rv30_fwd[missing_index - 30 : missing_index + 1]).all()


def test_dataset_eligibility_hash_and_walk_forward_purge(
    pooled_inputs: dict[str, ChainInputs],
) -> None:
    cutoff = pooled_inputs["btc"].dates[-1]
    first = build_dataset(pooled_inputs, cutoff)
    second = build_dataset(pooled_inputs, cutoff)
    assert first.sha256 == second.sha256
    assert first.rows
    assert all(len(row.features) == 16 for row in first.rows)
    assert all(
        np.isfinite(row.features).all()
        and row.rv7 > 0
        and row.rv30 > 0
        and row.q80 > 0
        and row.rv30_fwd >= 0
        for row in first.rows
    )

    changed_btc = list(pooled_inputs["btc"].closes)
    changed_btc[1300] = float(changed_btc[1300]) * 1.03
    changed_inputs = dict(pooled_inputs)
    changed_inputs["btc"] = ChainInputs(
        dates=pooled_inputs["btc"].dates,
        closes=tuple(changed_btc),
        volumes=pooled_inputs["btc"].volumes,
    )
    changed = build_dataset(changed_inputs, cutoff)
    assert changed.sha256 != first.sha256

    folds = make_folds(first.rows)
    assert len(folds) >= 2
    test_indices: list[int] = []
    previous_end: date | None = None
    for fold in folds:
        assert fold.train_indices
        assert fold.test_indices
        assert set(fold.train_indices).isdisjoint(fold.test_indices)
        assert all(
            first.rows[index].obs_date + timedelta(days=30) < fold.test_start
            for index in fold.train_indices
        )
        assert all(
            fold.test_start <= first.rows[index].obs_date < fold.test_end_exclusive
            for index in fold.test_indices
        )
        if previous_end is not None:
            assert fold.test_start == previous_end
        previous_end = fold.test_end_exclusive
        test_indices.extend(fold.test_indices)
    assert len(test_indices) == len(set(test_indices))
    assert all(index < len(first.rows) for index in test_indices)
    assert all(
        (fold.test_end_exclusive - fold.test_start).days == 90 for fold in folds[:-1]
    )
    assert 0 < (folds[-1].test_end_exclusive - folds[-1].test_start).days <= 90
    assert all(first.rows[index].chain == "btc" for index in folds[-1].test_indices)


def test_label_cutoff_requires_mature_forward_window() -> None:
    inputs = _garch_inputs(1100, 9876)
    frame = build_feature_frame(inputs.dates, inputs.closes, inputs.volumes)
    cutoff = inputs.dates[-1] - timedelta(days=10)
    labels = build_labels(frame, cutoff)
    assert np.all(labels.labels[-10:] == -1)
    assert np.all(np.isnan(labels.rv30_fwd[-10:]))


def test_independent_reference_matches_production_labels_and_volatility() -> None:
    inputs = _garch_inputs(2250, 5050)
    cutoff = inputs.dates[-1]
    dataset = build_dataset({"btc": inputs}, cutoff)
    reference = reference_labels(inputs.dates, inputs.closes, cutoff)

    assert dataset.rows
    for row in dataset.rows:
        expected = reference[row.obs_date]
        assert row.y == expected.y
        for observed, computed in (
            (row.rv30, expected.rv30),
            (row.rv30_fwd, expected.rv30_fwd),
            (row.q80, expected.q80),
        ):
            assert abs(observed - computed) <= 1e-9 * max(
                abs(observed),
                abs(computed),
            )
