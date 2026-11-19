from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion import (
    Observation,
    SeriesCoverage,
)
from app.ingestion.provider import ChainContext, MetricProvider, Point


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        provider: MetricProvider,
        provider_code: str,
        source_code: str,
    ) -> None:
        self.session = session
        self.provider = provider
        self.provider_code = provider_code
        self.source_code = source_code

    def validate_point(
        self,
        chain: ChainContext,
        metric: str,
        point: Point,
        today: date,
    ) -> tuple[bool, str | None]:
        del chain, metric
        if point.date > today:
            return False, "future_date"
        if point.date == today:
            return False, "incomplete_today"
        if not point.value.is_finite():
            return False, "non_finite"
        if point.value < Decimal("0"):
            return False, "negative"
        try:
            exponent = point.value.as_tuple().exponent
            if isinstance(exponent, int) and exponent < -12:
                return False, "precision_over_12"
        except (InvalidOperation, ValueError):
            return False, "invalid_decimal"
        return True, None

    async def last_stored_date(
        self,
        chain_code: str,
        metric_code: str,
    ) -> date | None:
        result = await self.session.execute(
            select(func.max(Observation.obs_date)).where(
                and_(
                    Observation.chain_code == chain_code,
                    Observation.metric_code == metric_code,
                    Observation.source_code == self.source_code,
                )
            )
        )
        return result.scalar_one_or_none()

    async def upsert_points(
        self,
        chain: ChainContext,
        metric: str,
        points: list[Point],
        *,
        today: date,
    ) -> tuple[int, int]:
        fetched_at = datetime.now(UTC)
        unique: dict[date, Decimal] = {}
        rejected = 0
        for point in points:
            valid, _reason = self.validate_point(chain, metric, point, today)
            if not valid:
                rejected += 1
                continue
            if point.date in unique:
                rejected += 1
                continue
            unique[point.date] = point.value

        rows = [
            {
                "chain_code": chain.code,
                "metric_code": metric,
                "source_code": self.source_code,
                "obs_date": obs_date,
                "value": value,
                "fetched_at": fetched_at,
            }
            for obs_date, value in sorted(unique.items())
        ]
        if not rows:
            return 0, rejected
        batch_size = 500
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            stmt = insert(Observation).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "chain_code",
                    "metric_code",
                    "source_code",
                    "obs_date",
                ],
                set_={
                    "value": stmt.excluded.value,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await self.session.execute(stmt)
        await self.session.commit()
        return len(rows), rejected

    async def recompute_coverage(
        self,
        chain_code: str,
        metric_code: str,
    ) -> None:
        result = await self.session.execute(
            select(
                func.min(Observation.obs_date),
                func.max(Observation.obs_date),
                func.count(Observation.obs_date),
            ).where(
                and_(
                    Observation.chain_code == chain_code,
                    Observation.metric_code == metric_code,
                    Observation.source_code == self.source_code,
                )
            )
        )
        first, last, count = result.one()
        missing = 0
        if first is not None and last is not None:
            missing = max(0, (last - first).days + 1 - int(count))
        today = datetime.now(UTC).date()
        status: Literal["ok", "stale", "error", "never_run"] = "ok"
        if last is None:
            status = "never_run"
        elif (today - last).days > 2:
            status = "stale"
        coverage = await self.session.get(
            SeriesCoverage,
            (chain_code, metric_code, self.source_code),
        )
        if coverage is None:
            coverage = SeriesCoverage(
                chain_code=chain_code,
                metric_code=metric_code,
                source_code=self.source_code,
            )
            self.session.add(coverage)
        coverage.first_date = first
        coverage.last_date = last
        coverage.points = int(count)
        coverage.missing_days = missing
        coverage.last_success_at = datetime.now(UTC)
        coverage.last_error = None
        coverage.status = status
        await self.session.commit()

    async def record_error(
        self,
        chain_code: str,
        metric_code: str,
        error: str,
    ) -> None:
        coverage = await self.session.get(
            SeriesCoverage,
            (chain_code, metric_code, self.source_code),
        )
        if coverage is None:
            coverage = SeriesCoverage(
                chain_code=chain_code,
                metric_code=metric_code,
                source_code=self.source_code,
                status="error",
            )
            self.session.add(coverage)
        coverage.last_error = error[:300]
        coverage.status = "error"
        await self.session.commit()
