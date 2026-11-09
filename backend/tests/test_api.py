from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, Query
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def application() -> FastAPI:
    test_app = create_app()

    @test_app.get("/_validation-probe")
    async def validation_probe(count: int = Query(ge=1)) -> dict[str, int]:
        return {"count": count}

    @test_app.get("/_error-probe")
    async def error_probe() -> None:
        raise RuntimeError("internal detail")

    return test_app


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_health_returns_expected_shape_when_database_is_up_or_down(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "health-test-request"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "health-test-request"
    payload = response.json()
    assert set(payload) == {"status", "db", "version"}
    assert payload["db"] in {"ok", "down"}
    assert payload["status"] == ("ok" if payload["db"] == "ok" else "degraded")
    assert isinstance(payload["version"], str)
    assert payload["version"]


@pytest.mark.asyncio
async def test_unknown_route_returns_consistent_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not Found"}


@pytest.mark.asyncio
async def test_validation_error_returns_consistent_error(client: AsyncClient) -> None:
    response = await client.get("/_validation-probe?count=invalid")

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Request validation failed",
    }


@pytest.mark.asyncio
async def test_unexpected_error_is_generic_and_keeps_request_id(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/_error-probe",
        headers={"X-Request-ID": "error-test-request"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "An unexpected error occurred",
    }
    assert response.headers["X-Request-ID"] == "error-test-request"
