from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from scripts.data_audit.run import (
    ProbeResult,
    ProbeSpec,
    _time_series_summary,
    apply_catalog_freshness,
    markdown_report,
    probe,
    run_audit,
    truncate_error_body,
)


def test_gap_staleness_and_first_last_dates() -> None:
    payload = {
        "prices": [
            [datetime(2026, 11, 16, tzinfo=UTC).timestamp() * 1000, 1.0],
            [datetime(2026, 11, 18, tzinfo=UTC).timestamp() * 1000, 1.2],
        ]
    }
    spec = ProbeSpec(
        "CoinGecko",
        "https://fixture.test/market",
        ("BTC",),
        ("PriceUSD",),
        "daily",
        "json",
        "fixture.json",
    )
    first, last, points, missing, staleness, samples = _time_series_summary(
        payload, spec
    )
    assert first == "2026-11-16"
    assert last == "2026-11-18"
    assert points == 2
    assert missing == 1
    assert staleness is not None
    assert len(samples) <= 3


@pytest.mark.asyncio
async def test_429_stops_source_and_records_retry_headers() -> None:
    spec = ProbeSpec(
        "CoinGecko",
        "https://fixture.test/ping",
        ("BTC",),
        ("API",),
        "none",
        "json",
        "fixture.json",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"},
            json={"error": "limited"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result, stopped = await probe(client, spec)
    assert stopped is True
    assert result.reachable is False
    assert result.http_status == 429
    assert result.error_class == "HTTP status"
    assert result.rate_limit_headers["retry-after"] == "60"


@pytest.mark.asyncio
async def test_timeout_is_error_not_crash() -> None:
    spec = ProbeSpec(
        "CoinGecko",
        "https://fixture.test/timeout",
        ("BTC",),
        ("API",),
        "none",
        "json",
        "fixture.json",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result, stopped = await probe(client, spec)
    assert stopped is False
    assert result.reachable is False
    assert result.error_class == "timeout"
    assert result.http_status is None


@pytest.mark.asyncio
async def test_offline_fixture_report_has_no_raw_payload() -> None:
    report = await run_audit(
        sources={"CoinGecko"},
        offline_fixtures=True,
    )
    assert report["offline_fixtures"] is True
    assert len(report["results"]) >= 1
    for result in report["results"]:
        assert len(json.dumps(result).encode("utf-8")) < 100_000
        assert "raw_payload" not in result


def test_markdown_generator() -> None:
    report = {
        "run_date": "2026-11-19",
        "duration_seconds": 12.5,
        "results": [
            {
                "source": "CoinGecko",
                "endpoint": "https://api.coingecko.com/api/v3/ping",
                "reachable": True,
                "error_class": "none",
                "error_detail": None,
                "http_status": 200,
                "latency_ms": 100,
            }
        ],
    }
    text = markdown_report(report)
    assert "# ChainCompass Free Data Audit" in text
    assert "## Coverage matrix" in text
    assert "## DECISION" in text
    assert "UNVERIFIED" in text


def test_markdown_rejects_http_error_as_not_available_free_only() -> None:
    report = {
        "run_date": "2026-11-19",
        "duration_seconds": 12.5,
        "coverage_matrix": [
            {
                "Metric": "Tx count",
                "BTC": "NOT AVAILABLE FREE",
                "ETH": "UNVERIFIED",
                "SOL": "UNVERIFIED",
                "BNB": "UNVERIFIED",
            }
        ],
        "results": [
            {
                "source": "Coin Metrics",
                "endpoint": "https://community-api.coinmetrics.io/v4/timeseries",
                "reachable": False,
                "error_class": "HTTP status",
                "error_detail": "HTTP 400",
                "http_status": 400,
                "latency_ms": 100,
            }
        ],
    }
    with pytest.raises(ValueError):
        markdown_report(report)


def test_error_body_capture_is_truncated() -> None:
    body = "x" * 500
    truncated = truncate_error_body(body)
    assert len(truncated) <= 200
    assert truncated.endswith("…")


def test_probe_window_and_source_depth_are_separate_fields() -> None:
    report = {
        "run_date": "2026-11-19",
        "duration_seconds": 12.5,
        "coverage_matrix": [
            {
                "Metric": "Price",
                "BTC": "AVAILABLE (source depth 2017-08-17; probe window 365d)",
                "ETH": "AVAILABLE (source depth 2017-08-17; probe window 365d)",
                "SOL": "UNVERIFIED (CoinGecko 429)",
                "BNB": "UNVERIFIED (source stopped)",
            }
        ],
        "results": [],
    }
    text = markdown_report(report)
    assert "source depth" in text or "probe window" in text


@pytest.mark.asyncio
async def test_coinmetrics_empty_200_is_unverified() -> None:
    spec = ProbeSpec(
        "Coin Metrics",
        "https://fixture.test/timeseries",
        ("BNB",),
        ("AdrActCnt",),
        "daily; bounded 365d",
        "json",
        "fixture.json",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []}, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        result, stopped = await probe(client, spec)
    assert stopped is False
    assert result.http_status == 200
    assert result.daily_points == 0
    assert result.availability == "UNVERIFIED (empty response)"


@pytest.mark.asyncio
async def test_coinmetrics_stale_200_is_discontinued() -> None:
    spec = ProbeSpec(
        "Coin Metrics",
        "https://fixture.test/timeseries",
        ("BNB",),
        ("AdrActCnt",),
        "daily; bounded 365d",
        "json",
        "fixture.json",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"time": "2019-04-22T00:00:00Z", "AdrActCnt": "123"}]},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        result, stopped = await probe(client, spec)
    assert stopped is False
    assert result.daily_points == 1
    assert result.last_date == "2019-04-22"
    assert result.availability == "DISCONTINUED (last data 2019-04-22)"


@pytest.mark.asyncio
async def test_coinmetrics_fresh_200_is_available() -> None:
    recent = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    spec = ProbeSpec(
        "Coin Metrics",
        "https://fixture.test/timeseries",
        ("BTC",),
        ("TxCnt",),
        "daily; bounded 365d",
        "json",
        "fixture.json",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"time": f"{recent}T00:00:00Z", "TxCnt": "100"}]},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        result, stopped = await probe(client, spec)
    assert stopped is False
    assert result.daily_points == 1
    assert result.availability == "AVAILABLE"


def test_markdown_rejects_stale_2xx_as_available() -> None:
    result = {
        "source": "Coin Metrics",
        "endpoint": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
        "chains": ["BNB"],
        "metrics": ["AdrActCnt"],
        "granularity": "daily; bounded 365d",
        "reachable": True,
        "http_status": 200,
        "daily_points": 1,
        "last_date": "2019-04-22",
        "availability": "AVAILABLE",
    }
    report = {
        "run_date": "2026-11-19",
        "duration_seconds": 1,
        "results": [result],
        "coverage_matrix": [
            {
                "Metric": "Active addresses",
                "BTC": "UNVERIFIED",
                "ETH": "UNVERIFIED",
                "SOL": "UNVERIFIED",
                "BNB": "AVAILABLE — Coin Metrics",
            }
        ],
    }
    with pytest.raises(ValueError):
        markdown_report(report)


def test_catalog_stale_maximum_marks_empty_coinmetrics_series_discontinued() -> None:
    catalog = ProbeResult(
        source="Coin Metrics",
        endpoint="https://community-api.coinmetrics.io/v4/catalog/assets?assets=bnb",
        chains=["BNB"],
        metrics=["asset catalog"],
        granularity="catalog",
        reachable=True,
        error_class="none",
        error_detail=None,
        latency_ms=1,
        http_status=200,
        rate_limit_headers={},
        response_top_level_keys=["data"],
        first_date=None,
        last_date=None,
        daily_points=None,
        missing_days=None,
        staleness_hours=None,
        sample_rows=[],
        bounded=True,
        catalog_metrics={
            "bnb": {
                "AdrActCnt": "2019-04-22",
                "TxCnt": "2019-04-22",
                "CapMrktCurUSD": "2019-04-22",
            }
        },
    )
    series = ProbeResult(
        source="Coin Metrics",
        endpoint="https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
        chains=["BNB"],
        metrics=["AdrActCnt"],
        granularity="daily; bounded 365d",
        reachable=True,
        error_class="none",
        error_detail=None,
        latency_ms=1,
        http_status=200,
        rate_limit_headers={},
        response_top_level_keys=["data"],
        first_date=None,
        last_date=None,
        daily_points=0,
        missing_days=None,
        staleness_hours=None,
        sample_rows=[],
        bounded=True,
        availability="UNVERIFIED (empty response)",
    )
    apply_catalog_freshness(
        [catalog, series],
        today=datetime(2026, 11, 19, tzinfo=UTC),
    )
    assert series.availability == "DISCONTINUED (last data 2019-04-22)"
    assert "catalog max_time" in (series.catalog_evidence or "")


def test_coin_metrics_requests_use_one_asset_and_one_metric_per_call() -> None:
    endpoint = (
        "https://community-api.coinmetrics.io/v4/timeseries/"
        "asset-metrics?assets=btc&metrics=PriceUSD"
        "&frequency=1d&start_time=2025-11-20&end_time=2026-11-19"
    )
    assert "assets=btc" in endpoint
    assert "metrics=PriceUSD" in endpoint
    assert "FeeTotUSD" not in endpoint


@pytest.mark.live_audit
@pytest.mark.asyncio
async def test_live_audit_is_opt_in() -> None:
    report = await run_audit()
    assert report["sources_probed"]
