from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.db.models.ingestion import (
    Chain,
    DataSource,
    IngestionRun,
    MetricDefinition,
    Observation,
    SeriesCoverage,
)
from app.ingest import (
    analyze_series,
    format_status,
    gap_ranges,
    http_error_is_unavailable,
    legacy_bnb_coinmetrics_reason,
    parse_args,
    purge_observations,
    run_updates_all,
)
from app.ingestion.btcnet import BtcNetworkProvider, btc_fees_to_usd
from app.ingestion.coinmetrics import CoinMetricsProvider
from app.ingestion.defillama import DefiLlamaProvider
from app.ingestion.http import PoliteHttpClient
from app.ingestion.provider import ChainContext, Point
from app.ingestion.service import IngestionService

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def ensure_reference(
    session: Any,
    chain: Chain,
    source: DataSource,
    metric: MetricDefinition,
) -> None:
    if await session.get(Chain, chain.code) is None:
        session.add(chain)
    if await session.get(DataSource, source.code) is None:
        session.add(source)
    if await session.get(MetricDefinition, metric.code) is None:
        session.add(metric)
    await session.commit()


@pytest.mark.asyncio
async def test_binance_paginates_full_page() -> None:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1000)
    first_page = [
        [
            start_ms + offset * 86_400_000,
            "1",
            "2",
            "0",
            "100",
            "1",
            start_ms + (offset + 1) * 86_400_000 - 1,
            "200",
            "1",
            "1",
            "0",
            "0",
        ]
        for offset in range(1000)
    ]
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        rows = first_page if calls == 1 else [first_page[-1]]
        if calls == 2:
            rows = [
                [
                    int(datetime(2022, 9, 27, tzinfo=UTC).timestamp() * 1000),
                    "1",
                    "2",
                    "0",
                    "101",
                    "1",
                    0,
                    "201",
                    "1",
                    "1",
                    "0",
                    "0",
                ]
            ]
        return httpx.Response(200, json=rows, request=request)

    http = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    from app.ingestion.binance import BinanceKlinesProvider

    provider = BinanceKlinesProvider(http=http)
    try:
        points = await provider.fetch(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            date(2020, 1, 1),
            date(2022, 10, 1),
        )
    finally:
        await provider.close()
    assert calls == 2
    assert len(points) == 1001


@pytest.mark.asyncio
async def test_coinmetrics_paginates_one_metric_and_drops_today() -> None:
    first_page = read_fixture("coinmetrics_page_1.json")
    second_page = read_fixture("coinmetrics_page_2.json")
    today = datetime.now(UTC).date().isoformat()
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.params.get("page") == "2":
            payload = second_page
        else:
            payload = dict(first_page)
            payload["data"].append(
                {"time": f"{today}T00:00:00Z", "CapMrktCurUSD": "999"}
            )
        return httpx.Response(200, json=payload, request=request)

    http = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    provider = CoinMetricsProvider(http=http)
    try:
        points = await provider.fetch(
            ChainContext("btc", "BTC"),
            "market_cap_usd",
            date(2026, 1, 1),
            date(2026, 1, 5),
        )
    finally:
        await provider.close()

    assert len(calls) == 2
    assert calls[0].url.params["metrics"] == "CapMrktCurUSD"
    assert calls[1].url.params["page"] == "2"
    assert [point.value for point in points] == [
        Decimal("100.123456789012"),
        Decimal("101.25"),
        Decimal("102.50"),
    ]
    assert all(point.date < datetime.now(UTC).date() for point in points)


@pytest.mark.asyncio
async def test_coinmetrics_403_is_recorded_unavailable(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await ensure_reference(
            session,
            Chain(
                code="sol",
                name="Solana",
                native_symbol="SOL",
                consensus="pos",
            ),
            DataSource(
                code="coin_metrics",
                name="Coin Metrics",
                url="https://community-api.coinmetrics.io/",
                license_note="Community API terms apply.",
                attribution_required=True,
            ),
            MetricDefinition(
                code="active_addresses",
                unit="addresses",
                frequency="1d",
                description="Daily active addresses",
            ),
        )
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="coinmetrics",
            source_code="coin_metrics",
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                text="access denied " + ("x" * 300),
                request=request,
            )

        http = PoliteHttpClient(
            minimum_interval_seconds=0,
            transport=httpx.MockTransport(handler),
        )
        try:
            with pytest.raises(httpx.HTTPStatusError) as error:
                await http.get_json("https://fixture.test/metrics", {})
        finally:
            await http.close()
        assert http_error_is_unavailable(error.value.response.status_code)
        assert len(error.value.response.text) > 200
        assert "x" * 201 not in str(error.value)
        await service.record_unavailable("sol", "active_addresses", str(error.value))
        coverage = await session.get(
            SeriesCoverage,
            ("sol", "active_addresses", "coin_metrics"),
        )
        assert coverage is not None
        assert coverage.status == "unavailable"
        assert "HTTP 403" in (coverage.last_error or "")
        assert not http_error_is_unavailable(400)


@pytest.mark.asyncio
async def test_429_error_status_is_saved(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await ensure_reference(
            session,
            Chain(
                code="btc",
                name="Bitcoin",
                native_symbol="BTC",
                consensus="pow",
            ),
            DataSource(
                code="mempool",
                name="mempool.space",
                url="https://mempool.space/",
                license_note="Public API terms apply.",
                attribution_required=True,
            ),
            MetricDefinition(
                code="hashrate",
                unit="H/s",
                frequency="1d",
                description="Daily hash rate",
            ),
        )
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="btcnet",
            source_code="mempool",
        )
        await service.record_error("btc", "hashrate", "HTTP 429: rate limited")
        coverage = await session.get(
            SeriesCoverage,
            ("btc", "hashrate", "mempool"),
        )
        assert coverage is not None
        assert coverage.status == "error"
        assert "429" in (coverage.last_error or "")


@pytest.mark.asyncio
async def test_upsert_preserves_decimal_precision(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await ensure_reference(
            session,
            Chain(
                code="btc",
                name="Bitcoin",
                native_symbol="BTC",
                consensus="pow",
            ),
            DataSource(
                code="binance",
                name="Binance",
                url="https://data-api.binance.vision/",
                license_note="Public market data terms apply.",
                attribution_required=False,
            ),
            MetricDefinition(
                code="price_close_usd",
                unit="USD",
                frequency="1d",
                description="Daily close",
            ),
        )
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="binance",
            source_code="binance",
        )
        day = datetime.now(UTC).date().replace(day=1) - timedelta(days=1)
        input_value = Decimal("123456789.12345678901234")
        expected = Decimal("123456789.123456789012")
        await service.upsert_points(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            [Point(day, input_value)],
            today=datetime.now(UTC).date(),
        )
        stored = await session.get(
            Observation,
            ("btc", "price_close_usd", "binance", day),
        )
        assert stored is not None
        assert isinstance(stored.value, Decimal)
        assert stored.value == expected


def test_incremental_overlap_uses_provider_window() -> None:
    last = date(2026, 5, 20)
    assert IngestionService.incremental_start(last, 3) == date(2026, 5, 17)
    assert IngestionService.incremental_start(last, 7) == date(2026, 5, 13)
    assert IngestionService.incremental_start(None, 7) is None


@pytest.mark.asyncio
async def test_defillama_preserves_gaps_and_drops_today() -> None:
    fixture = read_fixture("defillama_tvl.json")
    today = datetime.now(UTC).date()
    today_timestamp = int(datetime.combine(today, datetime.min.time(), UTC).timestamp())
    payload = list(fixture)
    payload.append({"date": today_timestamp, "tvl": 999})

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/ethereum")
        return httpx.Response(200, json=payload, request=request)

    http = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    provider = DefiLlamaProvider(http=http)
    try:
        points = await provider.fetch(
            ChainContext("eth", "ETH"),
            "tvl_usd",
            date(2025, 11, 19),
            today,
        )
    finally:
        await provider.close()

    assert len(points) == 3
    assert [point.value for point in points] == [
        Decimal("100.25"),
        Decimal("102.75"),
        Decimal("103.5"),
    ]
    assert len(gap_ranges([point.date for point in points])) == 1
    assert all(point.date < today for point in points)


@pytest.mark.asyncio
async def test_btc_hashrate_conversion_and_daily_fees() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("hash-rate"):
            payload = read_fixture("blockchain_hashrate.json")
        else:
            payload = read_fixture("blockchain_fees.json")
        return httpx.Response(200, json=payload, request=request)

    http = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    provider = BtcNetworkProvider(http=http)
    try:
        hashrate = await provider.fetch(
            ChainContext("btc", "BTC"),
            "hashrate",
            date(2025, 11, 19),
            date(2026, 1, 1),
        )
        fees = await provider.fetch(
            ChainContext("btc", "BTC"),
            "fees_usd",
            date(2025, 11, 19),
            date(2026, 1, 1),
        )
    finally:
        await provider.close()
    assert hashrate[0].value == Decimal("150000000000000000000")
    assert fees[0].value == Decimal("2.5")
    converted, rejected = btc_fees_to_usd(
        fees,
        {fees[0].date: Decimal("50000")},
    )
    assert converted[0].value == Decimal("125000")
    assert rejected == 0


@pytest.mark.asyncio
async def test_btc_chart_backfill_uses_bounded_sequential_windows() -> None:
    starts: list[date] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["start"])
        start_date = datetime.fromtimestamp(start, UTC).date()
        starts.append(start_date)
        return httpx.Response(
            200,
            json={
                "unit": "Hash Rate TH/s",
                "values": [{"x": start + 86400, "y": 100000000}],
            },
            request=request,
        )

    http = PoliteHttpClient(
        minimum_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    provider = BtcNetworkProvider(http=http)
    try:
        points = await provider.fetch(
            ChainContext("btc", "BTC"),
            "hashrate",
            date(2020, 1, 1),
            date(2022, 3, 10),
        )
    finally:
        await provider.close()
    assert len(starts) == 3
    assert starts == [
        date(2020, 1, 1),
        date(2020, 12, 31),
        date(2021, 12, 31),
    ]
    assert len(points) == 3


def test_defillama_parses_string_timestamps_for_stablecoin_series() -> None:
    point = DefiLlamaProvider._point(
        {
            "date": "1763596800",
            "totalCirculatingUSD": {"peggedUSD": 400.25},
        },
        "stablecoin_supply_usd",
    )
    assert point is not None
    assert point.date == date(2025, 11, 20)
    assert point.value == Decimal("400.25")


@pytest.mark.asyncio
async def test_update_all_continues_after_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ingest as ingest

    calls: list[str] = []

    async def fake_run_provider(
        *,
        job: str,
        provider_name: str,
        chains: list[str] | None,
        since: date | None,
    ) -> int:
        del job, chains, since
        calls.append(provider_name)
        if provider_name == "coinmetrics":
            raise RuntimeError("fixture failure")
        return 0

    monkeypatch.setattr(ingest, "run_provider", fake_run_provider)
    assert await run_updates_all() == 1
    assert calls == ["binance", "coinmetrics", "defillama", "btcnet"]


def test_check_finds_planted_gap_and_jump() -> None:
    dates = [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 4),
        date(2026, 1, 5),
    ]
    series = [
        Observation(
            chain_code="btc",
            metric_code="price_close_usd",
            source_code="binance",
            obs_date=day,
            value=value,
            fetched_at=datetime.now(UTC),
        )
        for day, value in zip(
            dates,
            map(Decimal, ("100", "110", "100", "200")),
            strict=True,
        )
    ]
    gaps, zeros, jumps, prelaunch_zeros = analyze_series(series, Decimal("0.4"))
    assert gaps == [(date(2026, 1, 3), date(2026, 1, 3))]
    assert zeros == []
    assert prelaunch_zeros is None
    assert len(jumps) == 1
    assert jumps[0][2] == Decimal(1)


def test_check_uses_trailing_median_for_volume_and_prelaunch_zeros() -> None:
    volume_series = [
        Observation(
            chain_code="btc",
            metric_code="volume_usd",
            source_code="binance",
            obs_date=date(2026, 1, 1) + timedelta(days=offset),
            value=value,
            fetched_at=datetime.now(UTC),
        )
        for offset, value in enumerate([Decimal("100")] * 30 + [Decimal("110")])
    ]
    _, _, volume_jumps, _ = analyze_series(volume_series, Decimal("0.4"))
    assert volume_jumps == []

    activity_series = [
        Observation(
            chain_code="btc",
            metric_code="active_addresses",
            source_code="coin_metrics",
            obs_date=date(2026, 1, 1) + timedelta(days=offset),
            value=value,
            fetched_at=datetime.now(UTC),
        )
        for offset, value in enumerate(
            map(Decimal, ("0", "0", "100", "0")),
        )
    ]
    _, suspicious_zeros, _, prelaunch_zeros = analyze_series(
        activity_series,
        Decimal("0.4"),
    )
    assert len(suspicious_zeros) == 1
    assert prelaunch_zeros == (date(2026, 1, 1), date(2026, 1, 2))


def test_status_renders_unavailable_reason() -> None:
    row = SeriesCoverage(
        chain_code="sol",
        metric_code="active_addresses",
        source_code="coin_metrics",
        points=0,
        missing_days=0,
        status="unavailable",
        last_error="HTTP 403: asset is not in community tier",
    )
    rendered = format_status([row])
    assert "unavailable" in rendered
    assert "HTTP 403: asset is not in community tier" in rendered


def test_status_labels_btc_fees_as_derived() -> None:
    row = SeriesCoverage(
        chain_code="btc",
        metric_code="fees_usd",
        source_code="blockchain_info",
        points=1,
        missing_days=0,
        status="ok",
    )
    assert "derived" in format_status([row])


def test_legacy_bnb_coinmetrics_series_are_not_refetched() -> None:
    assert (
        legacy_bnb_coinmetrics_reason("bnb", "active_addresses")
        == "legacy BNB asset series ended 2019-04-22; not BNB Chain"
    )
    assert legacy_bnb_coinmetrics_reason("bnb", "price_close_usd") is None
    assert legacy_bnb_coinmetrics_reason("btc", "active_addresses") is None


def test_purge_command_requires_confirmation() -> None:
    args = parse_args(
        ["purge", "--provider", "coinmetrics", "--chains", "bnb"],
    )
    assert args.yes is False
    confirmed = parse_args(
        ["purge", "--provider", "coinmetrics", "--chains", "bnb", "--yes"],
    )
    assert confirmed.yes is True


@pytest.mark.asyncio
async def test_purge_deletes_only_confirmed_coinmetrics_bnb_rows(
    auth_session_factory,
    clean_ingestion_tables,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with auth_session_factory() as session:
        for chain_code in ("bnb", "btc"):
            await ensure_reference(
                session,
                Chain(
                    code=chain_code,
                    name=chain_code.upper(),
                    native_symbol=chain_code.upper(),
                    consensus="pos",
                ),
                DataSource(
                    code="coin_metrics",
                    name="Coin Metrics",
                    url="https://community-api.coinmetrics.io/",
                    license_note="Community API terms apply.",
                    attribution_required=True,
                ),
                MetricDefinition(
                    code="tx_count",
                    unit="transactions",
                    frequency="1d",
                    description="Daily transactions",
                ),
            )
        for metric_code, unit in (
            ("market_cap_usd", "USD"),
            ("active_addresses", "addresses"),
        ):
            if await session.get(MetricDefinition, metric_code) is None:
                session.add(
                    MetricDefinition(
                        code=metric_code,
                        unit=unit,
                        frequency="1d",
                        description=metric_code,
                    )
                )
        await session.commit()
        session.add_all(
            [
                Observation(
                    chain_code="bnb",
                    metric_code="tx_count",
                    source_code="coin_metrics",
                    obs_date=date(2019, 4, 22),
                    value=Decimal("10"),
                    fetched_at=datetime.now(UTC),
                ),
                Observation(
                    chain_code="btc",
                    metric_code="tx_count",
                    source_code="coin_metrics",
                    obs_date=date(2026, 1, 1),
                    value=Decimal("20"),
                    fetched_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()

        assert (
            await purge_observations(
                session,
                provider_name="coinmetrics",
                chains=["bnb"],
                confirmed=False,
            )
            == 2
        )
        assert len((await session.scalars(select(Observation))).all()) == 2
        assert (
            await purge_observations(
                session,
                provider_name="coinmetrics",
                chains=["bnb"],
                confirmed=True,
            )
            == 0
        )
        remaining = list((await session.scalars(select(Observation))).all())
        assert len(remaining) == 1
        assert remaining[0].chain_code == "btc"
        coverage = await session.get(
            SeriesCoverage,
            ("bnb", "tx_count", "coin_metrics"),
        )
        assert coverage is not None
        assert coverage.status == "discontinued"
        assert "not BNB Chain" in (coverage.last_error or "")
        run = await session.scalar(
            select(IngestionRun).where(IngestionRun.job == "purge")
        )
        assert run is not None
        assert "purged_observations=1" in (run.error or "")
        assert "Purge plan: 1 observations" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_old_series_is_marked_discontinued(
    auth_session_factory,
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await ensure_reference(
            session,
            Chain(
                code="btc",
                name="Bitcoin",
                native_symbol="BTC",
                consensus="pow",
            ),
            DataSource(
                code="binance",
                name="Binance",
                url="https://data-api.binance.vision/",
                license_note="Public market data.",
                attribution_required=False,
            ),
            MetricDefinition(
                code="price_close_usd",
                unit="USD",
                frequency="1d",
                description="Daily close",
            ),
        )
        old_date = date(2010, 1, 1)
        service = IngestionService(
            session,
            provider=object(),  # type: ignore[arg-type]
            provider_code="binance",
            source_code="binance",
        )
        await service.upsert_points(
            ChainContext("btc", "BTC"),
            "price_close_usd",
            [Point(old_date, Decimal("100"))],
            today=datetime.now(UTC).date(),
        )
        await service.recompute_coverage("btc", "price_close_usd")
        coverage = await session.get(
            SeriesCoverage,
            ("btc", "price_close_usd", "binance"),
        )
        assert coverage is not None
        assert coverage.status == "discontinued"
        assert old_date.isoformat() in (coverage.last_error or "")


def test_check_threshold_rejects_non_finite_values() -> None:
    with pytest.raises(SystemExit):
        parse_args(["check", "--jump-threshold", "NaN"])
    with pytest.raises(SystemExit):
        parse_args(["check", "--jump-threshold", "-0.1"])


def test_binance_unavailability_classifier_is_status_specific() -> None:
    assert http_error_is_unavailable(403)
    assert http_error_is_unavailable(404)
    assert not http_error_is_unavailable(400)
    assert not http_error_is_unavailable(500)
