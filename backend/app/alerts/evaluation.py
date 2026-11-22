import logging
from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.alerts.evaluator import (
    AlertRuleSpec,
    AlertSnapshot,
    AlertType,
    evaluate_alert_rule,
)
from app.analytics.score_config import VERSION
from app.db.models.alerts import AlertEvent, AlertRule
from app.db.models.health import HealthScore, MarketRegime, RiskFlag
from app.db.session import SessionFactory
from app.schemas.alerts import validated_rule_params

logger = logging.getLogger("app.alerts")


async def _snapshot(
    session: AsyncSession, chain_id: str, as_of_date: date
) -> AlertSnapshot:
    score = await session.get(HealthScore, (chain_id, as_of_date, VERSION))
    regime = await session.get(MarketRegime, (chain_id, as_of_date, VERSION))
    flags = (
        await session.execute(
            select(RiskFlag.flag, RiskFlag.severity).where(
                RiskFlag.chain_id == chain_id,
                RiskFlag.as_of_date == as_of_date,
                RiskFlag.version == VERSION,
            )
        )
    ).all()
    return AlertSnapshot(
        as_of_date=as_of_date,
        score=score.score if score is not None else None,
        coverage=score.coverage if score is not None else None,
        confidence=score.confidence_label if score is not None else None,
        regime=regime.regime if regime is not None else None,
        flags={flag: severity for flag, severity in flags},
    )


def _utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(UTC).date()


async def evaluate_active_rules(
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> tuple[int, int, int]:
    async with session_factory() as session:
        rules = (
            await session.execute(
                select(AlertRule).where(AlertRule.is_active.is_(True))
            )
        ).scalars()
        rule_rows = [
            (
                rule.id,
                rule.user_id,
                rule.chain_id,
                rule.type,
                rule.params,
                _utc_date(rule.created_at),
            )
            for rule in rules
        ]

    events_created = 0
    evaluated = 0
    failed = 0
    for rule_id, user_id, chain_id, rule_type, raw_params, created_date in rule_rows:
        try:
            params = validated_rule_params(rule_type, raw_params)
            rule_spec = AlertRuleSpec(
                type=cast(AlertType, rule_type),
                params=params,
                created_date=created_date,
            )
            async with session_factory() as session:
                complete_rows = (
                    await session.execute(
                        select(HealthScore.as_of_date)
                        .join(
                            MarketRegime,
                            (MarketRegime.chain_id == HealthScore.chain_id)
                            & (MarketRegime.as_of_date == HealthScore.as_of_date)
                            & (MarketRegime.version == HealthScore.version),
                        )
                        .where(
                            HealthScore.chain_id == chain_id,
                            HealthScore.version == VERSION,
                        )
                        .order_by(HealthScore.as_of_date.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if complete_rows is None:
                    continue
                first_date = complete_rows - timedelta(days=3)
                dates = (
                    await session.execute(
                        select(HealthScore.as_of_date)
                        .join(
                            MarketRegime,
                            (MarketRegime.chain_id == HealthScore.chain_id)
                            & (MarketRegime.as_of_date == HealthScore.as_of_date)
                            & (MarketRegime.version == HealthScore.version),
                        )
                        .where(
                            HealthScore.chain_id == chain_id,
                            HealthScore.version == VERSION,
                            HealthScore.as_of_date >= first_date,
                            HealthScore.as_of_date <= complete_rows,
                        )
                        .order_by(HealthScore.as_of_date)
                    )
                ).scalars()

                for current_date in dates:
                    if current_date <= rule_spec.created_date:
                        continue
                    current = await _snapshot(session, chain_id, current_date)
                    previous = await _snapshot(
                        session, chain_id, current_date - timedelta(days=1)
                    )
                    payload = evaluate_alert_rule(rule_spec, previous, current)
                    evaluated += 1
                    if payload is None:
                        continue
                    statement = (
                        insert(AlertEvent)
                        .values(
                            rule_id=rule_id,
                            user_id=user_id,
                            chain_id=chain_id,
                            as_of_date=current_date,
                            type=rule_spec.type,
                            payload=payload,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["rule_id", "as_of_date"]
                        )
                        .returning(AlertEvent.id)
                    )
                    result = await session.execute(statement)
                    events_created += len(result.scalars().all())
                await session.commit()
        except Exception as exc:
            failed += 1
            logger.warning(
                "alert_rule_evaluation_failed rule_id=%s error_type=%s",
                rule_id,
                type(exc).__name__,
            )
    return events_created, evaluated, failed
