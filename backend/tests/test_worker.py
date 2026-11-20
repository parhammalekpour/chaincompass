from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.db.models.ingestion import IngestionRun, Observation, RpcProbe, SeriesCoverage
from app.ingestion.coingecko import (
    CoinGeckoClient,
    make_market_snapshot,
    parse_market_caps,
    previous_utc_date,
)
from app.ingestion.rpc import prune_probes
from app.ingestion.seed import seed_reference_data
from app.worker import (
    JOB_SPECS,
    JobOutcome,
    advisory_job_lock,
    build_scheduler,
    execute_job,
    format_job_list,
    rpc_probe_job,
    scores_job,
)


def test_coingecko_parser_accepts_only_positive_finite_market_caps() -> None:
    values, rejected = parse_market_caps(
        [
            {"id": "bitcoin", "market_cap": "100.25"},
            {"id": "ethereum", "market_cap": 0},
            {"id": "solana", "market_cap": None},
            {"id": "binancecoin", "market_cap": "NaN"},
            {"id": "unknown", "market_cap": "10"},
            {"id": ["not", "hashable"], "market_cap": "10"},
            {"id": "solana", "market_cap": "1e26"},
        ]
    )
    assert values == {"btc": Decimal("100.25")}
    assert rejected == 6


def test_snapshot_date_uses_previous_utc_day() -> None:
    timestamp = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    assert previous_utc_date(timestamp) == datetime(2025, 12, 31).date()
    offset_timestamp = datetime(
        2026,
        1,
        1,
        2,
        5,
        tzinfo=timezone(timedelta(hours=3, minutes=30)),
    )
    assert previous_utc_date(offset_timestamp) == datetime(2025, 12, 30).date()
    with pytest.raises(ValueError, match="timezone-aware"):
        previous_utc_date(datetime(2026, 1, 1))


@pytest.mark.asyncio
async def test_coingecko_client_makes_single_markets_request() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {"id": "bitcoin", "market_cap": 100},
                {"id": "ethereum", "market_cap": 200},
            ],
            request=request,
        )

    client = CoinGeckoClient(transport=httpx.MockTransport(handler))
    try:
        payload = await client.fetch()
    finally:
        await client.close()
    assert len(requests) == 1
    assert requests[0].url.path == "/api/v3/coins/markets"
    assert requests[0].url.params["vs_currency"] == "usd"
    assert requests[0].url.params["ids"] == "bitcoin,ethereum,solana,binancecoin"
    assert requests[0].headers["User-Agent"].startswith("ChainCompass/")
    snapshot = make_market_snapshot(
        payload,
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    )
    assert snapshot.obs_date == datetime(2025, 12, 31).date()
    assert snapshot.values == {"btc": Decimal(100), "eth": Decimal(200)}


@pytest.mark.asyncio
async def test_coingecko_429_records_rate_limited_without_observations(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await seed_reference_data(session)

    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            429,
            headers={"Retry-After": "0"},
            request=request,
        )

    client = CoinGeckoClient(transport=httpx.MockTransport(handler))

    async def snapshot_handler() -> JobOutcome:
        from app.worker import coingecko_snapshot_job

        return await coingecko_snapshot_job(
            session_factory=auth_session_factory,
            client=client,
        )

    try:
        result = await execute_job(
            "coingecko_snapshot",
            handlers={"coingecko_snapshot": snapshot_handler},
            session_factory=auth_session_factory,
        )
    finally:
        await client.close()

    assert result == 1
    assert requests == 4
    async with auth_session_factory() as session:
        observations = (
            await session.scalars(
                select(Observation).where(
                    Observation.source_code == "coingecko",
                    Observation.metric_code == "market_cap_usd",
                )
            )
        ).all()
        runs = (
            await session.scalars(
                select(IngestionRun).where(IngestionRun.job == "coingecko_snapshot")
            )
        ).all()
    assert observations == []
    assert len(runs) == 1
    assert runs[0].status == "rate_limited"
    assert "HTTP 429" in (runs[0].error or "")


@pytest.mark.asyncio
async def test_coingecko_snapshot_persists_four_source_scoped_caps(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await seed_reference_data(session)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"id": "bitcoin", "market_cap": "100.123456789012"},
                {"id": "ethereum", "market_cap": "200"},
                {"id": "solana", "market_cap": "300"},
                {"id": "binancecoin", "market_cap": "400"},
            ],
            request=request,
        )

    client = CoinGeckoClient(transport=httpx.MockTransport(handler))

    async def snapshot_handler() -> JobOutcome:
        from app.worker import coingecko_snapshot_job

        return await coingecko_snapshot_job(
            session_factory=auth_session_factory,
            client=client,
        )

    try:
        assert (
            await execute_job(
                "coingecko_snapshot",
                handlers={"coingecko_snapshot": snapshot_handler},
                session_factory=auth_session_factory,
            )
            == 0
        )
    finally:
        await client.close()

    async with auth_session_factory() as session:
        rows = (
            await session.scalars(
                select(Observation).where(
                    Observation.source_code == "coingecko",
                    Observation.metric_code == "market_cap_usd",
                )
            )
        ).all()
        run = await session.scalar(
            select(IngestionRun).where(IngestionRun.job == "coingecko_snapshot")
        )
        coverage = (
            await session.scalars(
                select(SeriesCoverage).where(
                    SeriesCoverage.source_code == "coingecko",
                    SeriesCoverage.metric_code == "market_cap_usd",
                )
            )
        ).all()
    assert {row.chain_code for row in rows} == {"btc", "eth", "sol", "bnb"}
    assert {row.obs_date for row in rows} == {
        datetime.now(UTC).date() - timedelta(days=1)
    }
    assert all(isinstance(row.value, Decimal) for row in rows)
    assert run is not None
    assert run.details is not None and run.details.startswith("snapshot_at=")
    assert run.rows_upserted == 4
    assert {row.chain_code for row in coverage} == {"btc", "eth", "sol", "bnb"}
    assert all(row.points == 1 and row.status == "ok" for row in coverage)


@pytest.mark.asyncio
async def test_failed_worker_job_is_recorded_and_next_job_runs(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async def failing() -> JobOutcome:
        raise RuntimeError("provider payload must not be logged")

    succeeded: list[bool] = []

    async def succeeding() -> JobOutcome:
        succeeded.append(True)
        return JobOutcome(status="ok")

    assert (
        await execute_job(
            "failure",
            handlers={"failure": failing},
            session_factory=auth_session_factory,
        )
        == 1
    )
    assert (
        await execute_job(
            "success",
            handlers={"success": succeeding},
            session_factory=auth_session_factory,
        )
        == 0
    )
    assert succeeded == [True]
    async with auth_session_factory() as session:
        runs = (
            await session.scalars(select(IngestionRun).order_by(IngestionRun.job))
        ).all()
    assert [(run.job, run.status) for run in runs] == [
        ("failure", "failed"),
        ("success", "ok"),
    ]
    assert runs[0].error == "job raised RuntimeError"


@pytest.mark.asyncio
async def test_failed_rpc_probe_is_recorded_without_blocking_next_job(
    auth_session_factory,
    clean_ingestion_tables,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ingestion.rpc import RpcProbeResult

    checked_at = datetime.now(UTC)
    results = [
        RpcProbeResult(
            chain_id=chain,
            provider_label=chain,
            checked_at=checked_at,
            ok=chain != "btc",
            latency_ms=10,
            block_height=1,
            block_age_seconds=None,
            error_code=None if chain != "btc" else "http_429",
        )
        for chain in ("btc", "eth", "sol", "bnb")
    ]

    async def fake_rpc_run() -> list[RpcProbeResult]:
        return results

    monkeypatch.setattr("app.worker.run_rpc_probe_job", fake_rpc_run)
    next_job_ran: list[bool] = []

    async def next_job() -> JobOutcome:
        next_job_ran.append(True)
        return JobOutcome(status="ok")

    assert (
        await execute_job(
            "rpc_probe",
            handlers={"rpc_probe": rpc_probe_job},
            session_factory=auth_session_factory,
        )
        == 0
    )
    assert (
        await execute_job(
            "after_rpc_probe",
            handlers={"after_rpc_probe": next_job},
            session_factory=auth_session_factory,
        )
        == 0
    )
    assert next_job_ran == [True]
    async with auth_session_factory() as session:
        runs = (
            await session.scalars(select(IngestionRun).order_by(IngestionRun.job))
        ).all()
    assert [(run.job, run.status) for run in runs] == [
        ("after_rpc_probe", "ok"),
        ("rpc_probe", "partial"),
    ]


def test_worker_job_registry_and_schedules() -> None:
    assert [(job.name, job.hour, job.minute) for job in JOB_SPECS] == [
        ("coingecko_snapshot", 0, 5),
        ("update_all", 0, 30),
        ("rpc_probe", 0, 0),
        ("prune_rpc_probes", 0, 45),
        ("scores", 1, 0),
    ]
    assert format_job_list().splitlines() == [
        "coingecko_snapshot: daily at 00:05 UTC",
        "update_all: daily at 00:30 UTC",
        "rpc_probe: every 15 minutes",
        "prune_rpc_probes: daily at 00:45 UTC",
        "scores: daily at 01:00 UTC",
    ]
    scheduler = build_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {
        "coingecko_snapshot",
        "update_all",
        "rpc_probe",
        "prune_rpc_probes",
        "scores",
    }
    assert all(job.max_instances == 1 and job.coalesce for job in jobs.values())
    assert all(job.misfire_grace_time == 3600 for job in jobs.values())
    assert all(job.trigger.jitter == 20 for job in jobs.values())


@pytest.mark.asyncio
async def test_scores_job_runs_feature_update_before_score_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import worker
    from app.analytics.repository import ComputeSummary
    from app.analytics.score_repository import (
        ScoreComputeSummary,
        ScoreRowCounts,
    )

    calls: list[str] = []

    async def compute_features(**kwargs):
        calls.append(f"features:{kwargs['mode']}")
        return ComputeSummary(
            rows_upserted=10,
            rows_deleted=3,
            rows_by_chain={"btc": 10},
        )

    async def compute_scores(**kwargs):
        calls.append(f"scores:{kwargs['mode']}:{kwargs['record_run']}")
        return ScoreComputeSummary(
            rows_upserted=5,
            rows_deleted=2,
            rows_by_chain={
                "btc": ScoreRowCounts(scores=1, regimes=3, risk_flags=1),
            },
        )

    monkeypatch.setattr(worker, "compute_features_and_store", compute_features)
    monkeypatch.setattr(worker, "compute_scores_and_store", compute_scores)

    outcome = await scores_job()

    assert calls == ["features:update", "scores:update:False"]
    assert outcome == JobOutcome(
        status="ok",
        rows_upserted=5,
        details="feature_rows=10 score/regime/flag_rows=btc:1/3/1",
    )


@pytest.mark.asyncio
async def test_failed_scores_job_is_recorded_and_next_job_runs(
    auth_session_factory,
    clean_ingestion_tables,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import worker

    async def failing_features(**kwargs):
        raise RuntimeError(f"failure in {kwargs['mode']}")

    next_job_ran: list[bool] = []

    async def next_job() -> JobOutcome:
        next_job_ran.append(True)
        return JobOutcome(status="ok")

    monkeypatch.setattr(worker, "compute_features_and_store", failing_features)

    assert (
        await execute_job(
            "scores",
            handlers={"scores": worker.scores_job},
            session_factory=auth_session_factory,
        )
        == 1
    )
    assert (
        await execute_job(
            "after_scores",
            handlers={"after_scores": next_job},
            session_factory=auth_session_factory,
        )
        == 0
    )
    assert next_job_ran == [True]
    async with auth_session_factory() as session:
        run = await session.scalar(
            select(IngestionRun).where(IngestionRun.job == "scores")
        )
    assert run is not None
    assert run.status == "failed"
    assert run.error == "job raised RuntimeError"


@pytest.mark.asyncio
async def test_postgres_advisory_lock_is_non_blocking(
    auth_session_factory,
) -> None:
    async with advisory_job_lock("advisory-lock-test", auth_session_factory) as first:
        assert first
        async with advisory_job_lock(
            "advisory-lock-test",
            auth_session_factory,
        ) as second:
            assert not second


@pytest.mark.asyncio
async def test_rpc_probe_retention_deletes_only_rows_older_than_threshold(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await seed_reference_data(session)
        now = datetime.now(UTC)
        session.add_all(
            (
                RpcProbe(
                    chain_id="eth",
                    provider_label="publicnode",
                    checked_at=now - timedelta(days=31),
                    ok=True,
                ),
                RpcProbe(
                    chain_id="eth",
                    provider_label="publicnode",
                    checked_at=now - timedelta(days=29),
                    ok=True,
                ),
            )
        )
        await session.commit()

    deleted = await prune_probes(30, session_factory=auth_session_factory)
    assert deleted == 1
    async with auth_session_factory() as session:
        rows = (await session.scalars(select(RpcProbe))).all()
    assert len(rows) == 1
