from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int8]
type ReliabilityBin = dict[str, float | int | None]


@dataclass(frozen=True)
class MetricSummary:
    count: int
    positive_count: int
    brier: float
    log_loss: float
    auc: float | None
    ece: float
    calibration_slope: float | None
    calibration_intercept: float | None
    calibration_status: str
    calibration_convergence_warnings: int
    reliability: tuple[ReliabilityBin, ...]


def _calibration(
    labels: IntArray,
    probabilities: FloatArray,
) -> tuple[float | None, float | None, str, int]:
    clipped = np.clip(probabilities, 1e-6, 1.0 - 1e-6)
    if np.all(clipped == clipped[0]):
        return None, None, "undefined: constant probability", 0
    if np.unique(labels).size < 2:
        return None, None, "undefined: single label class", 0
    logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    model = LogisticRegression(penalty=None, max_iter=1000)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        try:
            model.fit(logits, labels)
        except (ValueError, np.linalg.LinAlgError):
            return None, None, "undefined: fit failed", 0
    warning_count = sum(
        issubclass(item.category, ConvergenceWarning) for item in caught
    )
    return (
        float(model.coef_[0, 0]),
        float(model.intercept_[0]),
        "defined",
        warning_count,
    )


def compute_metrics(labels: IntArray, probabilities: FloatArray) -> MetricSummary:
    y = np.asarray(labels, dtype=np.int8)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or len(y) == 0:
        raise ValueError("metrics require equal non-empty one-dimensional arrays")
    if not np.all(np.isfinite(p)) or np.any(p < 0) or np.any(p > 1):
        raise ValueError("probabilities must be finite values in [0, 1]")

    clipped = np.clip(p, 1e-6, 1.0 - 1e-6)
    reliability: list[ReliabilityBin] = []
    ordered = np.argsort(p, kind="stable")
    bins = np.array_split(ordered, 10)
    ece = 0.0
    for bin_index, indices in enumerate(bins):
        if len(indices) == 0:
            reliability.append(
                {
                    "bin": bin_index + 1,
                    "count": 0,
                    "mean_probability": None,
                    "observed_rate": None,
                    "absolute_gap": None,
                }
            )
            continue
        mean_probability = float(np.mean(p[indices]))
        observed_rate = float(np.mean(y[indices]))
        absolute_gap = abs(mean_probability - observed_rate)
        ece += len(indices) / len(y) * absolute_gap
        reliability.append(
            {
                "bin": bin_index + 1,
                "count": len(indices),
                "mean_probability": mean_probability,
                "observed_rate": observed_rate,
                "absolute_gap": absolute_gap,
            }
        )

    auc = float(roc_auc_score(y, p)) if np.unique(y).size == 2 else None
    slope, intercept, calibration_status, calibration_warnings = _calibration(
        y,
        p,
    )
    return MetricSummary(
        count=len(y),
        positive_count=int(np.sum(y)),
        brier=float(np.mean((p - y) ** 2)),
        log_loss=float(log_loss(y, clipped, labels=[0, 1])),
        auc=auc,
        ece=float(ece),
        calibration_slope=slope,
        calibration_intercept=intercept,
        calibration_status=calibration_status,
        calibration_convergence_warnings=calibration_warnings,
        reliability=tuple(reliability),
    )


def macro_average(summaries: tuple[MetricSummary, ...]) -> MetricSummary:
    if not summaries:
        raise ValueError("macro average requires at least one chain summary")

    def average(values: list[float | None]) -> float | None:
        defined = [value for value in values if value is not None]
        return float(np.mean(defined)) if defined else None

    return MetricSummary(
        count=sum(summary.count for summary in summaries),
        positive_count=sum(summary.positive_count for summary in summaries),
        brier=float(np.mean([summary.brier for summary in summaries])),
        log_loss=float(np.mean([summary.log_loss for summary in summaries])),
        auc=average([summary.auc for summary in summaries]),
        ece=float(np.mean([summary.ece for summary in summaries])),
        calibration_slope=average([summary.calibration_slope for summary in summaries]),
        calibration_intercept=average(
            [summary.calibration_intercept for summary in summaries]
        ),
        calibration_status="macro average over informative chains",
        calibration_convergence_warnings=sum(
            summary.calibration_convergence_warnings for summary in summaries
        ),
        reliability=(),
    )
