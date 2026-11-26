from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.ml.dataset import DatasetRow

BASELINE_NAMES = ("B0", "B1", "B2", "B3")
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class HarFit:
    coefficients: tuple[float, float, float, float]
    sigma: float


def laplace_probability(labels: Sequence[int]) -> float:
    if not labels:
        raise ValueError("Laplace smoothing requires at least one training label")
    return (sum(labels) + 1) / (len(labels) + 2)


def conditional_probabilities(
    train_categories: Sequence[str | bool],
    train_labels: Sequence[int],
    test_categories: Sequence[str | bool],
    overall_rate: float,
) -> FloatArray:
    counts: dict[str | bool, list[int]] = {}
    for category, label in zip(train_categories, train_labels, strict=True):
        current = counts.setdefault(category, [0, 0])
        current[0] += 1
        current[1] += label
    result = []
    for category in test_categories:
        cell = counts.get(category)
        if cell is None:
            result.append(overall_rate)
        else:
            count, positives = cell
            result.append((positives + 1) / (count + 2))
    return np.asarray(result, dtype=np.float64)


def fit_har(train_rows: Sequence[DatasetRow]) -> HarFit:
    if len(train_rows) <= 4:
        raise ValueError("B3 requires more than four training rows")
    design = np.asarray(
        [
            [
                1.0,
                math.log(row.rv7),
                math.log(row.rv30),
                math.log(row.features[1]),
            ]
            for row in train_rows
        ],
        dtype=np.float64,
    )
    targets = np.asarray(
        [math.log(row.rv30_fwd) for row in train_rows],
        dtype=np.float64,
    )
    coefficients, _, _, _ = np.linalg.lstsq(design, targets, rcond=None)
    residuals = targets - design @ coefficients
    sigma = math.sqrt(float(np.dot(residuals, residuals)) / (len(train_rows) - 4))
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("B3 residual standard deviation must be positive")
    return HarFit(
        coefficients=(
            float(coefficients[0]),
            float(coefficients[1]),
            float(coefficients[2]),
            float(coefficients[3]),
        ),
        sigma=sigma,
    )


def predict_har(
    fit: HarFit,
    test_rows: Sequence[DatasetRow],
) -> FloatArray:
    test_design = np.asarray(
        [
            [
                1.0,
                math.log(row.rv7),
                math.log(row.rv30),
                math.log(row.features[1]),
            ]
            for row in test_rows
        ],
        dtype=np.float64,
    )
    predictions = test_design @ np.asarray(fit.coefficients, dtype=np.float64)
    result = []
    for row, prediction in zip(test_rows, predictions, strict=True):
        z = (math.log(row.q80) - float(prediction)) / (fit.sigma * math.sqrt(2.0))
        cdf = 0.5 * (1.0 + math.erf(z))
        result.append(1.0 - cdf)
    return np.asarray(result, dtype=np.float64)


def predict_baselines(
    train_rows: Sequence[DatasetRow],
    test_rows: Sequence[DatasetRow],
    train_vol_states: Sequence[str],
    test_vol_states: Sequence[str],
) -> dict[str, FloatArray]:
    if not train_rows or not test_rows:
        raise ValueError("baseline prediction requires non-empty train and test rows")
    if len(train_rows) != len(train_vol_states) or len(test_rows) != len(
        test_vol_states
    ):
        raise ValueError("vol_state arrays must align with their dataset rows")

    train_labels = [row.y for row in train_rows]
    overall_rate = laplace_probability(train_labels)
    b1_train = [row.rv30 > row.q80 for row in train_rows]
    b1_test = [row.rv30 > row.q80 for row in test_rows]

    har_fit = fit_har(train_rows)
    return {
        "B0": np.full(len(test_rows), overall_rate, dtype=np.float64),
        "B1": conditional_probabilities(
            b1_train,
            train_labels,
            b1_test,
            overall_rate,
        ),
        "B2": conditional_probabilities(
            train_vol_states,
            train_labels,
            test_vol_states,
            overall_rate,
        ),
        "B3": predict_har(har_fit, test_rows),
    }
