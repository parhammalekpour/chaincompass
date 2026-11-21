"""Descriptive score/return association; floats are used only for statistics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from app.analytics.scenarios import PricePoint
from app.research.statistics import (
    expanding_past_terciles,
    fisher_spearman_interval,
    spearman_correlation,
)

ScorePoint = tuple[date, Decimal]


def _sample_horizon(
    scores: tuple[ScorePoint, ...],
    prices: tuple[PricePoint, ...],
    horizon_days: int,
) -> list[tuple[date, Decimal, Decimal]]:
    scores_by_date = dict(scores)
    closes_by_date = dict(prices)
    if not scores:
        return []
    first_score_date = scores[0][0]
    last_score_date = scores[-1][0]
    output: list[tuple[date, Decimal, Decimal]] = []
    candidate = first_score_date
    while candidate <= last_score_date:
        score = scores_by_date.get(candidate)
        start_close = closes_by_date.get(candidate)
        end_close = closes_by_date.get(candidate + timedelta(days=horizon_days))
        if score is not None and start_close is not None and end_close is not None:
            output.append(
                (
                    candidate,
                    score,
                    end_close / start_close - Decimal(1),
                )
            )
        candidate += timedelta(days=horizon_days)
    return output


def _tercile_statistics(
    samples: list[tuple[date, Decimal, Decimal]],
    terciles: dict[date, str | None],
) -> tuple[dict[str, object], int]:
    grouped: dict[str, list[float]] = defaultdict(list)
    excluded = 0
    for sample_date, _score, forward_return in samples:
        group = terciles.get(sample_date)
        if group is None:
            excluded += 1
        else:
            grouped[group].append(float(forward_return))
    summaries: dict[str, object] = {}
    for group in ("low", "middle", "high"):
        values = grouped[group]
        summaries[group] = {
            "n": len(values),
            "mean_forward_return": sum(values) / len(values) if values else None,
            "median_forward_return": median(values) if values else None,
        }
    return summaries, excluded


def run_health_score_study(
    scores_by_chain: dict[str, tuple[ScorePoint, ...]],
    prices_by_chain: dict[str, tuple[PricePoint, ...]],
    protocol_commit: str | None,
) -> dict[str, object]:
    chains: list[dict[str, object]] = []
    source_dates: list[date] = []
    for chain in ("btc", "eth", "sol", "bnb"):
        scores = tuple(sorted(scores_by_chain.get(chain, ())))
        prices = tuple(sorted(prices_by_chain.get(chain, ())))
        if scores:
            source_dates.extend((scores[0][0], scores[-1][0]))
        terciles = expanding_past_terciles(scores, minimum_history=30)
        horizons: list[dict[str, object]] = []
        for horizon_days in (30, 90):
            samples = _sample_horizon(scores, prices, horizon_days)
            rho = spearman_correlation(
                [float(score) for _as_of, score, _forward in samples],
                [float(forward) for _as_of, _score, forward in samples],
            )
            interval = (
                fisher_spearman_interval(rho, len(samples)) if rho is not None else None
            )
            tercile_summary, excluded = _tercile_statistics(samples, terciles)
            horizons.append(
                {
                    "horizon_days": horizon_days,
                    "n": len(samples),
                    "n_independent": len(samples),
                    "spearman_rho": rho,
                    "fisher_z_approx_95": list(interval) if interval else None,
                    "association_not_distinguishable_from_zero": (
                        None if interval is None else interval[0] <= 0.0 <= interval[1]
                    ),
                    "terciles": tercile_summary,
                    "tercile_excluded_insufficient_past_scores": excluded,
                }
            )
        chains.append(
            {
                "chain": chain,
                "score_first_date": scores[0][0].isoformat() if scores else None,
                "score_last_date": scores[-1][0].isoformat() if scores else None,
                "horizons": horizons,
                "tercile_minimum_past_scores": 30,
            }
        )
    return {
        "study": "H",
        "protocol_commit": protocol_commit,
        "source_dates": {
            "first_score_date": min(source_dates).isoformat() if source_dates else None,
            "last_score_date": max(source_dates).isoformat() if source_dates else None,
        },
        "chains": chains,
    }
