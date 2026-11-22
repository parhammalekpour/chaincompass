from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from app.analytics.score_config import COMPONENTS, SCORE_QUANTUM, VERSION

IndicatorStatus = Literal["available", "not_available", "not_applicable"]
IndicatorGroup = Literal["market", "capital", "usage", "security"]

_GROUP_BY_PILLAR: dict[str, IndicatorGroup] = {
    "market_condition": "market",
    "capital": "capital",
    "adoption": "usage",
    "security_economics": "security",
}


@dataclass(frozen=True)
class RegimePoint:
    as_of_date: date
    regime: str
    vol_state: str | None


@dataclass(frozen=True)
class FundamentalReportSnapshot:
    chain: str
    as_of_date: date
    scores: dict[date, Decimal]
    confidence: str | None
    coverage: Decimal | None
    regime_rows: tuple[RegimePoint, ...]
    flags: tuple[tuple[str, str], ...]
    feature_values: dict[str, Decimal]
    component_percentiles: dict[str, Decimal]


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _change(
    scores: dict[date, Decimal],
    current: date,
    days: int,
) -> tuple[Decimal | None, Decimal | None]:
    earlier = scores.get(current - timedelta(days=days))
    if earlier is None:
        return None, None
    current_score = scores.get(current)
    if current_score is None:
        return earlier, None
    difference = (current_score - earlier).quantize(
        SCORE_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )
    return earlier, difference


def _regime_summary(
    points: tuple[RegimePoint, ...],
    as_of: date,
) -> dict[str, object]:
    by_date = {point.as_of_date: point for point in points}
    current = by_date.get(as_of)
    if current is None:
        return {
            "regime": None,
            "vol_state": None,
            "since_date": None,
            "days_in_regime": None,
            "history_gap": bool(points),
        }

    ordered_dates = sorted(by_date, reverse=True)
    history_gap = any(
        (newer - older).days > 1
        for newer, older in zip(ordered_dates, ordered_dates[1:], strict=False)
    )
    start = as_of
    count = 1
    cursor = as_of
    while True:
        previous_date = cursor - timedelta(days=1)
        previous = by_date.get(previous_date)
        if previous is None:
            break
        if previous.regime != current.regime:
            break
        start = previous_date
        cursor = previous_date
        count += 1

    return {
        "regime": current.regime,
        "vol_state": current.vol_state,
        "since_date": start.isoformat(),
        "days_in_regime": count,
        "history_gap": history_gap,
    }


def build_fundamental_report(
    snapshot: FundamentalReportSnapshot,
) -> dict[str, object]:
    score = snapshot.scores.get(snapshot.as_of_date)
    if score is None:
        return {"ok": False, "error": {"code": "no_data"}}

    score_30d, change_30d = _change(snapshot.scores, snapshot.as_of_date, 30)
    score_90d, change_90d = _change(snapshot.scores, snapshot.as_of_date, 90)
    indicators: list[dict[str, object]] = []
    data_gaps: list[dict[str, str]] = []

    for spec in COMPONENTS:
        if snapshot.chain not in spec.chains:
            status: IndicatorStatus = "not_applicable"
            value = None
            percentile = None
        else:
            value = snapshot.feature_values.get(spec.feature)
            percentile = snapshot.component_percentiles.get(spec.feature)
            status = "available" if percentile is not None else "not_available"
        indicators.append(
            {
                "key": spec.feature,
                "group": _GROUP_BY_PILLAR[spec.pillar],
                "value": _decimal_text(value),
                "percentile": _decimal_text(percentile),
                "status": status,
            }
        )
        if status != "available":
            data_gaps.append({"key": spec.feature, "status": status})

    data_gaps.extend(
        {"key": key, "status": "not_available_free"}
        for key in ("holder_distribution", "exchange_flows", "news_evidence")
    )

    return {
        "chain": snapshot.chain,
        "as_of_date": snapshot.as_of_date.isoformat(),
        "methodology_version": VERSION,
        "generated_from": "stored_data",
        "health": {
            "score": _decimal_text(score),
            "confidence": snapshot.confidence,
            "coverage": _decimal_text(snapshot.coverage),
            "score_30d_ago": _decimal_text(score_30d),
            "score_90d_ago": _decimal_text(score_90d),
            "change_30d": _decimal_text(change_30d),
            "change_90d": _decimal_text(change_90d),
        },
        "regime": _regime_summary(snapshot.regime_rows, snapshot.as_of_date),
        "flags": [
            {"code": code, "severity": severity}
            for code, severity in sorted(snapshot.flags)
        ],
        "indicators": indicators,
        "data_gaps": data_gaps,
    }
