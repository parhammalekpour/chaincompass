from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.dataset import Dataset, Fold


@dataclass(frozen=True)
class LeakageResults:
    permutation_aucs: tuple[float, ...]
    canary_auc: float

    @property
    def permutation_mean(self) -> float:
        return float(np.mean(self.permutation_aucs))

    @property
    def permutation_minimum(self) -> float:
        return min(self.permutation_aucs)

    @property
    def permutation_maximum(self) -> float:
        return max(self.permutation_aucs)


def _m1() -> Any:
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(
            penalty="l2",
            C=1.0,
            max_iter=1000,
            random_state=12345,
        ),
    )


def _pooled_test_predictions(
    features: NDArray[np.float64],
    labels: NDArray[np.int8],
    folds: tuple[Fold, ...],
) -> tuple[NDArray[np.int8], NDArray[np.float64]]:
    test_labels: list[int] = []
    test_probabilities: list[float] = []
    for fold in folds:
        train_indices = np.asarray(fold.train_indices, dtype=np.intp)
        test_indices = np.asarray(fold.test_indices, dtype=np.intp)
        train_labels = labels[train_indices]
        if np.unique(train_labels).size != 2:
            raise RuntimeError(
                f"fold {fold.index} training labels do not contain both classes"
            )
        model = _m1()
        model.fit(features[train_indices], train_labels)
        probabilities = model.predict_proba(features[test_indices])[:, 1]
        test_labels.extend(int(value) for value in labels[test_indices])
        test_probabilities.extend(float(value) for value in probabilities)
    if not test_labels:
        raise RuntimeError("walk-forward folds contain no test rows")
    return (
        np.asarray(test_labels, dtype=np.int8),
        np.asarray(test_probabilities, dtype=np.float64),
    )


def run_leakage_checks(
    dataset: Dataset,
    folds: tuple[Fold, ...],
    *,
    permutation_seeds: tuple[int, ...] = tuple(range(12345, 12365)),
) -> LeakageResults:
    if not folds:
        raise RuntimeError("walk-forward folds are required for leakage checks")
    rows = dataset.rows
    features = np.asarray([row.features for row in rows], dtype=np.float64)
    labels = np.asarray([row.y for row in rows], dtype=np.int8)
    permutation_aucs: list[float] = []

    for seed in permutation_seeds:
        shuffled_labels = np.random.default_rng(seed).permutation(labels)
        test_labels, test_probabilities = _pooled_test_predictions(
            features,
            shuffled_labels,
            folds,
        )
        if np.unique(test_labels).size != 2:
            raise RuntimeError(
                "permuted pooled test labels do not contain both classes"
            )
        permutation_aucs.append(float(roc_auc_score(test_labels, test_probabilities)))

    canary_values = np.asarray(
        [[math.log(row.rv30_fwd / row.q80)] for row in rows],
        dtype=np.float64,
    )
    true_labels, canary_probabilities = _pooled_test_predictions(
        canary_values,
        labels,
        folds,
    )
    if np.unique(true_labels).size != 2:
        raise RuntimeError("pooled canary test labels do not contain both classes")
    canary_auc = float(roc_auc_score(true_labels, canary_probabilities))
    return LeakageResults(
        permutation_aucs=tuple(permutation_aucs),
        canary_auc=canary_auc,
    )


def passed_permutation_check(results: LeakageResults) -> bool:
    return 0.45 <= results.permutation_mean <= 0.55


def passed_canary_check(results: LeakageResults) -> bool:
    return results.canary_auc >= 0.99
