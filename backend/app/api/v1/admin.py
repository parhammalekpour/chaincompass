from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.v1.auth.dependencies import SessionDependency, require_role
from app.core.config import settings
from app.db.models.auth import User
from app.db.models.ingestion import IngestionRun, RpcProbe, SeriesCoverage

router = APIRouter(prefix="/admin")
require_admin = require_role("admin")
AdminDependency = Annotated[User, Depends(require_admin)]
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_SECRET_PATTERN = re.compile(r"(?i)\b(api[_-]?key|token|password|secret)=\S+")


class DataFreshnessItem(BaseModel):
    chain: str
    metric: str
    source: str
    first_date: str | None
    last_date: str | None
    points: int
    missing: int
    status: str
    lag_days: int | None
    stale: bool


class DataFreshnessResponse(BaseModel):
    generated_at: datetime
    series: list[DataFreshnessItem]


class PipelineRun(BaseModel):
    job: str
    provider: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_upserted: int
    error: str | None


class LastSuccess(BaseModel):
    job: str
    provider: str
    finished_at: datetime


class PipelineResponse(BaseModel):
    runs: list[PipelineRun]
    last_success: list[LastSuccess]


class RpcLatest(BaseModel):
    chain: str
    provider_label: str
    checked_at: datetime
    ok: bool
    latency_ms: int | None
    block_height: int | None
    block_age_seconds: int | None
    error_code: str | None


class RpcChainSummary(BaseModel):
    chain: str
    success_ratio: str
    samples: int
    median_latency_ms: int | None


class RpcHealthResponse(BaseModel):
    generated_at: datetime
    latest: list[RpcLatest]
    summary_24h: list[RpcChainSummary]


def _short_safe_error(value: str | None) -> str | None:
    if not value:
        return None
    redacted = _URL_PATTERN.sub("[redacted-url]", value)
    redacted = _SECRET_PATTERN.sub(r"\1=[redacted]", redacted)
    return redacted[:180]


@router.get("/data-freshness", response_model=DataFreshnessResponse)
async def get_data_freshness(
    _: AdminDependency,
    session: SessionDependency,
) -> DataFreshnessResponse:
    generated_at = datetime.now(UTC)
    today = generated_at.date()
    coverages = (
        await session.scalars(
            select(SeriesCoverage).order_by(
                SeriesCoverage.chain_code,
                SeriesCoverage.metric_code,
                SeriesCoverage.source_code,
            )
        )
    ).all()
    return DataFreshnessResponse(
        generated_at=generated_at,
        series=[
            DataFreshnessItem(
                chain=row.chain_code,
                metric=row.metric_code,
                source=row.source_code,
                first_date=row.first_date.isoformat() if row.first_date else None,
                last_date=row.last_date.isoformat() if row.last_date else None,
                points=row.points,
                missing=row.missing_days,
                status=row.status,
                lag_days=(today - row.last_date).days if row.last_date else None,
                stale=(
                    (today - row.last_date).days > settings.ingestion_discontinued_days
                    if row.last_date
                    else False
                ),
            )
            for row in coverages
        ],
    )


@router.get("/pipeline", response_model=PipelineResponse)
async def get_pipeline(
    _: AdminDependency,
    session: SessionDependency,
) -> PipelineResponse:
    runs = (
        await session.scalars(
            select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(50)
        )
    ).all()
    success_rows = (
        await session.execute(
            select(
                IngestionRun.job,
                IngestionRun.provider,
                func.max(IngestionRun.finished_at),
            )
            .where(
                IngestionRun.status == "ok",
                IngestionRun.finished_at.is_not(None),
            )
            .group_by(IngestionRun.job, IngestionRun.provider)
            .order_by(IngestionRun.job, IngestionRun.provider)
        )
    ).all()
    last_success: list[LastSuccess] = []
    for job, provider, finished_at in success_rows:
        if finished_at is None:
            continue
        last_success.append(
            LastSuccess(job=job, provider=provider, finished_at=finished_at)
        )
    return PipelineResponse(
        runs=[
            PipelineRun(
                job=run.job,
                provider=run.provider,
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                rows_upserted=run.rows_upserted,
                error=_short_safe_error(run.error),
            )
            for run in runs
        ],
        last_success=last_success,
    )


@router.get("/rpc-health", response_model=RpcHealthResponse)
async def get_rpc_health(
    _: AdminDependency,
    session: SessionDependency,
) -> RpcHealthResponse:
    generated_at = datetime.now(UTC)
    latest_rows = (
        await session.scalars(
            select(RpcProbe).order_by(
                RpcProbe.chain_id,
                RpcProbe.provider_label,
                RpcProbe.checked_at.desc(),
            )
        )
    ).all()
    latest: list[RpcLatest] = []
    latest_seen: set[tuple[str, str]] = set()
    for row in latest_rows:
        key = (row.chain_id, row.provider_label)
        if key in latest_seen:
            continue
        latest_seen.add(key)
        latest.append(
            RpcLatest(
                chain=row.chain_id,
                provider_label=row.provider_label,
                checked_at=row.checked_at,
                ok=row.ok,
                latency_ms=row.latency_ms,
                block_height=row.block_height,
                block_age_seconds=row.block_age_seconds,
                error_code=row.error_code,
            )
        )

    recent_rows = (
        await session.scalars(
            select(RpcProbe).where(
                RpcProbe.checked_at >= generated_at - timedelta(hours=24)
            )
        )
    ).all()
    grouped: dict[str, list[RpcProbe]] = {}
    for row in recent_rows:
        grouped.setdefault(row.chain_id, []).append(row)
    summary: list[RpcChainSummary] = []
    for chain, rows in sorted(grouped.items()):
        latencies = sorted(
            Decimal(row.latency_ms) for row in rows if row.latency_ms is not None
        )
        middle = len(latencies) // 2
        if not latencies:
            median_latency = None
        elif len(latencies) % 2:
            median_latency = int(latencies[middle])
        else:
            median_latency = int(
                (latencies[middle - 1] + latencies[middle]) / Decimal(2)
            )
        successes = sum(row.ok for row in rows)
        success_ratio = Decimal(successes) / Decimal(len(rows))
        summary.append(
            RpcChainSummary(
                chain=chain,
                success_ratio=format(success_ratio, ".4f"),
                samples=len(rows),
                median_latency_ms=median_latency,
            )
        )
    return RpcHealthResponse(
        generated_at=generated_at,
        latest=latest,
        summary_24h=summary,
    )
