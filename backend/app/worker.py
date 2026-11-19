from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.ingestion import IngestionRun, Observation, SeriesCoverage
from app.db.session import SessionFactory
from app.ingest import run_updates_all
from app.ingestion.coingecko import (
    CoinGeckoClient,
    CoinGeckoRateLimited,
    CoinGeckoRequestFailed,
    configured_api_key,
    make_market_snapshot,
)

logger = logging.getLogger("app.worker")
RunStatus = Literal["ok", "partial", "failed", "rate_limited"]
JobHandler = Callable[[], Awaitable["JobOutcome"]]


@dataclass(frozen=True)
class JobOutcome:
    status: RunStatus
    rows_upserted: int = 0
    rows_rejected: int = 0
    details: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class JobSpec:
    name: str
    hour: int
    minute: int

    @property
    def schedule(self) -> str:
        return f"daily at {self.hour:02}:{self.minute:02} UTC"


JOB_SPECS = (
    JobSpec("coingecko_snapshot", 0, 5),
    JobSpec("update_all", 0, 30),
)


async def update_all_job() -> JobOutcome:
    result = await run_updates_all()
    if result:
        return JobOutcome(
            status="failed",
            details="provider run counts are recorded separately",
            error="one or more ingestion providers failed",
        )
    return JobOutcome(
        status="ok",
        details="provider run counts are recorded separately",
    )


async def coingecko_snapshot_job(
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    client: CoinGeckoClient | None = None,
) -> JobOutcome:
    owned_client = client is None
    api_client = client or CoinGeckoClient(api_key=configured_api_key())
    try:
        payload = await api_client.fetch()
    finally:
        if owned_client:
            await api_client.close()

    snapshot_at = datetime.now(UTC)
    snapshot = make_market_snapshot(payload, snapshot_at)
    details = f"snapshot_at={snapshot.snapshot_at.isoformat()}"
    if snapshot.missing_chains:
        details += f" missing_chains={','.join(snapshot.missing_chains)}"
    if not snapshot.values:
        return JobOutcome(
            status="failed",
            rows_rejected=snapshot.rows_rejected,
            details=details,
            error="CoinGecko returned no valid market caps",
        )

    rows = [
        {
            "chain_code": chain,
            "metric_code": "market_cap_usd",
            "source_code": "coingecko",
            "obs_date": snapshot.obs_date,
            "value": value,
            "fetched_at": snapshot.snapshot_at,
        }
        for chain, value in sorted(snapshot.values.items())
    ]
    async with session_factory() as session:
        statement = insert(Observation).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[
                "chain_code",
                "metric_code",
                "source_code",
                "obs_date",
            ],
            set_={
                "value": statement.excluded.value,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
        await session.execute(statement)
        for chain in snapshot.values:
            first, last, count = (
                await session.execute(
                    select(
                        func.min(Observation.obs_date),
                        func.max(Observation.obs_date),
                        func.count(Observation.obs_date),
                    ).where(
                        Observation.chain_code == chain,
                        Observation.metric_code == "market_cap_usd",
                        Observation.source_code == "coingecko",
                    )
                )
            ).one()
            coverage = await session.get(
                SeriesCoverage,
                (chain, "market_cap_usd", "coingecko"),
            )
            if coverage is None:
                coverage = SeriesCoverage(
                    chain_code=chain,
                    metric_code="market_cap_usd",
                    source_code="coingecko",
                )
                session.add(coverage)
            coverage.first_date = first
            coverage.last_date = last
            coverage.points = int(count)
            coverage.missing_days = (
                max(0, (last - first).days + 1 - int(count))
                if first is not None and last is not None
                else 0
            )
            coverage.last_success_at = snapshot.snapshot_at
            coverage.status = "ok"
            coverage.last_error = None
        await session.commit()

    return JobOutcome(
        status=(
            "partial" if snapshot.rows_rejected or snapshot.missing_chains else "ok"
        ),
        rows_upserted=len(rows),
        rows_rejected=snapshot.rows_rejected,
        details=details,
    )


JOB_HANDLERS: dict[str, JobHandler] = {
    "coingecko_snapshot": coingecko_snapshot_job,
    "update_all": update_all_job,
}


@asynccontextmanager
async def advisory_job_lock(
    job_name: str,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> AsyncIterator[bool]:
    async with session_factory() as session:
        acquired = bool(
            await session.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:job_name, 0))"),
                {"job_name": f"chaincompass.worker:{job_name}"},
            )
        )
        try:
            yield acquired
        finally:
            if acquired:
                await session.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:job_name, 0))"),
                    {"job_name": f"chaincompass.worker:{job_name}"},
                )


async def _create_run(
    job_name: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    run = IngestionRun(
        id=uuid4(),
        job=job_name,
        provider="worker",
        started_at=datetime.now(UTC),
        status="running",
    )
    async with session_factory() as session:
        session.add(run)
        await session.commit()
    return run.id


async def _finish_run(
    run_id: UUID,
    outcome: JobOutcome,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        run = await session.get(IngestionRun, run_id)
        if run is None:
            raise RuntimeError("worker run record disappeared")
        run.finished_at = datetime.now(UTC)
        run.status = outcome.status
        run.rows_upserted = outcome.rows_upserted
        run.rows_rejected = outcome.rows_rejected
        run.error = outcome.error[:300] if outcome.error else None
        run.details = outcome.details
        await session.commit()


async def execute_job(
    job_name: str,
    *,
    handlers: Mapping[str, JobHandler] = JOB_HANDLERS,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> int:
    handler = handlers.get(job_name)
    if handler is None:
        raise ValueError(f"unknown worker job: {job_name}")

    async with advisory_job_lock(job_name, session_factory) as acquired:
        if not acquired:
            logger.info("worker_job_skipped job=%s reason=already_running", job_name)
            print(f"{job_name}: skipped: already running")
            return 0

        run_id = await _create_run(job_name, session_factory)
        try:
            outcome = await handler()
        except CoinGeckoRateLimited as exc:
            outcome = JobOutcome(status="rate_limited", error=str(exc))
        except CoinGeckoRequestFailed as exc:
            outcome = JobOutcome(status="failed", error=str(exc))
        except Exception as exc:
            logger.error(
                "worker_job_failed job=%s error_type=%s",
                job_name,
                type(exc).__name__,
            )
            outcome = JobOutcome(
                status="failed",
                error=f"job raised {type(exc).__name__}",
            )
        try:
            await _finish_run(run_id, outcome, session_factory)
        except Exception as exc:
            logger.error(
                "worker_run_record_failed job=%s error_type=%s",
                job_name,
                type(exc).__name__,
            )
            return 1

    logger.info(
        "worker_job_finished job=%s status=%s rows_upserted=%s rows_rejected=%s",
        job_name,
        outcome.status,
        outcome.rows_upserted,
        outcome.rows_rejected,
    )
    summary = (
        f"{job_name}: status={outcome.status} "
        f"upserted={outcome.rows_upserted} rejected={outcome.rows_rejected}"
    )
    if outcome.details:
        summary += f" details={outcome.details}"
    if outcome.error:
        summary += f" error={outcome.error}"
    print(summary)
    return 1 if outcome.status in {"failed", "rate_limited"} else 0


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=UTC)
    for spec in JOB_SPECS:
        scheduler.add_job(
            execute_job,
            trigger=CronTrigger(
                hour=spec.hour,
                minute=spec.minute,
                timezone=UTC,
                jitter=20,
            ),
            id=spec.name,
            kwargs={"job_name": spec.name},
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    return scheduler


def format_job_list() -> str:
    return "\n".join(f"{spec.name}: {spec.schedule}" for spec in JOB_SPECS)


async def serve_scheduler(run_for_seconds: int | None = None) -> None:
    scheduler = build_scheduler()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(stop_signal, stop.set)
        except (NotImplementedError, RuntimeError):
            continue
    scheduler.start()
    logger.info("worker_scheduler_started")
    try:
        if run_for_seconds is None:
            await stop.wait()
        else:
            await asyncio.sleep(run_for_seconds)
    finally:
        scheduler.shutdown(wait=True)
        logger.info("worker_scheduler_stopped")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChainCompass ingestion worker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--once", choices=tuple(JOB_HANDLERS))
    group.add_argument("--run-for-seconds", type=int)
    args = parser.parse_args(argv)
    if args.run_for_seconds is not None and args.run_for_seconds <= 0:
        parser.error("--run-for-seconds must be greater than zero")
    return args


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(sys.argv[1:])
    if args.list:
        print(format_job_list())
        return
    if args.once:
        exit_code = asyncio.run(execute_job(args.once))
    else:
        try:
            asyncio.run(serve_scheduler(args.run_for_seconds))
            exit_code = 0
        except KeyboardInterrupt:
            logger.info("worker_interrupted")
            exit_code = 0
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
