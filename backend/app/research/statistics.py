"""Statistical calculations convert Decimal values to floats at this boundary."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.analytics.scenarios import type7_quantile

WILSON_Z_95 = 1.959963984540054


def wilson_interval(
    successes: int, n: int, z: float = WILSON_Z_95
) -> tuple[float, float]:
    if n <= 0 or successes < 0 or successes > n:
        raise ValueError("Wilson interval requires 0 <= successes <= n and n > 0")
    proportion = successes / n
    z_squared = z * z
    denominator = 1.0 + z_squared / n
    center = (proportion + z_squared / (2.0 * n)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / n + z_squared / (4.0 * n * n))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def proportion_summary(
    successes: int, n: int
) -> dict[str, int | float | list[float] | None]:
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("proportion counts must satisfy 0 <= successes <= n")
    interval = wilson_interval(successes, n) if n else None
    return {
        "successes": successes,
        "n": n,
        "share": successes / n if n else None,
        "wilson_95": list(interval) if interval is not None else None,
    }


def pinball_loss(quantile: float, realized: float, forecast: float) -> float:
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be strictly between zero and one")
    residual = realized - forecast
    return max(quantile * residual, (quantile - 1.0) * residual)


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for index in range(start, end):
            ranks[ordered[index][0]] = average_rank
        start = end
    return ranks


def spearman_correlation(
    x_values: Sequence[float], y_values: Sequence[float]
) -> float | None:
    if len(x_values) != len(y_values):
        raise ValueError("Spearman inputs must have equal lengths")
    if len(x_values) < 2:
        return None
    x_ranks = _average_ranks(x_values)
    y_ranks = _average_ranks(y_values)
    x_mean = sum(x_ranks) / len(x_ranks)
    y_mean = sum(y_ranks) / len(y_ranks)
    covariance = sum(
        (x_rank - x_mean) * (y_rank - y_mean)
        for x_rank, y_rank in zip(x_ranks, y_ranks, strict=True)
    )
    x_variance = sum((value - x_mean) ** 2 for value in x_ranks)
    y_variance = sum((value - y_mean) ** 2 for value in y_ranks)
    if x_variance == 0.0 or y_variance == 0.0:
        return None
    return max(-1.0, min(1.0, covariance / math.sqrt(x_variance * y_variance)))


def fisher_spearman_interval(
    rho: float, n_independent: int
) -> tuple[float, float] | None:
    if n_independent <= 3 or not -1.0 < rho < 1.0:
        return None
    transformed = math.atanh(rho)
    margin = WILSON_Z_95 / math.sqrt(n_independent - 3)
    return math.tanh(transformed - margin), math.tanh(transformed + margin)


def expanding_past_terciles(
    dated_scores: Sequence[tuple[date, Decimal]],
    minimum_history: int = 30,
) -> dict[date, str | None]:
    ordered = sorted(dated_scores, key=lambda item: item[0])
    prior: list[Decimal] = []
    result: dict[date, str | None] = {}
    for score_date, score in ordered:
        if len(prior) < minimum_history:
            result[score_date] = None
        else:
            lower = type7_quantile(prior, Decimal(1) / Decimal(3))
            upper = type7_quantile(prior, Decimal(2) / Decimal(3))
            result[score_date] = (
                "low" if score <= lower else "middle" if score <= upper else "high"
            )
        prior.append(score)
    return result
