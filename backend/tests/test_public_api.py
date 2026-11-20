from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.health import HealthScore, MarketRegime, RiskFlag
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
from app.db.session import get_session
from app.ingestion.seed import seed_reference_data
from app.main import create_app
from app.services.rate_limit import reset_rate_limiter

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _clear_public_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        for model in (
            RiskFlag,
            MarketRegime,
            HealthScore,
            ComputedFeature,
            Observation,
            RpcProbe,
            SeriesCoverage,
            IngestionRun,
            MetricDefinition,
            DataSource,
            Chain,
        ):
            await session.execute(delete(model))
        await session.commit()


@pytest_asyncio.fixture(loop_scope="session")
async def public_session_factory(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    await _clear_public_data(auth_session_factory)
    yield auth_session_factory
    await _clear_public_data(auth_session_factory)


@pytest_asyncio.fixture(loop_scope="session")
async def public_client(
    public_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    reset_rate_limiter()
    application: FastAPI = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with public_session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client
    application.dependency_overrides.clear()


def _score(
    chain: str,
    as_of: date,
    score: str,
    coverage: str,
) -> HealthScore:
    coverage_value = Decimal(coverage)
    confidence = (
        "High"
        if coverage_value >= Decimal("0.80")
        else "Medium"
        if coverage_value >= Decimal("0.50")
        else "Low"
    )
    return HealthScore(
        chain_id=chain,
        as_of_date=as_of,
        version="v1",
        score=Decimal(score),
        coverage=coverage_value,
        confidence_label=confidence,
        pillars={
            "market_condition": {
                "score": "55.000000000000",
                "weight_used": 30,
                "available": True,
            }
        },
        components=[
            {
                "feature": "drawdown_365d",
                "value": "-0.200000000000",
                "percentile": "55.000000000000",
                "weight": 10,
                "direction": "higher_is_better",
            }
        ],
    )


def _regime(chain: str, as_of: date, regime: str) -> MarketRegime:
    return MarketRegime(
        chain_id=chain,
        as_of_date=as_of,
        version="v1",
        regime=regime,
        raw_regime=regime,
        vol_state="normal",
        days_in_regime=1,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_public_data(
    public_session_factory: async_sessionmaker[AsyncSession],
) -> date:
    async with public_session_factory() as session:
        await seed_reference_data(session)
        today = datetime.now(UTC).date()
        latest = today - timedelta(days=1)
        previous = today - timedelta(days=2)
        old_date = date(2020, 3, 13)

        session.add_all(
            [
                _score("btc", old_date, "42.50", "0.7000"),
                _score("btc", previous, "55.50", "0.7000"),
                _score("btc", latest, "53.75", "0.6000"),
                _score("eth", latest, "61.00", "0.9000"),
                _regime("btc", old_date, "stress"),
                _regime("btc", previous, "uptrend"),
                _regime("btc", latest, "uptrend"),
                _regime("eth", latest, "range"),
                _regime("btc", date(2026, 1, 1), "uptrend"),
                _regime("btc", date(2026, 1, 2), "uptrend"),
                _regime("btc", date(2026, 1, 4), "uptrend"),
                _regime("btc", date(2026, 1, 5), "stress"),
                RiskFlag(
                    chain_id="btc",
                    as_of_date=latest,
                    flag="deep_drawdown",
                    version="v1",
                    severity="medium",
                    value=Decimal("-0.420000000000"),
                    threshold=Decimal("-0.400000000000"),
                ),
            ]
        )
        session.add_all(
            [
                Observation(
                    chain_code="btc",
                    metric_code="price_close_usd",
                    source_code="binance",
                    obs_date=old_date,
                    value=Decimal("50000.000000000000"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="price_close_usd",
                    source_code="binance",
                    obs_date=today - timedelta(days=3),
                    value=Decimal("80000.000000000000"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="price_close_usd",
                    source_code="binance",
                    obs_date=latest,
                    value=Decimal("81000.000000000000"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="fees_usd",
                    source_code="blockchain_info",
                    obs_date=today - timedelta(days=3),
                    value=Decimal("10.000000000000"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="fees_usd",
                    source_code="blockchain_info",
                    obs_date=latest,
                    value=Decimal("12.000000000000"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="market_cap_usd",
                    source_code="coingecko",
                    obs_date=latest,
                    value=Decimal("1000000000000.000000000000"),
                    fetched_at=datetime.now(UTC),
                ),
            ]
        )
        session.add_all(
            [
                ComputedFeature(
                    chain_id="btc",
                    feature="ret_30d",
                    as_of_date=old_date,
                    value=Decimal("-0.123400000000"),
                    n_obs=2,
                    window_days=30,
                    source_metric="price_close_usd",
                    source="binance",
                ),
                ComputedFeature(
                    chain_id="btc",
                    feature="ret_30d",
                    as_of_date=latest,
                    value=Decimal("0.025000000000"),
                    n_obs=2,
                    window_days=30,
                    source_metric="price_close_usd",
                    source="binance",
                ),
            ]
        )
        session.add_all(
            [
                SeriesCoverage(
                    chain_code="btc",
                    metric_code="price_close_usd",
                    source_code="binance",
                    first_date=old_date,
                    last_date=latest,
                    points=3,
                    missing_days=0,
                    status="ok",
                ),
                SeriesCoverage(
                    chain_code="btc",
                    metric_code="fees_usd",
                    source_code="blockchain_info",
                    first_date=today - timedelta(days=3),
                    last_date=latest,
                    points=2,
                    missing_days=1,
                    status="ok",
                ),
                SeriesCoverage(
                    chain_code="btc",
                    metric_code="market_cap_usd",
                    source_code="coingecko",
                    first_date=latest,
                    last_date=latest,
                    points=1,
                    missing_days=0,
                    status="ok",
                ),
                SeriesCoverage(
                    chain_code="btc",
                    metric_code="tvl_usd",
                    source_code="defillama",
                    points=0,
                    missing_days=0,
                    status="unavailable",
                ),
                SeriesCoverage(
                    chain_code="bnb",
                    metric_code="active_addresses",
                    source_code="coin_metrics",
                    points=0,
                    missing_days=0,
                    status="discontinued",
                    last_error="PRIVATE_INGESTION_ERROR_SENTINEL",
                ),
            ]
        )
        await session.commit()
        return latest


async def test_chains_and_detail_expose_partial_score_and_decimal_strings(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    chains_response = await public_client.get("/api/v1/chains")
    assert chains_response.status_code == 200
    assert chains_response.headers["Cache-Control"] == (
        "public, max-age=300, stale-while-revalidate=600"
    )
    chains = chains_response.json()
    assert [row["slug"] for row in chains["chains"]] == ["btc", "eth", "sol", "bnb"]
    btc_summary = chains["chains"][0]
    assert btc_summary["score"]["as_of_date"] == seeded_public_data.isoformat()
    assert btc_summary["score"]["coverage_max"] == "0.7000"
    assert btc_summary["score"]["coverage"] == "0.6000"
    assert btc_summary["score"]["is_partial"] is True
    assert isinstance(btc_summary["price"]["close_usd"], str)
    assert btc_summary["regime"]["label"] == "uptrend"
    assert btc_summary["flags"] == [{"flag": "deep_drawdown", "severity": "medium"}]
    assert not {"runs", "rpc", "admin", "error"} & set(btc_summary)

    detail_response = await public_client.get("/api/v1/chains/btc")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["analysis_only"] is True
    assert detail["score"]["value"] == "53.75"
    assert detail["score"]["components"][0]["value"] == "-0.200000000000"
    assert detail["last_full_coverage"] == {
        "value": "55.50",
        "as_of_date": (seeded_public_data - timedelta(days=1)).isoformat(),
        "coverage": "0.7000",
        "confidence_label": "Medium",
    }
    assert detail["flags"][0]["value"] == "-0.420000000000"
    assert detail["flags"][0]["threshold"] == "-0.400000000000"
    assert any(
        row["metric"] == "fees_usd"
        and row["derived"] is True
        and row["role"] == "score"
        for row in detail["data_coverage"]
    )

    eth = (await public_client.get("/api/v1/chains/eth")).json()
    assert eth["score"]["coverage_max"] == "0.9000"
    assert eth["score"]["is_partial"] is False
    assert eth["score"]["confidence_label"] == "High"
    assert "last_full_coverage" not in eth


async def test_point_in_time_snapshots_and_unknown_chain_errors(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    del seeded_public_data
    snapshot = await public_client.get(
        "/api/v1/chains/btc",
        params={"as_of": "2020-03-13"},
    )
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["score"]["value"] == "42.50"
    assert body["price"]["as_of_date"] == "2020-03-13"
    assert body["price"]["ret_30d"] == "-0.123400000000"
    market_cap = next(
        row
        for row in body["data_coverage"]
        if row["metric"] == "market_cap_usd" and row["source"] == "coingecko"
    )
    assert market_cap["last_date"] is None

    missing = await public_client.get(
        "/api/v1/chains/btc",
        params={"as_of": "2020-03-14"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "no_snapshot_for_date"

    future_date = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    future = await public_client.get(
        "/api/v1/chains/btc",
        params={"as_of": future_date},
    )
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "future_as_of_date"

    unknown = await public_client.get("/api/v1/chains/unknown")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "chain_not_found"


async def test_history_validation_and_ascending_order(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    history = await public_client.get(
        "/api/v1/chains/btc/score-history",
        params={"from": "2020-03-01", "to": "2026-11-19"},
    )
    assert history.status_code == 200
    dates = [item["as_of_date"] for item in history.json()["items"]]
    assert dates == sorted(dates)
    assert "2020-03-13" in dates

    invalid_order = await public_client.get(
        "/api/v1/chains/btc/score-history",
        params={"from": "2026-11-20", "to": "2026-11-19"},
    )
    assert invalid_order.status_code == 422
    assert invalid_order.json()["error"]["code"] == "invalid_date_range"

    too_long = await public_client.get(
        "/api/v1/chains/btc/score-history",
        params={"from": "2000-01-01", "to": seeded_public_data.isoformat()},
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "range_too_large"

    invalid_date = await public_client.get(
        "/api/v1/chains/btc/score-history",
        params={"from": "not-a-date"},
    )
    assert invalid_date.status_code == 422
    assert invalid_date.json()["error"]["code"] == "validation_error"


async def test_regime_segments_split_on_label_change_and_gaps(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    del seeded_public_data
    response = await public_client.get(
        "/api/v1/chains/btc/regimes",
        params={"from": "2026-01-01", "to": "2026-01-05"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["segments"] == [
        {
            "regime": "uptrend",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "days": 2,
        },
        {
            "regime": "uptrend",
            "start_date": "2026-01-04",
            "end_date": "2026-01-04",
            "days": 1,
        },
        {
            "regime": "stress",
            "start_date": "2026-01-05",
            "end_date": "2026-01-05",
            "days": 1,
        },
    ]
    assert body["latest_vol_state"] == "normal"


async def test_series_allowlist_context_derived_gaps_and_unavailable(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    response = await public_client.get(
        "/api/v1/chains/btc/series",
        params={"metric": "fees_usd"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["role"] == "score"
    assert body["meta"]["derived"] is True
    assert body["meta"]["points"] == 2
    assert body["meta"]["missing"] == 1
    assert len(body["points"]) == 2
    assert all(isinstance(point["value"], str) for point in body["points"])

    context = await public_client.get(
        "/api/v1/chains/btc/series",
        params={"metric": "market_cap_usd", "source": "coingecko"},
    )
    assert context.status_code == 200
    assert context.json()["meta"]["role"] == "context"

    source_required = await public_client.get(
        "/api/v1/chains/btc/series",
        params={"metric": "market_cap_usd"},
    )
    assert source_required.status_code == 422
    assert source_required.json()["error"]["code"] == "source_required"
    assert "coin_metrics" in source_required.json()["error"]["message"]

    legacy = await public_client.get(
        "/api/v1/chains/bnb/series",
        params={"metric": "active_addresses", "source": "coin_metrics"},
    )
    assert legacy.status_code == 404
    assert legacy.json()["error"]["code"] == "series_not_available"
    assert "legacy bnb asset" in legacy.json()["error"]["message"].lower()

    unavailable = await public_client.get(
        "/api/v1/chains/btc/series",
        params={"metric": "tvl_usd", "source": "defillama"},
    )
    assert unavailable.status_code == 404
    assert unavailable.json()["error"]["code"] == "series_not_available"

    unknown = await public_client.get(
        "/api/v1/chains/btc/series",
        params={"metric": "secret_metric"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "series_not_available"
    del seeded_public_data


async def test_series_point_limit(
    public_client: AsyncClient,
    public_session_factory: async_sessionmaker[AsyncSession],
    seeded_public_data: date,
) -> None:
    del seeded_public_data
    first = date(2000, 1, 1)
    async with public_session_factory() as session:
        session.add_all(
            [
                Observation(
                    chain_code="btc",
                    metric_code="volume_usd",
                    source_code="binance",
                    obs_date=first + timedelta(days=offset),
                    value=Decimal("1.000000000000"),
                    fetched_at=datetime.now(UTC),
                )
                for offset in range(5001)
            ]
        )
        await session.commit()

    response = await public_client.get(
        "/api/v1/chains/btc/series",
        params={
            "metric": "volume_usd",
            "from": first.isoformat(),
            "to": (first + timedelta(days=5000)).isoformat(),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_points"


async def test_empty_chain_returns_nulls_and_empty_collections(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    del seeded_public_data
    response = await public_client.get("/api/v1/chains/sol")
    assert response.status_code == 200
    body = response.json()
    assert body["score"] is None
    assert body["regime"] is None
    assert body["flags"] == []

    history = await public_client.get("/api/v1/chains/sol/score-history")
    assert history.status_code == 200
    assert history.json()["items"] == []

    bnb = (await public_client.get("/api/v1/chains/bnb")).json()
    legacy = next(
        row
        for row in bnb["data_coverage"]
        if row["metric"] == "active_addresses" and row["source"] == "coin_metrics"
    )
    assert legacy["role"] == "context"
    assert legacy["status"] == "discontinued"
    assert legacy["derived"] is False
    assert "legacy bnb asset" in legacy["note"].lower()
    assert "last_error" not in str(bnb)


async def test_public_routes_do_not_expose_internal_fields_or_provider_errors(
    public_client: AsyncClient,
    seeded_public_data: date,
) -> None:
    del seeded_public_data
    responses = [
        await public_client.get("/api/v1/chains"),
        await public_client.get("/api/v1/chains/btc"),
        await public_client.get("/api/v1/chains/bnb"),
        await public_client.get("/api/v1/chains/btc/score-history"),
        await public_client.get("/api/v1/chains/btc/regimes"),
        await public_client.get(
            "/api/v1/chains/btc/series",
            params={"metric": "fees_usd"},
        ),
        await public_client.get(
            "/api/v1/chains/bnb/series",
            params={"metric": "active_addresses", "source": "coin_metrics"},
        ),
        await public_client.get("/api/v1/methodology"),
    ]
    assert [response.status_code for response in responses] == [
        200,
        200,
        200,
        200,
        200,
        200,
        404,
        200,
    ]

    private_fields = {
        "admin",
        "ingestion_run",
        "ingestion_runs",
        "last_error",
        "provider_error",
        "rpc",
        "rpc_probe",
        "rpc_probes",
        "run_id",
        "runs",
    }

    def field_names(value: object) -> set[str]:
        if isinstance(value, dict):
            return {str(key).casefold() for key in value} | set().union(
                *(field_names(item) for item in value.values())
            )
        if isinstance(value, list):
            return set().union(*(field_names(item) for item in value))
        return set()

    for response in responses:
        body = response.json()
        assert not private_fields & field_names(body)
        assert "PRIVATE_INGESTION_ERROR_SENTINEL" not in response.text


async def test_public_cache_rate_limit_and_decimal_openapi_schema(
    public_client: AsyncClient,
) -> None:
    methodology = await public_client.get("/api/v1/methodology")
    assert methodology.status_code == 200
    assert methodology.headers["Cache-Control"] == (
        "public, max-age=300, stale-while-revalidate=600"
    )
    body = methodology.json()
    assert body["version"] == "v1"
    assert body["coverage_max"] == {
        "btc": "0.7000",
        "eth": "0.9000",
        "sol": "0.6000",
        "bnb": "0.6000",
    }
    assert body["pillars"][0]["components"]
    assert body["risk_flags"]
    assert len(body["sources"]) == 6

    schema = create_app().openapi()["components"]["schemas"]
    decimal_properties = (
        ("ScoreSummary", "value"),
        ("ScoreSummary", "coverage"),
        ("PriceResponse", "close_usd"),
        ("SeriesPoint", "value"),
    )
    for model_name, property_name in decimal_properties:
        property_schema = schema[model_name]["properties"][property_name]
        rendered = str(property_schema)
        assert '"type": "number"' not in rendered
        assert "string" in rendered

    limited = None
    for _ in range(119):
        limited = await public_client.get("/api/v1/methodology")
        assert limited.status_code == 200
    assert limited is not None
    response = await public_client.get("/api/v1/methodology")
    assert response.status_code == 429
    assert response.headers.get("Retry-After")
    assert response.json()["error"]["code"] == "rate_limited"
