from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.alerts.evaluation import evaluate_active_rules
from app.analytics.score_config import VERSION
from app.db.models.alerts import AlertEvent, AlertRule
from app.db.models.auth import User
from app.db.models.health import HealthScore, MarketRegime
from app.db.models.ingestion import Chain


async def _seed_chain(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        if await session.get(Chain, "btc") is None:
            session.add(
                Chain(
                    code="btc",
                    name="Bitcoin",
                    native_symbol="BTC",
                    consensus="pow",
                    enabled=True,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_worker_catchup_window_idempotency_and_user_independence(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_chain(auth_session_factory)
    suffix = uuid4().hex
    async with auth_session_factory() as session:
        users = [
            User(email=f"alerts-{suffix}-{index}@example.test") for index in range(4)
        ]
        session.add_all(users)
        await session.flush()
        latest = date.today() - timedelta(days=1)
        first = latest - timedelta(days=5)
        created_at = datetime.combine(
            first - timedelta(days=1), datetime.min.time(), tzinfo=UTC
        )
        for owner in users[:2]:
            session.add(
                AlertRule(
                    user_id=owner.id,
                    chain_id="btc",
                    type="score_cross",
                    params={"direction": "below", "threshold": 50},
                    params_key='{"direction":"below","threshold":50}',
                    created_at=created_at,
                )
            )
        session.add(
            AlertRule(
                user_id=users[2].id,
                chain_id="btc",
                type="score_cross",
                params={"direction": "below", "threshold": 50},
                params_key='{"direction":"below","threshold":50}',
                created_at=datetime.combine(latest, datetime.min.time(), tzinfo=UTC),
            )
        )
        session.add(
            AlertRule(
                user_id=users[3].id,
                chain_id="btc",
                type="risk_flag",
                params={},
                params_key="{}",
                created_at=created_at,
            )
        )
        scores = ["70", "40", "39", "60", "40", "45"]
        for offset, score in enumerate(scores):
            as_of_date = first + timedelta(days=offset)
            session.add(
                HealthScore(
                    chain_id="btc",
                    as_of_date=as_of_date,
                    version=VERSION,
                    score=Decimal(score),
                    coverage=Decimal("0.70"),
                    confidence_label="Medium",
                    pillars={},
                    components=[],
                )
            )
            session.add(
                MarketRegime(
                    chain_id="btc",
                    as_of_date=as_of_date,
                    version=VERSION,
                    regime="range",
                    raw_regime="range",
                    days_in_regime=1,
                )
            )
        user_ids = [owner.id for owner in users]
        await session.commit()

    created, evaluated, failed = await evaluate_active_rules(
        session_factory=auth_session_factory
    )
    assert (created, evaluated, failed) == (2, 8, 1)
    async with auth_session_factory() as session:
        events = (
            (
                await session.execute(
                    select(AlertEvent).where(AlertEvent.user_id.in_(user_ids))
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 2
        assert {event.user_id for event in events} == set(user_ids[:2])
        assert {event.as_of_date for event in events} == {latest - timedelta(days=1)}
        assert all(event.payload["score"] == "40.00" for event in events)

    created_again, _, failed_again = await evaluate_active_rules(
        session_factory=auth_session_factory
    )
    assert created_again == 0
    assert failed_again == 1
    async with auth_session_factory() as session:
        events = (
            (
                await session.execute(
                    select(AlertEvent).where(AlertEvent.user_id.in_(user_ids))
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 2
        for owner_id in user_ids:
            owner = await session.get(User, owner_id)
            assert owner is not None
            await session.delete(owner)
        await session.commit()
