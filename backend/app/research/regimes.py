"""Read-only comparison of shipped regime v1 and a fixed stress-entry variant."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from app.analytics.scoring import FeatureRecord, RegimeValue, compute_analytics

STRESS_THRESHOLD = Decimal("-0.50")
REGIME_STRESS = "stress"


@dataclass(frozen=True)
class RegimePoint:
    as_of_date: date
    regime: str
    raw_regime: str


def regime_v2(raw_points: Sequence[RegimePoint]) -> tuple[RegimePoint, ...]:
    reported: str | None = None
    pending: str | None = None
    pending_days = 0
    previous_date: date | None = None
    output: list[RegimePoint] = []

    for raw_point in raw_points:
        raw = raw_point.raw_regime
        consecutive = (
            previous_date is not None
            and raw_point.as_of_date == previous_date + timedelta(days=1)
        )
        if reported is None:
            reported = raw
            pending = None
            pending_days = 0
        elif not consecutive:
            pending = None
            pending_days = 0
            if raw == REGIME_STRESS:
                reported = REGIME_STRESS
            elif raw != reported:
                pending = raw
                pending_days = 1
        elif raw == REGIME_STRESS:
            reported = REGIME_STRESS
            pending = None
            pending_days = 0
        elif reported == REGIME_STRESS:
            if pending == raw:
                pending_days += 1
            else:
                pending = raw
                pending_days = 1
            if pending_days >= 5:
                reported = raw
                pending = None
                pending_days = 0
        elif raw == reported:
            pending = None
            pending_days = 0
        elif pending == raw:
            pending_days += 1
            if pending_days >= 5:
                reported = raw
                pending = None
                pending_days = 0
        else:
            pending = raw
            pending_days = 1

        output.append(
            RegimePoint(
                as_of_date=raw_point.as_of_date,
                regime=reported,
                raw_regime=raw,
            )
        )
        previous_date = raw_point.as_of_date
    return tuple(output)


def _runs(
    points: Sequence[RegimePoint],
) -> list[dict[str, object]]:
    ordered = sorted(points, key=lambda point: point.as_of_date)
    if not ordered:
        return []
    runs: list[dict[str, object]] = []
    start = ordered[0].as_of_date
    previous = ordered[0]
    duration = 1
    for point in ordered[1:]:
        consecutive = point.as_of_date == previous.as_of_date + timedelta(days=1)
        if consecutive and point.regime == previous.regime:
            duration += 1
        else:
            runs.append(
                {
                    "regime": previous.regime,
                    "start_date": start.isoformat(),
                    "end_date": previous.as_of_date.isoformat(),
                    "days": duration,
                    "censored": not consecutive,
                }
            )
            start = point.as_of_date
            duration = 1
        previous = point
    runs.append(
        {
            "regime": previous.regime,
            "start_date": start.isoformat(),
            "end_date": previous.as_of_date.isoformat(),
            "days": duration,
            "censored": True,
        }
    )
    return runs


def _raw_stress_episodes(
    features: Sequence[FeatureRecord],
) -> list[tuple[date, date]]:
    drawdowns = {
        record.as_of_date: record.value
        for record in features
        if record.feature == "drawdown_365d"
    }
    dates = sorted(drawdowns)
    episodes: list[tuple[date, date]] = []
    start: date | None = None
    previous: date | None = None
    for current in dates:
        is_stress = drawdowns[current] <= STRESS_THRESHOLD
        if is_stress and (
            start is None or previous is None or current != previous + timedelta(days=1)
        ):
            if start is not None and previous is not None:
                episodes.append((start, previous))
            start = current
        elif not is_stress and start is not None and previous is not None:
            episodes.append((start, previous))
            start = None
        previous = current
    if start is not None and previous is not None:
        episodes.append((start, previous))
    return episodes


def _stress_lags(
    episodes: Sequence[tuple[date, date]],
    states: Sequence[RegimePoint],
) -> list[dict[str, object]]:
    by_date = {point.as_of_date: point.regime for point in states}
    latest = max(by_date) if by_date else None
    output: list[dict[str, object]] = []
    for start, end in episodes:
        stress_dates = sorted(
            current
            for current, regime in by_date.items()
            if start <= current <= end and regime == REGIME_STRESS
        )
        detected = stress_dates[0] if stress_dates else None
        exit_date = (
            min(
                (
                    current
                    for current, regime in by_date.items()
                    if current > end and regime != REGIME_STRESS
                ),
                default=None,
            )
            if detected is not None
            else None
        )
        output.append(
            {
                "raw_stress_start": start.isoformat(),
                "raw_stress_end": end.isoformat(),
                "detection_lag_days": (detected - start).days if detected else None,
                "detection_not_observed": detected is None,
                "exit_lag_days": (exit_date - end).days if exit_date else None,
                "exit_right_censored": detected is not None
                and exit_date is None
                and latest is not None
                and latest >= end,
            }
        )
    return output


def _version_metrics(
    states: Sequence[RegimePoint],
    stress_episodes: Sequence[tuple[date, date]],
) -> dict[str, object]:
    runs = _runs(states)
    durations = [run["days"] for run in runs if isinstance(run["days"], int)]
    switches = sum(
        previous.regime != current.regime
        for previous, current in zip(states, states[1:], strict=False)
    )
    return {
        "regime_switches": switches,
        "regime_episode_count": len(runs),
        "mean_regime_duration_days": (
            sum(durations) / len(durations) if durations else None
        ),
        "median_regime_duration_days": median(durations) if durations else None,
        "episodes_under_10_days": sum(duration < 10 for duration in durations),
        "regime_durations": runs,
        "raw_stress_episodes": _stress_lags(stress_episodes, states),
    }


def _compare_stored_regimes(
    computed: Sequence[RegimeValue],
    stored: Sequence[tuple[date, str]],
) -> dict[str, object]:
    computed_by_date = {point.as_of_date: point.regime for point in computed}
    stored_by_date = dict(stored)
    mismatches = [
        {
            "date": as_of.isoformat(),
            "computed": computed_by_date.get(as_of),
            "stored": stored_by_date.get(as_of),
        }
        for as_of in sorted(computed_by_date.keys() | stored_by_date.keys())
        if computed_by_date.get(as_of) != stored_by_date.get(as_of)
    ]
    return {
        "matches": not mismatches,
        "mismatch_count": len(mismatches),
        "examples": mismatches[:10],
    }


def run_regime_study(
    features_by_chain: dict[str, tuple[FeatureRecord, ...]],
    stored_regimes_by_chain: dict[str, tuple[tuple[date, str], ...]],
    protocol_commit: str | None,
) -> dict[str, object]:
    chains: list[dict[str, object]] = []
    for chain in ("btc", "eth", "sol", "bnb"):
        features = features_by_chain.get(chain, ())
        output = compute_analytics(chain, features)
        v1_states = tuple(
            RegimePoint(point.as_of_date, point.regime, point.raw_regime)
            for point in output.regimes
        )
        v2_states = regime_v2(v1_states)
        stress_episodes = _raw_stress_episodes(features)
        chains.append(
            {
                "chain": chain,
                "stored_v1_comparison": _compare_stored_regimes(
                    output.regimes,
                    stored_regimes_by_chain.get(chain, ()),
                ),
                "versions": {
                    "v1": _version_metrics(v1_states, stress_episodes),
                    "v2": _version_metrics(v2_states, stress_episodes),
                },
            }
        )
    return {
        "study": "R",
        "protocol_commit": protocol_commit,
        "raw_stress_definition": "drawdown_365d <= -0.50",
        "chains": chains,
    }
