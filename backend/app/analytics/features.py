from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

from app.analytics.registry import FeatureInput, FeatureRole, get_feature_input

logger = logging.getLogger(__name__)
FEATURE_QUANTUM = Decimal("0.000000000001")
DECIMAL_PRECISION = 50
EFFECTIVE_NONZERO_RUN_DAYS = 30
_LOGGED_EXCLUSIONS: set[tuple[str, str, str]] = set()


@dataclass(frozen=True)
class FeaturePoint:
    obs_date: date
    value: Decimal


@dataclass(frozen=True)
class FeatureValue:
    chain: str
    feature: str
    as_of_date: date
    value: Decimal
    n_obs: int
    window_days: int
    source_metric: str
    source: str
    role: FeatureRole


def _feature_prefix(spec: FeatureInput) -> str:
    if spec.source == "coingecko" and spec.metric == "market_cap_usd":
        return "coingecko_market_cap_usd"
    return spec.metric


def _date_at_offset(as_of: date, offset: int) -> date:
    return as_of - timedelta(days=offset)


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _required_coverage(days: int) -> int:
    return (days * 9 + 9) // 10


def _rounded(value: Decimal) -> Decimal:
    try:
        rounded = value.quantize(FEATURE_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError(
            "feature value cannot be represented at 12 decimal places"
        ) from exc
    if rounded != 0 and rounded.adjusted() > 25:
        raise ValueError("feature value exceeds NUMERIC(38,12)")
    return rounded


def _make_value(
    spec: FeatureInput,
    feature: str,
    as_of: date,
    value: Decimal,
    n_obs: int,
    window_days: int,
) -> FeatureValue:
    return FeatureValue(
        chain=spec.chain,
        feature=feature,
        as_of_date=as_of,
        value=_rounded(value),
        n_obs=n_obs,
        window_days=window_days,
        source_metric=spec.metric,
        source=spec.source,
        role=spec.role,
    )


def find_effective_start(points: Sequence[FeaturePoint]) -> date | None:
    """Return the first day of a completed 30-day non-zero run."""
    ordered = sorted(points, key=lambda point: point.obs_date)
    run_start: date | None = None
    run_length = 0
    previous_date: date | None = None
    for point in ordered:
        if point.value == 0:
            run_start = None
            run_length = 0
        elif (
            previous_date is None
            or point.obs_date != previous_date + timedelta(days=1)
            or run_length == 0
        ):
            run_start = point.obs_date
            run_length = 1
        else:
            run_length += 1
        if run_length >= EFFECTIVE_NONZERO_RUN_DAYS:
            return run_start
        previous_date = point.obs_date
    return None


def _log_exclusion_once(
    spec: FeatureInput,
    points: Sequence[FeaturePoint],
    effective_start: date | None,
) -> None:
    key = (spec.chain, spec.metric, spec.source)
    if key in _LOGGED_EXCLUSIONS or effective_start is None:
        return
    first_date = min(point.obs_date for point in points)
    if first_date >= effective_start:
        return
    excluded = sum(point.obs_date < effective_start for point in points)
    logger.info(
        "feature_leading_data_excluded chain=%s metric=%s source=%s "
        "effective_start=%s excluded_observations=%s",
        spec.chain,
        spec.metric,
        spec.source,
        effective_start.isoformat(),
        excluded,
    )
    _LOGGED_EXCLUSIONS.add(key)


def _input_window(
    values: dict[date, Decimal],
    as_of: date,
    days: int,
) -> tuple[list[Decimal], list[date]]:
    dates = [_date_at_offset(as_of, offset) for offset in range(days)]
    present_dates = [day for day in dates if day in values]
    return [values[day] for day in present_dates], present_dates


def _median_window(
    values: dict[date, Decimal],
    as_of: date,
    effective_start: date,
) -> tuple[Decimal, list[date]] | None:
    start = as_of - timedelta(days=29)
    if start < effective_start:
        return None
    window_values, present_dates = _input_window(values, as_of, 30)
    if len(present_dates) < 24:
        return None
    return _median(window_values), present_dates


def _append_price_features(
    output: list[FeatureValue],
    spec: FeatureInput,
    values: dict[date, Decimal],
    log_returns: dict[date, Decimal],
    as_of: date,
    effective_start: date,
) -> None:
    current = values.get(as_of)

    for days in (7, 30, 90, 365):
        start = as_of - timedelta(days=days)
        if start < effective_start:
            continue
        prior = values.get(start)
        if current is None or prior is None or current <= 0 or prior <= 0:
            continue
        output.append(
            _make_value(
                spec,
                f"ret_{days}d",
                as_of,
                current / prior - Decimal(1),
                2,
                days,
            )
        )

    for days in (30, 90):
        start = as_of - timedelta(days=days)
        if start < effective_start:
            continue
        return_dates = [
            _date_at_offset(as_of, offset)
            for offset in range(days - 1, -1, -1)
            if _date_at_offset(as_of, offset) in log_returns
        ]
        if len(return_dates) < _required_coverage(days):
            continue
        returns = [log_returns[day] for day in return_dates]
        mean = sum(returns, Decimal(0)) / Decimal(len(returns))
        variance = sum(
            ((value - mean) ** 2 for value in returns), Decimal(0)
        ) / Decimal(len(returns) - 1)
        annualized = variance.sqrt() * Decimal(365).sqrt()
        used_dates = {day - timedelta(days=1) for day in return_dates} | set(
            return_dates
        )
        output.append(
            _make_value(
                spec,
                f"realized_vol_{days}d",
                as_of,
                annualized,
                len(used_dates),
                days,
            )
        )

    drawdown_start = as_of - timedelta(days=364)
    if drawdown_start >= effective_start and current is not None and current > 0:
        window_values, present_dates = _input_window(values, as_of, 365)
        if len(present_dates) >= _required_coverage(365):
            peak = max(window_values)
            if peak > 0:
                output.append(
                    _make_value(
                        spec,
                        "drawdown_365d",
                        as_of,
                        current / peak - Decimal(1),
                        len(present_dates),
                        365,
                    )
                )

    sma_start = as_of - timedelta(days=199)
    if sma_start >= effective_start and current is not None and current > 0:
        window_values, present_dates = _input_window(values, as_of, 200)
        if len(present_dates) >= _required_coverage(200):
            mean = sum(window_values, Decimal(0)) / Decimal(len(window_values))
            if mean > 0:
                output.append(
                    _make_value(
                        spec,
                        "price_vs_sma200",
                        as_of,
                        current / mean - Decimal(1),
                        len(present_dates),
                        200,
                    )
                )


def _append_volume_features(
    output: list[FeatureValue],
    spec: FeatureInput,
    values: dict[date, Decimal],
    as_of: date,
    effective_start: date,
) -> None:
    window_30 = _median_window(values, as_of, effective_start)
    if window_30 is not None:
        median_30, dates_30 = window_30
        output.append(
            _make_value(spec, "volume_med30", as_of, median_30, len(dates_30), 30)
        )
    else:
        return

    start_365 = as_of - timedelta(days=364)
    if start_365 < effective_start:
        return
    values_365, dates_365 = _input_window(values, as_of, 365)
    if len(dates_365) < _required_coverage(365):
        return
    median_365 = _median(values_365)
    if median_365 <= 0:
        return
    output.append(
        _make_value(
            spec,
            "volume_ratio_30_365",
            as_of,
            median_30 / median_365,
            len(dates_365),
            365,
        )
    )


def _append_level_features(
    output: list[FeatureValue],
    spec: FeatureInput,
    values: dict[date, Decimal],
    as_of: date,
    effective_start: date,
) -> None:
    prefix = _feature_prefix(spec)
    current_window = _median_window(values, as_of, effective_start)
    if current_window is None:
        return
    current_median, current_dates = current_window
    output.append(
        _make_value(
            spec,
            f"{prefix}_med30",
            as_of,
            current_median,
            len(current_dates),
            30,
        )
    )

    for days in (30, 90):
        prior_date = as_of - timedelta(days=days)
        prior_window = _median_window(values, prior_date, effective_start)
        if prior_window is None:
            continue
        prior_median, prior_dates = prior_window
        if prior_median <= 0:
            continue
        all_dates = set(current_dates) | set(prior_dates)
        output.append(
            _make_value(
                spec,
                f"{prefix}_chg{days}",
                as_of,
                current_median / prior_median - Decimal(1),
                len(all_dates),
                30 + days,
            )
        )


def compute_series_features(
    chain: str,
    metric: str,
    source: str,
    points: Sequence[FeaturePoint],
    *,
    as_of_dates: Iterable[date] | None = None,
) -> list[FeatureValue]:
    """Compute daily features using only points dated on or before each as-of day."""
    spec = get_feature_input(chain, metric, source)
    if spec is None:
        raise ValueError(f"unregistered feature input: {chain}/{metric}/{source}")
    if not points:
        return []

    ordered = sorted(points, key=lambda point: point.obs_date)
    values: dict[date, Decimal] = {}
    for point in ordered:
        if not isinstance(point.value, Decimal):
            raise TypeError("feature inputs must be Decimal values")
        if not point.value.is_finite():
            raise ValueError("feature inputs must be finite")
        if point.obs_date in values:
            raise ValueError(f"duplicate input date: {point.obs_date.isoformat()}")
        values[point.obs_date] = point.value

    effective_start = find_effective_start(ordered)
    _log_exclusion_once(spec, ordered, effective_start)
    selected_dates = set(as_of_dates) if as_of_dates is not None else None
    first_date = ordered[0].obs_date
    last_date = ordered[-1].obs_date

    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        log_returns: dict[date, Decimal] = {}
        for day in sorted(values):
            previous = values.get(day - timedelta(days=1))
            current = values[day]
            if previous is not None and previous > 0 and current > 0:
                log_returns[day] = (current / previous).ln()

        output: list[FeatureValue] = []
        run_start: date | None = None
        run_last: date | None = None
        run_length = 0
        cursor = first_date
        point_in_time_effective_start: date | None = None
        while cursor <= last_date:
            value = values.get(cursor)
            if value is not None and value != 0:
                if run_last == cursor - timedelta(days=1):
                    run_length += 1
                else:
                    run_start = cursor
                    run_length = 1
                run_last = cursor
                if (
                    point_in_time_effective_start is None
                    and run_length >= EFFECTIVE_NONZERO_RUN_DAYS
                    and run_start is not None
                ):
                    point_in_time_effective_start = run_start
            else:
                run_start = None
                run_last = None
                run_length = 0

            effective = point_in_time_effective_start
            should_compute = selected_dates is None or cursor in selected_dates
            if effective is not None and should_compute:
                if metric == "price_close_usd":
                    _append_price_features(
                        output,
                        spec,
                        values,
                        log_returns,
                        cursor,
                        effective,
                    )
                elif metric == "volume_usd":
                    _append_volume_features(output, spec, values, cursor, effective)
                else:
                    _append_level_features(output, spec, values, cursor, effective)
            cursor += timedelta(days=1)

    output.sort(key=lambda item: (item.as_of_date, item.feature))
    return output
