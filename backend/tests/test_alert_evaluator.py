from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.alerts.evaluator import AlertRuleSpec, AlertSnapshot, evaluate_alert_rule

DAY = date(2026, 11, 20)


def snapshot(
    day: date,
    *,
    score: str | None = "50",
    coverage: str | None = "0.70",
    regime: str | None = "range",
    flags: dict[str, str] | None = None,
) -> AlertSnapshot:
    return AlertSnapshot(
        as_of_date=day,
        score=Decimal(score) if score is not None else None,
        coverage=Decimal(coverage) if coverage is not None else None,
        confidence="Medium" if score is not None else None,
        regime=regime,
        flags=flags or {},
    )


@pytest.mark.parametrize(
    ("direction", "before", "after", "expected"),
    [
        ("below", "60", "49", True),
        ("below", "50", "49", True),
        ("below", "49", "40", False),
        ("above", "40", "50", True),
        ("above", "49", "50", True),
        ("above", "50", "60", False),
    ],
)
def test_score_cross_boundaries(
    direction: str, before: str, after: str, expected: bool
) -> None:
    rule = AlertRuleSpec(
        "score_cross",
        {"direction": direction, "threshold": 50},
        DAY - timedelta(days=2),
    )
    result = evaluate_alert_rule(
        rule,
        snapshot(DAY - timedelta(days=1), score=before),
        snapshot(DAY, score=after),
    )
    assert (result is not None) is expected


def test_evaluator_requires_adjacent_dates_and_day_after_rule_creation() -> None:
    rule = AlertRuleSpec("regime_change", {}, DAY - timedelta(days=1))
    assert (
        evaluate_alert_rule(rule, snapshot(DAY - timedelta(days=2)), snapshot(DAY))
        is None
    )
    assert (
        evaluate_alert_rule(
            rule,
            snapshot(DAY - timedelta(days=1)),
            snapshot(DAY),
        )
        is None
    )


def test_regime_change_returns_stored_regime_codes() -> None:
    rule = AlertRuleSpec("regime_change", {}, DAY - timedelta(days=2))
    assert evaluate_alert_rule(
        rule,
        snapshot(DAY - timedelta(days=1), regime="range"),
        snapshot(DAY, regime="stress"),
    ) == {"from": "range", "to": "stress"}


def test_risk_flag_is_edge_triggered_and_any_excludes_info() -> None:
    rule = AlertRuleSpec("risk_flag", {"flag": None}, DAY - timedelta(days=1))
    previous = snapshot(DAY - timedelta(days=1), flags={"deep_drawdown": "medium"})
    current = snapshot(
        DAY,
        flags={"deep_drawdown": "medium", "low_confidence": "info"},
    )
    assert evaluate_alert_rule(rule, previous, current) is None
    assert evaluate_alert_rule(
        rule,
        snapshot(DAY - timedelta(days=1)),
        snapshot(DAY, flags={"deep_drawdown": "high"}),
    ) == {"flag": "deep_drawdown", "severity": "high"}


@pytest.mark.parametrize(("cur", "expected"), [("0.75", False), ("0.751", True)])
def test_score_cross_includes_coverage_change_flag(cur: str, expected: bool) -> None:
    rule = AlertRuleSpec(
        "score_cross",
        {"direction": "below", "threshold": 50},
        DAY - timedelta(days=2),
    )
    result = evaluate_alert_rule(
        rule,
        snapshot(DAY - timedelta(days=1), score="50", coverage="0.70"),
        snapshot(DAY, score="49", coverage=cur),
    )
    assert result is not None
    assert result["coverage_changed"] is expected
    assert result["score"] == "49"


def test_missing_score_or_regime_suppresses_every_rule_type() -> None:
    rule = AlertRuleSpec("risk_flag", {"flag": None}, DAY - timedelta(days=1))
    assert (
        evaluate_alert_rule(
            rule,
            snapshot(DAY - timedelta(days=1)),
            snapshot(DAY, score=None),
        )
        is None
    )
    assert (
        evaluate_alert_rule(
            rule,
            snapshot(DAY - timedelta(days=1)),
            snapshot(DAY, regime=None),
        )
        is None
    )
