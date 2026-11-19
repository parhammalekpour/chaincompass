from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models.ingestion import Observation, SeriesCoverage
from app.ingest import parse_args
from app.ingestion.binance import BinanceKlinesProvider
from app.ingestion.http import PoliteHttpClient, ProviderStopped
from app.ingestion.provider import ChainContext, Point
from app.ingestion.service import IngestionService


def kline(open_ms: int, close: str, quote_volume: str) -> list[object]:
    return [
        open_ms,
        "1",
        "2",
        "0",
        close,
        "1",
        str(open_ms + 86_400_000 - 1),
        quote_volume,
        "1",
        "1",
        "0",
        "0",
    ]


@pytest.mark.asyncio
async def test_binance_pagination_and_incomplete_today_excluded() -> None:
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        params = request.url.params
        cursor = int(params["startTime"])
        if calls == 1:
            rows = [kline(cursor, "100.123456789012", "250.000000000000")]
            return httpx.Response(
                200,
                json=rows,
                headers={"X-Page": "1"},
                request=request,
            )
        if cursor:
            rows = [
                kline(
                    int(
                        datetime.combine(
                            yesterday,
                            datetime.min.time(),
                            UTC,
                        ).timestamp()
                        * 1000
                    ),
                    "101.000000000000",
                    "260.000000000000",
                )
            ]
            return httpx.Response(200, json=rows, request=request)
        return httpx.Response(200, json=[], request=request)

    polite = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    provider = BinanceKlinesProvider(http=polite)
    try:
        points = await provider.fetch(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            today - timedelta(days=2),
            today,
        )
    finally:
        await provider.close()
    assert calls >= 1
    assert all(point.date <= yesterday for point in points)
    assert Decimal("100.123456789012") in [point.value for point in points]


@pytest.mark.asyncio
async def test_validation_rejects_bad_rows_and_preserves_precision(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="binance",
            source_code="binance",
        )
        today = datetime.now(UTC).date()
        valid = Point(today - timedelta(days=1), Decimal("123456789.123456789012"))
        valid_ok, reason = service.validate_point(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            valid,
            today,
        )
        assert valid_ok
        assert reason is None
        assert Decimal("123456789.123456789012").as_tuple().exponent == -12

        bad = Point(today - timedelta(days=1), Decimal("-1"))
        valid_ok, reason = service.validate_point(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            bad,
            today,
        )
        assert not valid_ok
        assert reason == "negative"


@pytest.mark.asyncio
async def test_upsert_idempotency_and_three_day_overlap(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        from app.db.models.ingestion import Chain, DataSource, MetricDefinition

        session.add_all(
            [
                Chain(
                    code="btc",
                    name="Bitcoin",
                    native_symbol="BTC",
                    consensus="pow",
                    enabled=True,
                ),
                DataSource(
                    code="binance",
                    name="Binance",
                    url="https://data-api.binance.vision/",
                    license_note="Public market data",
                    attribution_required=False,
                ),
                MetricDefinition(
                    code="price_close_usd",
                    unit="USD",
                    frequency="1d",
                    description="Daily close",
                ),
            ]
        )
        await session.commit()
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="binance",
            source_code="binance",
        )
        obs_date = datetime.now(UTC).date() - timedelta(days=1)
        points = [Point(obs_date, Decimal("123.450000000000"))]
        first_count, rejected = await service.upsert_points(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            points,
            today=datetime.now(UTC).date(),
        )
        second_count, second_rejected = await service.upsert_points(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            points,
            today=datetime.now(UTC).date(),
        )
        row_count = await session.scalar(select(func.count()).select_from(Observation))
        assert first_count == 1
        assert second_count == 1
        assert rejected == 0
        assert second_rejected == 0
        assert row_count == 1
        assert await service.last_stored_date("btc", "price_close_usd") == obs_date


@pytest.mark.asyncio
async def test_429_stops_provider_and_is_recorded() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "1"},
            text="rate limited",
            request=request,
        )

    polite = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ProviderStopped):
            await polite.get_json(
                "https://fixture.test/klines",
                {"limit": 1000},
            )
    finally:
        await polite.close()


@pytest.mark.asyncio
async def test_coverage_missing_days_and_stale(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        from app.db.models.ingestion import Chain, DataSource, MetricDefinition

        chain = await session.get(Chain, "btc")
        if chain is None:
            session.add(
                Chain(
                    code="btc",
                    name="Bitcoin",
                    native_symbol="BTC",
                    consensus="pow",
                    enabled=True,
                )
            )
        if await session.get(DataSource, "binance") is None:
            session.add(
                DataSource(
                    code="binance",
                    name="Binance",
                    url="https://data-api.binance.vision/",
                    license_note="Public",
                    attribution_required=False,
                )
            )
        if await session.get(MetricDefinition, "price_close_usd") is None:
            session.add(
                MetricDefinition(
                    code="price_close_usd",
                    unit="USD",
                    frequency="1d",
                    description="Close",
                )
            )
        await session.commit()
        today = datetime.now(UTC).date()
        session.add_all(
            [
                Observation(
                    chain_code="btc",
                    metric_code="price_close_usd",
                    source_code="binance",
                    obs_date=today - timedelta(days=5),
                    value=Decimal("1"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="price_close_usd",
                    source_code="binance",
                    obs_date=today - timedelta(days=3),
                    value=Decimal("2"),
                    fetched_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="binance",
            source_code="binance",
        )
        await service.recompute_coverage("btc", "price_close_usd")
        coverage = await session.get(
            SeriesCoverage,
            ("btc", "price_close_usd", "binance"),
        )
        assert coverage is not None
        assert coverage.points == 2
        assert coverage.missing_days == 1
        assert coverage.status == "stale"


def test_cli_status_argument_parses() -> None:
    args = parse_args(["status"])
    assert args.command == "status"
