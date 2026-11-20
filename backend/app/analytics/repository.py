from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.analytics.features import (
    FeaturePoint,
    FeatureValue,
    compute_series_features,
)
from app.analytics.registry import FEATURE_INPUTS
from app.db.models.ingestion import ComputedFeature, IngestionRun, Observation
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)
ComputeMode = Literal["backfill", "update"]
INSERT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class ComputeSummary:
    rows_upserted: int
    rows_deleted: int
    rows_by_chain: dict[str, int]


def _series_predicates(chain: str | None) -> list[ColumnElement[bool]]:
    return [
        and_(
            Observation.chain_code == spec.chain,
            Observation.metric_code == spec.metric,
            Observation.source_code == spec.source,
        )
        for spec in FEATURE_INPUTS
        if chain is None or spec.chain == chain
    ]


def _feature_row(item: FeatureValue) -> dict[str, object]:
    return {
        "chain_id": item.chain,
        "feature": item.feature,
        "as_of_date": item.as_of_date,
        "value": item.value,
        "n_obs": item.n_obs,
        "window_days": item.window_days,
        "source_metric": item.source_metric,
        "source": item.source,
    }


async def _start_run(
    session_factory: async_sessionmaker[AsyncSession],
    mode: ComputeMode,
    chain: str | None,
) -> IngestionRun:
    started_at = datetime.now(UTC)
    run = IngestionRun(
        id=uuid4(),
        job="features",
        provider="analytics",
        started_at=started_at,
        status="running",
        details=f"mode={mode} chain={chain or 'all'}",
    )
    async with session_factory() as session:
        session.add(run)
        await session.commit()
    return run


async def _mark_failed(
    run_id: UUID,
    error_type: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        run = await session.get(IngestionRun, run_id)
        if run is None:
            raise RuntimeError("feature run record disappeared")
        run.finished_at = datetime.now(UTC)
        run.status = "failed"
        run.error = f"feature computation failed ({error_type})"
        await session.commit()


async def compute_and_store(
    *,
    mode: ComputeMode,
    chain: str | None = None,
    today: date | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> ComputeSummary:
    if chain is not None and chain not in {"btc", "eth", "sol", "bnb"}:
        raise ValueError(f"unsupported chain: {chain}")
    as_of_today = today or datetime.now(UTC).date()
    run = await _start_run(session_factory, mode, chain)
    try:
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(Observation)
                    .where(or_(*_series_predicates(chain)))
                    .order_by(
                        Observation.chain_code,
                        Observation.metric_code,
                        Observation.source_code,
                        Observation.obs_date,
                    )
                )
            ).all()
            grouped: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
            for row in rows:
                grouped[(row.chain_code, row.metric_code, row.source_code)].append(row)

            target_dates = None
            if mode == "update":
                target_dates = {
                    as_of_today - timedelta(days=days_ago) for days_ago in range(1, 15)
                }

            computed: list[FeatureValue] = []
            for spec in FEATURE_INPUTS:
                if chain is not None and spec.chain != chain:
                    continue
                stored = grouped.get((spec.chain, spec.metric, spec.source), [])
                if not stored:
                    continue
                computed.extend(
                    compute_series_features(
                        spec.chain,
                        spec.metric,
                        spec.source,
                        [FeaturePoint(row.obs_date, row.value) for row in stored],
                        as_of_dates=target_dates,
                    )
                )

            chain_codes = sorted(
                {
                    spec.chain
                    for spec in FEATURE_INPUTS
                    if chain is None or spec.chain == chain
                }
            )
            cleanup_conditions: list[ColumnElement[bool]] = [
                ComputedFeature.chain_id.in_(chain_codes)
            ]
            if mode == "update":
                cleanup_conditions.append(
                    and_(
                        ComputedFeature.as_of_date >= as_of_today - timedelta(days=14),
                        ComputedFeature.as_of_date < as_of_today,
                    )
                )
            rows_deleted = await session.scalar(
                select(func.count())
                .select_from(ComputedFeature)
                .where(*cleanup_conditions)
            )
            await session.execute(delete(ComputedFeature).where(*cleanup_conditions))

            values = [_feature_row(item) for item in computed]
            for offset in range(0, len(values), INSERT_BATCH_SIZE):
                batch = values[offset : offset + INSERT_BATCH_SIZE]
                statement = insert(ComputedFeature).values(batch)
                statement = statement.on_conflict_do_update(
                    index_elements=["chain_id", "feature", "as_of_date"],
                    set_={
                        "value": statement.excluded.value,
                        "n_obs": statement.excluded.n_obs,
                        "window_days": statement.excluded.window_days,
                        "source_metric": statement.excluded.source_metric,
                        "source": statement.excluded.source,
                    },
                )
                await session.execute(statement)

            run_row = await session.get(IngestionRun, run.id)
            if run_row is None:
                raise RuntimeError("feature run record disappeared")
            run_row.finished_at = datetime.now(UTC)
            run_row.status = "ok"
            run_row.rows_upserted = len(computed)
            run_row.rows_rejected = 0
            run_row.error = None
            run_row.details = (
                f"mode={mode} chain={chain or 'all'} "
                f"rows_deleted={int(rows_deleted or 0)}"
            )
            await session.commit()
    except Exception as exc:
        logger.error(
            "feature_computation_failed run_id=%s error_type=%s",
            run.id,
            type(exc).__name__,
        )
        try:
            await _mark_failed(run.id, type(exc).__name__, session_factory)
        except Exception as record_exc:
            logger.error(
                "feature_run_record_failed run_id=%s error_type=%s",
                run.id,
                type(record_exc).__name__,
            )
        raise

    counts: dict[str, int] = defaultdict(int)
    for item in computed:
        counts[item.chain] += 1
    summary = ComputeSummary(
        rows_upserted=len(computed),
        rows_deleted=int(rows_deleted or 0),
        rows_by_chain=dict(sorted(counts.items())),
    )
    logger.info(
        "feature_computation_finished run_id=%s mode=%s rows=%s",
        run.id,
        mode,
        summary.rows_upserted,
    )
    return summary


async def feature_status(
    *,
    chain: str | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> list[tuple[str, str, date | None, date | None, int]]:
    conditions = [ComputedFeature.chain_id == chain] if chain is not None else []
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    ComputedFeature.chain_id,
                    ComputedFeature.feature,
                    func.min(ComputedFeature.as_of_date),
                    func.max(ComputedFeature.as_of_date),
                    func.count(),
                )
                .where(*conditions)
                .group_by(ComputedFeature.chain_id, ComputedFeature.feature)
                .order_by(ComputedFeature.chain_id, ComputedFeature.feature)
            )
        ).all()
    return [
        (chain_code, feature, first_date, last_date, int(count))
        for chain_code, feature, first_date, last_date, count in rows
    ]
