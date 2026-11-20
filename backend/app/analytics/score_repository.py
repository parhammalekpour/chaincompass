from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.registry import get_feature_input
from app.analytics.score_config import (
    CHAINS,
    COMPONENTS,
    INSERT_BATCH_SIZE,
    REGIME_FEATURES,
    RISK_FLAGS,
    UPDATE_DAYS,
    VERSION,
)
from app.analytics.scoring import (
    AnalyticsOutput,
    FeatureRecord,
    RegimeValue,
    RiskFlagValue,
    ScoreValue,
    compute_analytics,
)
from app.db.models.health import HealthScore, MarketRegime, RiskFlag
from app.db.models.ingestion import ComputedFeature, IngestionRun
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)
ScoreComputeMode = Literal["backfill", "update"]


@dataclass(frozen=True)
class ScoreRowCounts:
    scores: int
    regimes: int
    risk_flags: int


@dataclass(frozen=True)
class ScoreComputeSummary:
    rows_upserted: int
    rows_deleted: int
    rows_by_chain: dict[str, ScoreRowCounts]


@dataclass(frozen=True)
class RiskFlagStatus:
    flag: str
    severity: str
    value: str
    threshold: str


@dataclass(frozen=True)
class ScoreStatus:
    chain: str
    first_date: date | None
    last_date: date | None
    rows: int
    latest_score: str | None
    coverage: str | None
    confidence_label: str | None
    regime: str | None
    vol_state: str | None
    flags: tuple[RiskFlagStatus, ...]


def _required_feature_names(chain: str) -> set[str]:
    names = {spec.feature for spec in COMPONENTS if chain in spec.chains}
    names.update(REGIME_FEATURES)
    names.update(
        spec.feature
        for spec in RISK_FLAGS
        if chain in spec.chains and spec.feature is not None
    )
    return names


def _json_decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _score_json(score: ScoreValue) -> tuple[dict[str, object], list[dict[str, object]]]:
    pillars: dict[str, object] = {
        pillar.name: {
            "score": _json_decimal(pillar.score),
            "weight_used": pillar.weight_used,
            "available": pillar.available,
        }
        for pillar in score.pillars
    }
    components: list[dict[str, object]] = []
    for component in score.components:
        item: dict[str, object] = {
            "feature": component.feature,
            "value": _json_decimal(component.value),
            "percentile": _json_decimal(component.percentile),
            "weight": component.weight,
            "direction": component.direction,
        }
        if component.derived_label is not None:
            item["derived_label"] = component.derived_label
        components.append(item)
    return pillars, components


def _score_row(score: ScoreValue) -> dict[str, object]:
    if score.score is None:
        raise ValueError("cannot persist a score below the configured coverage floor")
    pillars, components = _score_json(score)
    return {
        "chain_id": score.chain,
        "as_of_date": score.as_of_date,
        "version": score.version,
        "score": score.score,
        "coverage": score.coverage,
        "confidence_label": score.confidence_label,
        "pillars": pillars,
        "components": components,
    }


def _regime_row(regime: RegimeValue) -> dict[str, object]:
    return {
        "chain_id": regime.chain,
        "as_of_date": regime.as_of_date,
        "version": regime.version,
        "regime": regime.regime,
        "raw_regime": regime.raw_regime,
        "vol_state": regime.vol_state,
        "days_in_regime": regime.days_in_regime,
    }


def _risk_flag_row(flag: RiskFlagValue) -> dict[str, object]:
    return {
        "chain_id": flag.chain,
        "as_of_date": flag.as_of_date,
        "flag": flag.flag,
        "version": flag.version,
        "severity": flag.severity,
        "value": flag.value,
        "threshold": flag.threshold,
    }


async def _start_run(
    session_factory: async_sessionmaker[AsyncSession],
    mode: ScoreComputeMode,
    chain: str | None,
) -> IngestionRun:
    run = IngestionRun(
        id=uuid4(),
        job="scores",
        provider="analytics",
        started_at=datetime.now(UTC),
        status="running",
        details=f"mode={mode} chain={chain or 'all'} version={VERSION}",
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
            raise RuntimeError("score run record disappeared")
        run.finished_at = datetime.now(UTC)
        run.status = "failed"
        run.error = f"score computation failed ({error_type})"
        await session.commit()


async def _delete_version_rows(
    session: AsyncSession,
    model: type[HealthScore] | type[MarketRegime] | type[RiskFlag],
    chains: tuple[str, ...],
    mode: ScoreComputeMode,
    update_start: date,
    today: date,
) -> int:
    conditions = [
        model.chain_id.in_(chains),
        model.version == VERSION,
    ]
    if mode == "update":
        conditions.extend(
            (
                model.as_of_date >= update_start,
                model.as_of_date < today,
            )
        )
    count = await session.scalar(
        select(func.count()).select_from(model).where(*conditions)
    )
    await session.execute(delete(model).where(*conditions))
    return int(count or 0)


async def _insert_rows(
    session: AsyncSession,
    model: type[HealthScore] | type[MarketRegime] | type[RiskFlag],
    rows: list[dict[str, object]],
    conflict_columns: list[str],
    update_columns: tuple[str, ...],
) -> None:
    for offset in range(0, len(rows), INSERT_BATCH_SIZE):
        batch = rows[offset : offset + INSERT_BATCH_SIZE]
        statement = insert(model).values(batch)
        statement = statement.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={
                column: getattr(statement.excluded, column) for column in update_columns
            },
        )
        await session.execute(statement)


async def compute_scores_and_store(
    *,
    mode: ScoreComputeMode,
    chain: str | None = None,
    today: date | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    record_run: bool = True,
) -> ScoreComputeSummary:
    if chain is not None and chain not in CHAINS:
        raise ValueError(f"unsupported chain: {chain}")
    as_of_today = today or datetime.now(UTC).date()
    update_start = as_of_today - timedelta(days=UPDATE_DAYS)
    selected_chains = (chain,) if chain is not None else CHAINS
    run = await _start_run(session_factory, mode, chain) if record_run else None
    try:
        async with session_factory() as session:
            feature_names = set().union(
                *(_required_feature_names(code) for code in selected_chains)
            )
            rows = (
                await session.scalars(
                    select(ComputedFeature)
                    .where(
                        ComputedFeature.chain_id.in_(selected_chains),
                        ComputedFeature.feature.in_(feature_names),
                        ComputedFeature.as_of_date < as_of_today,
                    )
                    .order_by(
                        ComputedFeature.chain_id,
                        ComputedFeature.feature,
                        ComputedFeature.as_of_date,
                    )
                )
            ).all()
            grouped: dict[str, list[FeatureRecord]] = defaultdict(list)
            for row in rows:
                registered = get_feature_input(
                    row.chain_id,
                    row.source_metric,
                    row.source,
                )
                if registered is None:
                    continue
                grouped[row.chain_id].append(
                    FeatureRecord(
                        chain=row.chain_id,
                        feature=row.feature,
                        as_of_date=row.as_of_date,
                        value=row.value,
                        source_metric=row.source_metric,
                        source=row.source,
                    )
                )

            analytics_by_chain: dict[str, AnalyticsOutput] = {
                selected_chain: compute_analytics(
                    selected_chain,
                    grouped.get(selected_chain, []),
                )
                for selected_chain in selected_chains
            }

            if mode == "backfill":
                score_rows = [
                    _score_row(score)
                    for output in analytics_by_chain.values()
                    for score in output.scores
                    if score.score is not None
                ]
                regime_rows = [
                    _regime_row(regime)
                    for output in analytics_by_chain.values()
                    for regime in output.regimes
                ]
                flag_rows = [
                    _risk_flag_row(flag)
                    for output in analytics_by_chain.values()
                    for flag in output.risk_flags
                ]
            else:
                score_rows = [
                    _score_row(score)
                    for output in analytics_by_chain.values()
                    for score in output.scores
                    if score.score is not None
                    and update_start <= score.as_of_date < as_of_today
                ]
                regime_rows = [
                    _regime_row(regime)
                    for output in analytics_by_chain.values()
                    for regime in output.regimes
                    if update_start <= regime.as_of_date < as_of_today
                ]
                flag_rows = [
                    _risk_flag_row(flag)
                    for output in analytics_by_chain.values()
                    for flag in output.risk_flags
                    if update_start <= flag.as_of_date < as_of_today
                ]

            deleted = 0
            deleted += await _delete_version_rows(
                session,
                HealthScore,
                selected_chains,
                mode,
                update_start,
                as_of_today,
            )
            deleted += await _delete_version_rows(
                session,
                MarketRegime,
                selected_chains,
                mode,
                update_start,
                as_of_today,
            )
            deleted += await _delete_version_rows(
                session,
                RiskFlag,
                selected_chains,
                mode,
                update_start,
                as_of_today,
            )
            await _insert_rows(
                session,
                HealthScore,
                score_rows,
                ["chain_id", "as_of_date", "version"],
                (
                    "score",
                    "coverage",
                    "confidence_label",
                    "pillars",
                    "components",
                ),
            )
            await _insert_rows(
                session,
                MarketRegime,
                regime_rows,
                ["chain_id", "as_of_date", "version"],
                ("regime", "raw_regime", "vol_state", "days_in_regime"),
            )
            await _insert_rows(
                session,
                RiskFlag,
                flag_rows,
                ["chain_id", "as_of_date", "flag", "version"],
                ("severity", "value", "threshold"),
            )

            if run is not None:
                run_row = await session.get(IngestionRun, run.id)
                if run_row is None:
                    raise RuntimeError("score run record disappeared")
                run_row.finished_at = datetime.now(UTC)
                run_row.status = "ok"
                run_row.rows_upserted = (
                    len(score_rows) + len(regime_rows) + len(flag_rows)
                )
                run_row.rows_rejected = 0
                run_row.error = None
                run_row.details = (
                    f"mode={mode} chain={chain or 'all'} version={VERSION} "
                    f"scores={len(score_rows)} regimes={len(regime_rows)} "
                    f"risk_flags={len(flag_rows)} rows_deleted={deleted}"
                )
            await session.commit()
    except Exception as exc:
        if run is not None:
            logger.error(
                "score_computation_failed run_id=%s error_type=%s",
                run.id,
                type(exc).__name__,
            )
            try:
                await _mark_failed(run.id, type(exc).__name__, session_factory)
            except Exception as record_exc:
                logger.error(
                    "score_run_record_failed run_id=%s error_type=%s",
                    run.id,
                    type(record_exc).__name__,
                )
        raise

    counts_by_chain = {
        selected_chain: ScoreRowCounts(
            scores=sum(row["chain_id"] == selected_chain for row in score_rows),
            regimes=sum(row["chain_id"] == selected_chain for row in regime_rows),
            risk_flags=sum(row["chain_id"] == selected_chain for row in flag_rows),
        )
        for selected_chain in selected_chains
    }
    summary = ScoreComputeSummary(
        rows_upserted=len(score_rows) + len(regime_rows) + len(flag_rows),
        rows_deleted=deleted,
        rows_by_chain=counts_by_chain,
    )
    logger.info(
        "score_computation_finished mode=%s rows=%s",
        mode,
        summary.rows_upserted,
    )
    return summary


async def score_status(
    *,
    chain: str | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> list[ScoreStatus]:
    if chain is not None and chain not in CHAINS:
        raise ValueError(f"unsupported chain: {chain}")
    selected_chains = (chain,) if chain is not None else CHAINS
    statuses: list[ScoreStatus] = []
    async with session_factory() as session:
        for chain_code in selected_chains:
            first, last, count = (
                await session.execute(
                    select(
                        func.min(HealthScore.as_of_date),
                        func.max(HealthScore.as_of_date),
                        func.count(),
                    ).where(
                        HealthScore.chain_id == chain_code,
                        HealthScore.version == VERSION,
                    )
                )
            ).one()
            latest = (
                await session.scalars(
                    select(HealthScore)
                    .where(
                        HealthScore.chain_id == chain_code,
                        HealthScore.version == VERSION,
                    )
                    .order_by(HealthScore.as_of_date.desc())
                    .limit(1)
                )
            ).first()
            regime = None
            flags: tuple[RiskFlagStatus, ...] = ()
            if latest is not None:
                regime = await session.get(
                    MarketRegime,
                    (chain_code, latest.as_of_date, VERSION),
                )
                stored_flags = (
                    await session.scalars(
                        select(RiskFlag)
                        .where(
                            RiskFlag.chain_id == chain_code,
                            RiskFlag.as_of_date == latest.as_of_date,
                            RiskFlag.version == VERSION,
                        )
                        .order_by(RiskFlag.flag)
                    )
                ).all()
                flags = tuple(
                    RiskFlagStatus(
                        flag=row.flag,
                        severity=row.severity,
                        value=format(row.value, "f"),
                        threshold=format(row.threshold, "f"),
                    )
                    for row in stored_flags
                )
            statuses.append(
                ScoreStatus(
                    chain=chain_code,
                    first_date=first,
                    last_date=last,
                    rows=int(count),
                    latest_score=(
                        format(latest.score, "f") if latest is not None else None
                    ),
                    coverage=(
                        format(latest.coverage, "f") if latest is not None else None
                    ),
                    confidence_label=(
                        latest.confidence_label if latest is not None else None
                    ),
                    regime=regime.regime if regime is not None else None,
                    vol_state=regime.vol_state if regime is not None else None,
                    flags=flags,
                )
            )
    return statuses
