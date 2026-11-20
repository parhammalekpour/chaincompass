from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from app.analytics.scenarios_config import (
    HORIZONS_DAYS,
    LOW_SAMPLE_INDEPENDENT_WINDOWS,
    METHOD_NOTE,
    MIN_INDEPENDENT_WINDOWS,
    QUANTILES,
    RETURN_QUANTUM,
    SHARE_QUANTUM,
    VERSION,
    QuantileName,
    ScenarioName,
)

PricePoint = tuple[date, Decimal]


@dataclass(frozen=True)
class BasePrice:
    close_usd: Decimal
    date: date


@dataclass(frozen=True)
class ScenarioValue:
    name: ScenarioName
    quantile: QuantileName
    return_value: Decimal
    illustrative_price_usd: Decimal


@dataclass(frozen=True)
class HorizonScenarios:
    days: int
    available: bool
    reason: str | None
    low_sample: bool
    n_windows: int
    n_independent: int
    first_window_start: date | None
    last_window_end: date | None
    share_negative: Decimal | None
    scenarios: tuple[ScenarioValue, ...]


@dataclass(frozen=True)
class ScenarioAnalysis:
    version: str
    not_a_forecast: Literal[True]
    method_note: str
    as_of_date: date
    base_price: BasePrice
    horizons: tuple[HorizonScenarios, ...]


def type7_quantile(values: Sequence[Decimal], probability: Decimal) -> Decimal:
    if not values:
        raise ValueError("quantiles require at least one value")
    if not Decimal("0") <= probability <= Decimal("1"):
        raise ValueError("quantile probability must be between zero and one")
    if any(not value.is_finite() for value in values):
        raise ValueError("quantile values must be finite")

    ordered = sorted(values)
    with localcontext() as context:
        context.prec = 50
        position = Decimal(len(ordered) - 1) * probability
        lower_index = int(position)
        upper_index = min(lower_index + 1, len(ordered) - 1)
        fraction = position - Decimal(lower_index)
        return ordered[lower_index] + fraction * (
            ordered[upper_index] - ordered[lower_index]
        )


def window_returns(
    prices: Sequence[PricePoint],
    as_of_date: date,
    horizon_days: int,
) -> tuple[tuple[date, date, Decimal], ...]:
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    closes = {price_date: close for price_date, close in prices}
    windows: list[tuple[date, date, Decimal]] = []
    with localcontext() as context:
        context.prec = 50
        for start_date, start_close in prices:
            try:
                end_date = start_date + timedelta(days=horizon_days)
            except OverflowError:
                continue
            if end_date > as_of_date:
                continue
            end_close = closes.get(end_date)
            if end_close is None:
                continue
            realized_return = (end_close / start_close - Decimal("1")).quantize(
                RETURN_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            )
            windows.append((start_date, end_date, realized_return))
    return tuple(windows)


def share_negative(returns: Sequence[Decimal]) -> Decimal:
    if not returns:
        raise ValueError("share_negative requires at least one return")
    negative_count = sum(value < 0 for value in returns)
    with localcontext() as context:
        context.prec = 50
        return (Decimal(negative_count) / Decimal(len(returns))).quantize(
            SHARE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def _horizon_scenarios(
    prices: Sequence[PricePoint],
    as_of_date: date,
    base_close: Decimal,
    horizon_days: int,
) -> HorizonScenarios:
    windows = window_returns(prices, as_of_date, horizon_days)
    returns = [window[2] for window in windows]
    n_windows = len(windows)
    n_independent = n_windows // horizon_days
    first_window_start = windows[0][0] if windows else None
    last_window_end = windows[-1][1] if windows else None

    if n_independent < MIN_INDEPENDENT_WINDOWS:
        return HorizonScenarios(
            days=horizon_days,
            available=False,
            reason="insufficient_history",
            low_sample=False,
            n_windows=n_windows,
            n_independent=n_independent,
            first_window_start=first_window_start,
            last_window_end=last_window_end,
            share_negative=None,
            scenarios=(),
        )

    return_quantiles = [
        type7_quantile(returns, spec.probability).quantize(
            RETURN_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
        for spec in QUANTILES
    ]
    scenario_values: list[ScenarioValue] = []
    with localcontext() as context:
        context.prec = 50
        for spec, realized_return in zip(
            QUANTILES,
            return_quantiles,
            strict=True,
        ):
            scenario_values.append(
                ScenarioValue(
                    name=spec.name,
                    quantile=spec.label,
                    return_value=realized_return,
                    illustrative_price_usd=base_close
                    * (Decimal("1") + realized_return),
                )
            )
    return HorizonScenarios(
        days=horizon_days,
        available=True,
        reason=None,
        low_sample=n_independent < LOW_SAMPLE_INDEPENDENT_WINDOWS,
        n_windows=n_windows,
        n_independent=n_independent,
        first_window_start=first_window_start,
        last_window_end=last_window_end,
        share_negative=share_negative(returns),
        scenarios=tuple(scenario_values),
    )


def calculate_scenarios(
    prices: Sequence[PricePoint],
    as_of_date: date,
) -> ScenarioAnalysis:
    historical_prices = sorted(
        (price_date, close) for price_date, close in prices if price_date <= as_of_date
    )
    if not historical_prices:
        raise ValueError("a price close on or before as_of_date is required")

    previous_date: date | None = None
    for price_date, close in historical_prices:
        if not isinstance(close, Decimal):
            raise TypeError("price closes must be Decimal values")
        if not close.is_finite() or close <= 0:
            raise ValueError("price closes must be finite and positive")
        if price_date == previous_date:
            raise ValueError(f"duplicate price date: {price_date}")
        previous_date = price_date

    base_date, base_close = historical_prices[-1]
    return ScenarioAnalysis(
        version=VERSION,
        not_a_forecast=True,
        method_note=METHOD_NOTE,
        as_of_date=as_of_date,
        base_price=BasePrice(close_usd=base_close, date=base_date),
        horizons=tuple(
            _horizon_scenarios(
                historical_prices,
                as_of_date,
                base_close,
                horizon_days,
            )
            for horizon_days in HORIZONS_DAYS
        ),
    )
