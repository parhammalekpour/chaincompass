"""Historical scenario calibration; floats are used only for statistics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from app.analytics.scenarios import (
    PricePoint,
    calculate_scenarios,
    type7_quantile,
    window_returns,
)
from app.analytics.scenarios_config import (
    HORIZONS_DAYS,
    LOW_SAMPLE_INDEPENDENT_WINDOWS,
    MIN_INDEPENDENT_WINDOWS,
    RETURN_QUANTUM,
)
from app.research.statistics import pinball_loss, proportion_summary

ERA_ONE_END = date(2021, 12, 31)
METHODS = ("scenarios-v1", "B1")
QUANTILE_PROBABILITIES = {
    "p10": Decimal("0.10"),
    "p50": Decimal("0.50"),
    "p90": Decimal("0.90"),
}
CALIBRATION_REFERENCES = {
    "below_p10": 0.10,
    "below_p50": 0.50,
    "above_p90": 0.10,
    "p10_p90_hit": 0.80,
}
Category = Literal["low_sample", "normal_sample"]


@dataclass(frozen=True)
class ScenarioOrigin:
    chain: str
    as_of_date: date
    horizon_days: int
    method: str
    realized: Decimal
    forecasts: dict[str, Decimal]
    n_independent: int

    @property
    def sample_category(self) -> Category | None:
        if self.n_independent >= LOW_SAMPLE_INDEPENDENT_WINDOWS:
            return "normal_sample"
        if self.n_independent >= MIN_INDEPENDENT_WINDOWS:
            return "low_sample"
        return None


@dataclass(frozen=True)
class OriginForecast:
    available: bool
    forecasts: dict[str, Decimal]
    n_independent: int


def scenario_forecasts_at_origin(
    prices: tuple[PricePoint, ...],
    origin: date,
) -> dict[int, OriginForecast]:
    """Evaluate the shipped engine with no input dated after the requested origin."""
    history = tuple(sorted(point for point in prices if point[0] <= origin))
    analysis = calculate_scenarios(history, origin)
    return {
        horizon.days: OriginForecast(
            available=horizon.available,
            forecasts={item.quantile: item.return_value for item in horizon.scenarios},
            n_independent=horizon.n_independent,
        )
        for horizon in analysis.horizons
    }


def _b1_forecasts(
    prices: tuple[PricePoint, ...],
    origin: date,
    horizon_days: int,
) -> tuple[dict[str, Decimal] | None, int]:
    window_start = origin - timedelta(days=1094)
    window_prices = tuple(
        (price_date, close)
        for price_date, close in prices
        if window_start <= price_date <= origin
    )
    windows = window_returns(window_prices, origin, horizon_days)
    independent = len(windows) // horizon_days
    minimum = min(5, 1095 // horizon_days)
    if independent < minimum:
        return None, independent
    returns = [window[2] for window in windows]
    forecasts = {
        quantile: type7_quantile(returns, probability).quantize(
            RETURN_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
        for quantile, probability in QUANTILE_PROBABILITIES.items()
    }
    return forecasts, independent


def walk_forward_origins(
    chain: str,
    prices: tuple[PricePoint, ...],
) -> tuple[list[ScenarioOrigin], dict[str, dict[str, int]]]:
    """Evaluate every calendar origin using only price rows dated on or before it."""
    ordered_prices = tuple(sorted(prices))
    if not ordered_prices:
        return [], {}
    close_by_date = dict(ordered_prices)
    origins: list[ScenarioOrigin] = []
    exclusions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for origin_date in sorted(close_by_date):
        forecasts_at_origin = scenario_forecasts_at_origin(
            ordered_prices,
            origin_date,
        )
        for horizon_days in HORIZONS_DAYS:
            label = str(horizon_days)
            origin_forecast = forecasts_at_origin[horizon_days]
            if not origin_forecast.available:
                exclusions[label]["v1_unavailable"] += 1
            else:
                future_date = origin_date + timedelta(days=horizon_days)
                end_close = close_by_date.get(future_date)
                if end_close is None:
                    exclusions[label]["v1_missing_future_close"] += 1
                else:
                    realized = end_close / close_by_date[origin_date] - Decimal(1)
                    origins.append(
                        ScenarioOrigin(
                            chain=chain,
                            as_of_date=origin_date,
                            horizon_days=horizon_days,
                            method="scenarios-v1",
                            realized=realized,
                            forecasts=origin_forecast.forecasts,
                            n_independent=origin_forecast.n_independent,
                        )
                    )

            forecasts, independent = _b1_forecasts(
                ordered_prices, origin_date, horizon_days
            )
            future_date = origin_date + timedelta(days=horizon_days)
            end_close = close_by_date.get(future_date)
            if forecasts is None:
                exclusions[label]["B1_unavailable"] += 1
            elif end_close is None:
                exclusions[label]["B1_missing_future_close"] += 1
            else:
                realized = end_close / close_by_date[origin_date] - Decimal(1)
                origins.append(
                    ScenarioOrigin(
                        chain=chain,
                        as_of_date=origin_date,
                        horizon_days=horizon_days,
                        method="B1",
                        realized=realized,
                        forecasts=forecasts,
                        n_independent=independent,
                    )
                )
    return origins, {
        horizon: dict(sorted(counts.items()))
        for horizon, counts in sorted(exclusions.items())
    }


def _era(origin: ScenarioOrigin) -> str:
    return "E1" if origin.as_of_date <= ERA_ONE_END else "E2"


def _on_grid(origins: list[ScenarioOrigin]) -> list[ScenarioOrigin]:
    if not origins:
        return []
    ordered = sorted(origins, key=lambda origin: origin.as_of_date)
    anchor = ordered[0].as_of_date
    horizon = ordered[0].horizon_days
    by_date = {origin.as_of_date: origin for origin in ordered}
    selected: list[ScenarioOrigin] = []
    candidate = anchor
    last = ordered[-1].as_of_date
    while candidate <= last:
        origin = by_date.get(candidate)
        if origin is not None:
            selected.append(origin)
        candidate += timedelta(days=horizon)
    return selected


def calibration_metrics(
    origins: list[ScenarioOrigin],
    *,
    include_wilson: bool,
) -> dict[str, object]:
    counts = dict.fromkeys(CALIBRATION_REFERENCES, 0)
    for origin in origins:
        realized = float(origin.realized)
        p10 = float(origin.forecasts["p10"])
        p50 = float(origin.forecasts["p50"])
        p90 = float(origin.forecasts["p90"])
        counts["below_p10"] += realized < p10
        counts["below_p50"] += realized < p50
        counts["above_p90"] += realized > p90
        counts["p10_p90_hit"] += p10 <= realized <= p90
    results: dict[str, object] = {}
    for metric, reference in CALIBRATION_REFERENCES.items():
        summary = proportion_summary(counts[metric], len(origins))
        if not include_wilson:
            summary.pop("wilson_95")
        results[metric] = {**summary, "reference": reference}
    return results


def _summarize_sample(
    origins: list[ScenarioOrigin],
    *,
    non_overlapping: bool,
) -> dict[str, object]:
    return {
        "n": len(origins),
        "n_independent_origins": len(origins) if non_overlapping else None,
        "metrics": calibration_metrics(origins, include_wilson=non_overlapping),
    }


def _summarize_origins(
    origins: list[ScenarioOrigin],
    grid_origins: list[ScenarioOrigin],
    *,
    include_sample_groups: bool,
) -> dict[str, object]:
    result: dict[str, object] = {
        "all_origins": _summarize_sample(origins, non_overlapping=False),
        "non_overlapping": _summarize_sample(
            grid_origins,
            non_overlapping=True,
        ),
    }
    if include_sample_groups:
        result["sample_groups"] = {
            category: {
                sample_name: _summarize_sample(
                    [
                        origin
                        for origin in (
                            origins if sample_name == "all_origins" else grid_origins
                        )
                        if origin.sample_category == category
                    ],
                    non_overlapping=sample_name == "non_overlapping",
                )
                for sample_name in ("all_origins", "non_overlapping")
            }
            for category in ("low_sample", "normal_sample")
        }
    return result


def _paired_pinball(
    v1_origins: list[ScenarioOrigin],
    b1_origins: list[ScenarioOrigin],
    selected_dates: list[date] | None = None,
) -> dict[str, dict[str, float | int | None]]:
    v1_by_date = {origin.as_of_date: origin for origin in v1_origins}
    b1_by_date = {origin.as_of_date: origin for origin in b1_origins}
    common_dates = sorted(v1_by_date.keys() & b1_by_date.keys())
    if not common_dates:
        return {
            method: {"n": 0, "p10": None, "p50": None, "p90": None}
            for method in METHODS
        }
    if selected_dates is None:
        horizon = v1_origins[0].horizon_days
        anchor = common_dates[0]
        common = set(common_dates)
        selected_dates = []
        candidate = anchor
        while candidate <= common_dates[-1]:
            if candidate in common:
                selected_dates.append(candidate)
            candidate += timedelta(days=horizon)
    output: dict[str, dict[str, float | int | None]] = {}
    for method, by_date in (("scenarios-v1", v1_by_date), ("B1", b1_by_date)):
        losses: dict[str, list[float]] = {key: [] for key in ("p10", "p50", "p90")}
        for as_of in selected_dates:
            origin = by_date[as_of]
            realized = float(origin.realized)
            for quantile, probability in QUANTILE_PROBABILITIES.items():
                losses[quantile].append(
                    pinball_loss(
                        float(probability),
                        realized,
                        float(origin.forecasts[quantile]),
                    )
                )
        output[method] = {
            "n": len(selected_dates),
            **{
                quantile: sum(values) / len(values) if values else None
                for quantile, values in losses.items()
            },
        }
    return output


def _label_v1(pooled: dict[str, object]) -> str:
    non_overlapping = pooled.get("non_overlapping")
    if not isinstance(non_overlapping, dict):
        return "inconclusive"
    metrics = non_overlapping.get("metrics")
    if not isinstance(metrics, dict):
        return "inconclusive"
    hit = _wilson_interval(metrics, "p10_p90_hit")
    lower = _wilson_interval(metrics, "below_p10")
    upper = _wilson_interval(metrics, "above_p90")
    if hit is None or lower is None or upper is None:
        return "inconclusive"
    hit_contains = hit[0] <= 0.80 <= hit[1]
    tails_contain = lower[0] <= 0.10 <= lower[1] and upper[0] <= 0.10 <= upper[1]
    if hit_contains and tails_contain:
        return "well calibrated"
    if not hit_contains:
        return "miscalibrated"
    return "inconclusive"


def _wilson_interval(
    metrics: dict[object, object],
    metric_name: str,
) -> tuple[float, float] | None:
    metric = metrics.get(metric_name)
    if not isinstance(metric, dict):
        return None
    interval = metric.get("wilson_95")
    if (
        not isinstance(interval, list)
        or len(interval) != 2
        or not all(isinstance(value, (int, float)) for value in interval)
    ):
        return None
    return float(interval[0]), float(interval[1])


def run_scenario_study(
    prices_by_chain: dict[str, tuple[PricePoint, ...]],
    protocol_commit: str | None,
) -> dict[str, object]:
    cells: list[dict[str, object]] = []
    source_dates: list[date] = []
    for chain in ("btc", "eth", "sol", "bnb"):
        prices = prices_by_chain.get(chain, ())
        if prices:
            source_dates.extend((prices[0][0], prices[-1][0]))
        origins, exclusions = walk_forward_origins(chain, prices)
        for horizon in HORIZONS_DAYS:
            method_origins = {
                method: [
                    origin
                    for origin in origins
                    if origin.horizon_days == horizon and origin.method == method
                ]
                for method in METHODS
            }
            method_summaries: dict[str, dict[str, dict[str, object]]] = {}
            labels: dict[str, str] = {}
            for method, items in method_origins.items():
                grid_origins = _on_grid(items)
                periods = {
                    period: _summarize_origins(
                        [
                            origin
                            for origin in items
                            if period == "pooled" or _era(origin) == period
                        ],
                        [
                            origin
                            for origin in grid_origins
                            if period == "pooled" or _era(origin) == period
                        ],
                        include_sample_groups=method == "scenarios-v1",
                    )
                    for period in ("pooled", "E1", "E2")
                }
                method_summaries[method] = periods
                if method == "scenarios-v1":
                    labels = {period: _label_v1(periods[period]) for period in periods}

            v1_dates = {origin.as_of_date for origin in method_origins["scenarios-v1"]}
            b1_dates = {origin.as_of_date for origin in method_origins["B1"]}
            paired_origins = v1_dates & b1_dates
            pinball: dict[str, object] = {}
            common_dates = sorted(paired_origins)
            paired_grid: list[date] = []
            if common_dates:
                candidate = common_dates[0]
                while candidate <= common_dates[-1]:
                    if candidate in paired_origins:
                        paired_grid.append(candidate)
                    candidate += timedelta(days=horizon)
            for period in ("pooled", "E1", "E2"):
                shared_dates = [
                    as_of
                    for as_of in paired_grid
                    if period == "pooled"
                    or ("E1" if as_of <= ERA_ONE_END else "E2") == period
                ]
                pinball[period] = _paired_pinball(
                    [
                        origin
                        for origin in method_origins["scenarios-v1"]
                        if origin.as_of_date in shared_dates
                    ],
                    [
                        origin
                        for origin in method_origins["B1"]
                        if origin.as_of_date in shared_dates
                    ],
                    selected_dates=shared_dates,
                )

            cells.append(
                {
                    "chain": chain,
                    "horizon_days": horizon,
                    "methods": method_summaries,
                    "paired_non_overlapping_pinball": pinball,
                    "scenarios_v1_labels": labels,
                    "exclusions": exclusions.get(str(horizon), {}),
                }
            )
    return {
        "study": "S",
        "protocol_commit": protocol_commit,
        "price_series": {
            "metric": "price_close_usd",
            "source": "binance",
            "first_date": min(source_dates).isoformat() if source_dates else None,
            "last_date": max(source_dates).isoformat() if source_dates else None,
        },
        "cells": cells,
    }
