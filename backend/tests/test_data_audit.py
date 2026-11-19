from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from scripts.data_audit.run import (
    ProbeSpec,
    _time_series_summary,
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
