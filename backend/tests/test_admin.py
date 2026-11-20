from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.db.models.auth import User
from app.db.models.ingestion import (
    Chain,
    ComputedFeature,
    DataSource,
    IngestionRun,
    MetricDefinition,
    Observation,
    RpcProbe,
    SeriesCoverage,
)
from app.ingestion.seed import seed_reference_data

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.usefixtures("clean_auth_tables", "clean_ingestion_tables"),
]


@pytest_asyncio.fixture(loop_scope="session")
async def clean_admin_reference_data(
    auth_session_factory: async_sessionmaker[AsyncSession],
):
    async def clear() -> None:
        async with auth_session_factory() as session:
            for model in (
                Observation,
                ComputedFeature,
                RpcProbe,
                SeriesCoverage,
                IngestionRun,
                MetricDefinition,
                DataSource,
                Chain,
            ):
                await session.execute(delete(model))
            await session.commit()

    await clear()
    yield
    await clear()


async def test_admin_routes_enforce_roles_and_return_monitoring_shapes(
    auth_client: AsyncClient,
    auth_session_factory: async_sessionmaker[AsyncSession],
    clean_admin_reference_data: None,
) -> None:
    del clean_admin_reference_data
    async with auth_session_factory() as session:
        await seed_reference_data(session)
        regular_user = User(email="regular-admin-test@example.com", role="user")
        admin_user = User(email="admin-admin-test@example.com", role="admin")
        session.add_all((regular_user, admin_user))
        today = datetime.now(UTC).date()
        session.add(
            SeriesCoverage(
                chain_code="eth",
                metric_code="market_cap_usd",
                source_code="coin_metrics",
                first_date=today - timedelta(days=100),
                last_date=today - timedelta(days=40),
                points=61,
                missing_days=0,
                status="ok",
            )
        )
        session.add_all(
            (
                IngestionRun(
                    id=uuid4(),
                    job="rpc_probe",
                    provider="worker",
                    started_at=datetime.now(UTC) - timedelta(minutes=2),
                    finished_at=datetime.now(UTC) - timedelta(minutes=1),
                    status="failed",
                    error="failed at https://rpc.example/path?api_key=secret",
                ),
                IngestionRun(
                    id=uuid4(),
                    job="rpc_probe",
                    provider="worker",
                    started_at=datetime.now(UTC) - timedelta(hours=1),
                    finished_at=datetime.now(UTC) - timedelta(minutes=59),
                    status="ok",
                    rows_upserted=4,
                ),
            )
        )
        session.add_all(
            (
                RpcProbe(
                    id=uuid4(),
                    chain_id="eth",
                    provider_label="publicnode",
                    checked_at=datetime.now(UTC) - timedelta(minutes=1),
                    ok=True,
                    latency_ms=20,
                    block_height=100,
                    block_age_seconds=10,
                ),
                RpcProbe(
                    id=uuid4(),
                    chain_id="eth",
                    provider_label="publicnode",
                    checked_at=datetime.now(UTC) - timedelta(minutes=2),
                    ok=False,
                    latency_ms=40,
                    error_code="http_429",
                ),
            )
        )
        await session.commit()

    freshness_url = "/api/v1/admin/data-freshness"
    assert (await auth_client.get(freshness_url)).status_code == 401
    regular_token = create_access_token(str(regular_user.id), "user")
    forbidden = await auth_client.get(
        freshness_url,
        headers={"Authorization": f"Bearer {regular_token}"},
    )
    assert forbidden.status_code == 403
    assert set(forbidden.json()["error"]) == {"code", "message"}

    admin_token = create_access_token(str(admin_user.id), "admin")
    headers = {"Authorization": f"Bearer {admin_token}"}
    freshness = await auth_client.get(freshness_url, headers=headers)
    assert freshness.status_code == 200
    fresh_body = freshness.json()
    assert fresh_body["generated_at"]
    assert len(fresh_body["series"]) == 1
    item = fresh_body["series"][0]
    assert item["chain"] == "eth"
    assert item["lag_days"] == 40
    assert item["stale"] is True
    assert item["missing"] == 0

    pipeline = await auth_client.get("/api/v1/admin/pipeline", headers=headers)
    assert pipeline.status_code == 200
    pipeline_body = pipeline.json()
    assert len(pipeline_body["runs"]) == 2
    assert pipeline_body["runs"][0]["error"] == ("failed at [redacted-url]")
    assert pipeline_body["last_success"][0]["job"] == "rpc_probe"

    rpc_health = await auth_client.get("/api/v1/admin/rpc-health", headers=headers)
    assert rpc_health.status_code == 200
    rpc_body = rpc_health.json()
    assert rpc_body["latest"][0]["provider_label"] == "publicnode"
    assert rpc_body["summary_24h"][0]["success_ratio"] == "0.5000"
    assert rpc_body["summary_24h"][0]["median_latency_ms"] == 30


async def test_set_role_cli_refuses_unknown_email(
    auth_session_factory: async_sessionmaker[AsyncSession],
    capsys: pytest.CaptureFixture[str],
    clean_admin_reference_data: None,
) -> None:
    del clean_admin_reference_data
    from app import users

    code = await users.execute_command(
        [
            "set-role",
            "--email",
            "unknown@example.com",
            "--role",
            "admin",
        ],
        session_factory=auth_session_factory,
    )
    assert code == 1
    assert "No user found" in capsys.readouterr().err
