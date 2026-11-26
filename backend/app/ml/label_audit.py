from __future__ import annotations

import math
from bisect import insort
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ReferenceLabel:
    rv30: float
    rv30_fwd: float
    q80: float
    y: int


def _manual_realized_volatility(
    closes: Sequence[float],
    start: int,
    end: int,
) -> float | None:
    if start < 0 or end >= len(closes):
        return None
    returns: list[float] = []
    for index in range(start + 1, end + 1):
        previous = closes[index - 1]
        current = closes[index]
        if (
            not math.isfinite(previous)
            or not math.isfinite(current)
            or previous <= 0
            or current <= 0
        ):
            return None
        returns.append(math.log(current) - math.log(previous))
    if len(returns) < 2:
        return None
    mean = math.fsum(returns) / len(returns)
    sum_squared_deviations = math.fsum((value - mean) ** 2 for value in returns)
    sample_std = math.sqrt(sum_squared_deviations / (len(returns) - 1))
    return sample_std * math.sqrt(365.0)


def _type7_eightieth_percentile(sorted_values: Sequence[float]) -> float:
    position = 0.8 * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )


def reference_labels(
    dates: Sequence[date],
    closes: Sequence[float | None],
    cutoff: date,
) -> dict[date, ReferenceLabel]:
    if len(dates) != len(closes):
        raise ValueError("dates and closes must have equal lengths")

    observations: dict[date, float | None] = {}
    for obs_date, close in zip(dates, closes, strict=True):
        if obs_date > cutoff:
            continue
        if obs_date in observations:
            raise ValueError(f"duplicate observation date: {obs_date.isoformat()}")
        observations[obs_date] = close
    if not observations:
        return {}

    first_date = min(observations)
    last_date = max(observations)
    calendar: list[date] = []
    dense_closes: list[float] = []
    cursor = first_date
    while cursor <= last_date:
        close = observations.get(cursor)
        calendar.append(cursor)
        dense_closes.append(float(close) if close is not None else math.nan)
        cursor += timedelta(days=1)

    sorted_rv30: list[float] = []
    reference: dict[date, ReferenceLabel] = {}
    for index, obs_date in enumerate(calendar):
        rv30 = _manual_realized_volatility(dense_closes, index - 30, index)
        if rv30 is not None:
            insort(sorted_rv30, rv30)
        if len(sorted_rv30) < 365 or obs_date + timedelta(days=30) > cutoff:
            continue

        q80 = _type7_eightieth_percentile(sorted_rv30)
        rv30_fwd = _manual_realized_volatility(
            dense_closes,
            index,
            index + 30,
        )
        if rv30_fwd is None:
            continue
        reference[obs_date] = ReferenceLabel(
            rv30=rv30 if rv30 is not None else math.nan,
            rv30_fwd=rv30_fwd,
            q80=q80,
            y=int(rv30_fwd > q80),
        )
    return reference
