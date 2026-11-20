from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.repository import compute_and_store, feature_status
from app.db.models.ingestion import ComputedFeature, IngestionRun, Observation
from app.ingestion.seed import seed_reference_data

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _feature_checksum(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    ComputedFeature.chain_id,
                    ComputedFeature.feature,
                    ComputedFeature.as_of_date,
                    ComputedFeature.value,
                    ComputedFeature.n_obs,
                    ComputedFeature.window_days,
                    ComputedFeature.source_metric,
                    ComputedFeature.source,
                ).order_by(
                    ComputedFeature.chain_id,
                    ComputedFeature.feature,
                    ComputedFeature.as_of_date,
                )
            )
        ).all()
    body = "\n".join("|".join(str(value) for value in row) for row in rows)
    return len(rows), hashlib.md5(body.encode("utf-8")).hexdigest()


async def test_backfill_and_update_are_idempotent_and_run_logged(
    auth_session_factory: async_sessionmaker[AsyncSession],
    clean_ingestion_tables,
) -> None:
    start = date(2024, 1, 1)
    fetched_at = datetime(2026, 11, 20, tzinfo=UTC)
    async with auth_session_factory() as session:
        await seed_reference_data(session)
        session.add_all(
            [
                Observation(
                    chain_code="btc",
                    metric_code=metric,
                    source_code="binance",
                    obs_date=start + timedelta(days=index),
                    value=(
                        Decimal(100 + index)
                        if metric == "price_close_usd"
                        else Decimal(1000 + index)
                    ),
                    fetched_at=fetched_at,
                )
                for metric in ("price_close_usd", "volume_usd")
                for index in range(400)
            ]
        )
        await session.commit()

    as_of_today = start + timedelta(days=400)
    first = await compute_and_store(
        mode="backfill",
        chain="btc",
        today=as_of_today,
        session_factory=auth_session_factory,
    )
    before_update = await _feature_checksum(auth_session_factory)
    assert first.rows_upserted == before_update[0] > 0
    assert first.rows_by_chain == {"btc": first.rows_upserted}

    update = await compute_and_store(
        mode="update",
        chain="btc",
        today=as_of_today,
        session_factory=auth_session_factory,
    )
    after_update = await _feature_checksum(auth_session_factory)
    assert update.rows_deleted > 0
    assert after_update == before_update

    second = await compute_and_store(
        mode="backfill",
        chain="btc",
        today=as_of_today,
        session_factory=auth_session_factory,
    )
    after_backfill = await _feature_checksum(auth_session_factory)
    assert second.rows_upserted == first.rows_upserted
    assert after_backfill == before_update
    async with auth_session_factory() as session:
        stored_features = (await session.scalars(select(ComputedFeature))).all()
    assert all(isinstance(row.value, Decimal) for row in stored_features)

    statuses = await feature_status(
        chain="btc",
        session_factory=auth_session_factory,
    )
    assert any(
        chain == "btc" and feature == "ret_30d" and rows > 0
        for chain, feature, _, _, rows in statuses
    )
    async with auth_session_factory() as session:
        successful_runs = await session.scalar(
            select(func.count())
            .select_from(IngestionRun)
            .where(IngestionRun.job == "features", IngestionRun.status == "ok")
        )
    assert successful_runs == 3
