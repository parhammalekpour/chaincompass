from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, cast

AlertType = Literal["regime_change", "risk_flag", "score_cross"]


@dataclass(frozen=True)
class AlertSnapshot:
    as_of_date: date
    score: Decimal | None
    coverage: Decimal | None
    confidence: str | None
    regime: str | None
    flags: dict[str, str]


@dataclass(frozen=True)
class AlertRuleSpec:
    type: AlertType
    params: dict[str, object]
    created_date: date


def evaluate_alert_rule(
    rule: AlertRuleSpec,
    previous: AlertSnapshot | None,
    current: AlertSnapshot,
) -> dict[str, object] | None:
    if (
        previous is None
        or previous.as_of_date != current.as_of_date - timedelta(days=1)
        or current.as_of_date <= rule.created_date
        or current.score is None
        or previous.score is None
        or current.regime is None
        or previous.regime is None
    ):
        return None

    if rule.type == "regime_change":
        if current.regime == previous.regime:
            return None
        return {"from": previous.regime, "to": current.regime}

    if rule.type == "risk_flag":
        requested_flag = rule.params["flag"]
        added_flags = sorted(
            flag
            for flag, severity in current.flags.items()
            if flag not in previous.flags
            and (requested_flag is not None or severity != "info")
            and (requested_flag is None or requested_flag == flag)
        )
        if not added_flags:
            return None
        flag = added_flags[0]
        return {"flag": flag, "severity": current.flags[flag]}

    direction = cast(Literal["below", "above"], rule.params["direction"])
    threshold = cast(int, rule.params["threshold"])
    if current.coverage is None or previous.coverage is None:
        return None
    crossed = (
        previous.score >= threshold and current.score < threshold
        if direction == "below"
        else previous.score < threshold and current.score >= threshold
    )
    if not crossed:
        return None
    return {
        "direction": direction,
        "threshold": threshold,
        "previous_score": str(previous.score),
        "score": str(current.score),
        "confidence": current.confidence,
        "coverage": str(current.coverage),
        "coverage_changed": abs(current.coverage - previous.coverage) > Decimal("0.05"),
    }
