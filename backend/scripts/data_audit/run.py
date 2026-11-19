"""Audit no-key public data sources used by ChainCompass."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

USER_AGENT = "ChainCompass-audit/0.1"
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "backend" / "scripts" / "data_audit" / "output"
FIXTURE_DIR = ROOT / "backend" / "tests" / "fixtures" / "data_audit"
MAX_SAMPLE_ROWS = 3

ErrorClass = Literal[
    "DNS",
    "TLS",
    "timeout",
    "HTTP status",
    "transport",
    "none",
]


@dataclass(frozen=True)
class ProbeSpec:
    source: str
    endpoint: str
    chains: tuple[str, ...]
    metrics: tuple[str, ...]
    granularity: str
    kind: Literal["json", "binance_klines", "rpc"]
    offline_fixture: str


@dataclass
class ProbeResult:
    source: str
    endpoint: str
    chains: list[str]
    metrics: list[str]
    granularity: str
    reachable: bool
    error_class: ErrorClass
    error_detail: str | None
    latency_ms: int | None
    http_status: int | None
    rate_limit_headers: dict[str, str]
    response_top_level_keys: list[str]
    first_date: str | None
    last_date: str | None
    daily_points: int | None
    missing_days: int | None
    staleness_hours: float | None
    sample_rows: list[dict[str, Any]]
    bounded: bool


def _probe_specs() -> tuple[ProbeSpec, ...]:
    return (
        ProbeSpec(
            "DefiLlama",
            "https://api.llama.fi/v2/chains",
            ("BTC", "ETH", "SOL", "BNB"),
            ("TVL",),
            "current",
            "json",
            "defillama_chains.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://stablecoins.llama.fi/stablecoincharts/all",
            ("BTC", "ETH", "SOL", "BNB"),
            ("Stablecoin supply",),
            "daily",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://api.llama.fi/v2/historicalChainTvl/ethereum",
            ("ETH",),
            ("TVL",),
            "daily; bounded 365d",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://api.llama.fi/v2/historicalChainTvl/solana",
            ("SOL",),
            ("TVL",),
            "daily; bounded 365d",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://api.llama.fi/v2/historicalChainTvl/bsc",
            ("BNB",),
            ("TVL",),
            "daily; bounded 365d",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://stablecoins.llama.fi/stablecoincharts/ethereum",
            ("ETH",),
            ("Stablecoin supply",),
            "daily",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://stablecoins.llama.fi/stablecoincharts/solana",
            ("SOL",),
            ("Stablecoin supply",),
            "daily",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "DefiLlama",
            "https://stablecoins.llama.fi/stablecoincharts/bsc",
            ("BNB",),
            ("Stablecoin supply",),
            "daily",
            "json",
            "defillama_stablecoins.json",
        ),
        ProbeSpec(
            "CoinGecko",
            "https://api.coingecko.com/api/v3/ping",
            ("BTC", "ETH", "SOL", "BNB"),
            ("API availability",),
            "none",
            "json",
            "coingecko_ping.json",
        ),
        ProbeSpec(
            "CoinGecko",
            "https://api.coingecko.com/api/v3/simple/price?"
            "ids=bitcoin,ethereum,solana,binancecoin"
            "&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true",
            ("BTC", "ETH", "SOL", "BNB"),
            ("PriceUSD", "Volume24h", "MarketCap"),
            "current",
            "json",
            "coingecko_price.json",
        ),
        ProbeSpec(
            "CoinGecko",
            "https://api.coingecko.com/api/v3/coins/bitcoin/"
            "market_chart?vs_currency=usd&days=365&interval=daily",
            ("BTC",),
            ("PriceUSD", "Volume24h", "MarketCap"),
            "daily; bounded 365d",
            "json",
            "coingecko_market_chart.json",
        ),
        ProbeSpec(
            "CoinGecko",
            "https://api.coingecko.com/api/v3/coins/ethereum/"
            "market_chart?vs_currency=usd&days=365&interval=daily",
            ("ETH",),
            ("PriceUSD", "Volume24h", "MarketCap"),
            "daily; bounded 365d",
            "json",
            "coingecko_market_chart.json",
        ),
        ProbeSpec(
            "CoinGecko",
            "https://api.coingecko.com/api/v3/coins/solana/"
            "market_chart?vs_currency=usd&days=365&interval=daily",
            ("SOL",),
            ("PriceUSD", "Volume24h", "MarketCap"),
            "daily; bounded 365d",
            "json",
            "coingecko_market_chart.json",
        ),
        ProbeSpec(
            "CoinGecko",
            "https://api.coingecko.com/api/v3/coins/binancecoin/"
            "market_chart?vs_currency=usd&days=365&interval=daily",
            ("BNB",),
            ("PriceUSD", "Volume24h", "MarketCap"),
            "daily; bounded 365d",
            "json",
            "coingecko_market_chart.json",
        ),
        ProbeSpec(
            "Coin Metrics",
            "https://community-api.coinmetrics.io/v4/catalog/assets",
            ("BTC", "ETH", "SOL", "BNB"),
            ("catalog",),
            "catalog",
            "json",
            "coinmetrics_catalog.json",
        ),
        ProbeSpec(
            "Coin Metrics",
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?"
            "assets=btc&metrics=PriceUSD,CapMrktCurUSD,AdrActCnt,TxCnt,FeeTotUSD,"
            "HashRate&frequency=1d&limit=10",
            ("BTC",),
            ("PriceUSD", "MarketCap", "AdrActCnt", "TxCnt", "FeeTotUSD", "HashRate"),
            "daily; bounded 10 points",
            "json",
            "coinmetrics_catalog.json",
        ),
        ProbeSpec(
            "Coin Metrics",
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?"
            "assets=eth&metrics=PriceUSD,CapMrktCurUSD,AdrActCnt,TxCnt,FeeTotUSD,"
            "HashRate&frequency=1d&limit=10",
            ("ETH",),
            ("PriceUSD", "MarketCap", "AdrActCnt", "TxCnt", "FeeTotUSD", "HashRate"),
            "daily; bounded 10 points",
            "json",
            "coinmetrics_catalog.json",
        ),
        ProbeSpec(
            "Coin Metrics",
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?"
            "assets=sol&metrics=PriceUSD,CapMrktCurUSD,AdrActCnt,TxCnt,FeeTotUSD,"
            "HashRate&frequency=1d&limit=10",
            ("SOL",),
            ("PriceUSD", "MarketCap", "AdrActCnt", "TxCnt", "FeeTotUSD", "HashRate"),
            "daily; bounded 10 points",
            "json",
            "coinmetrics_catalog.json",
        ),
        ProbeSpec(
            "Coin Metrics",
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?"
            "assets=bnb&metrics=PriceUSD,CapMrktCurUSD,AdrActCnt,TxCnt,FeeTotUSD,"
            "HashRate&frequency=1d&limit=10",
            ("BNB",),
            ("PriceUSD", "MarketCap", "AdrActCnt", "TxCnt", "FeeTotUSD", "HashRate"),
            "daily; bounded 10 points",
            "json",
            "coinmetrics_catalog.json",
        ),
        ProbeSpec(
            "mempool.space",
            "https://mempool.space/api/v1/mining/difficulty-adjustment",
            ("BTC",),
            ("Difficulty", "Hashrate"),
            "current",
            "json",
            "mempool_difficulty.json",
        ),
        ProbeSpec(
            "mempool.space",
            "https://mempool.space/api/v1/mining/hashrate/1y",
            ("BTC",),
            ("Hashrate",),
            "1d; bounded 1y",
            "json",
            "mempool_hashrate.json",
        ),
        ProbeSpec(
            "mempool.space",
            "https://mempool.space/api/v1/fees/recommended",
            ("BTC",),
            ("Fees",),
            "current",
            "json",
            "mempool_fees.json",
        ),
        ProbeSpec(
            "Blockchain.info",
            "https://api.blockchain.info/charts/hash-rate?"
            "timespan=365days&format=json&sampled=false",
            ("BTC",),
            ("Hashrate",),
            "daily; bounded 365d",
            "json",
            "blockchain_hashrate.json",
        ),
        ProbeSpec(
            "Blockchain.info",
            "https://api.blockchain.info/charts/transactions-per-second?"
            "timespan=30days&format=json&sampled=false",
            ("BTC",),
            ("TxCount", "TPS"),
            "daily; bounded 30d",
            "json",
            "blockchain_hashrate.json",
        ),
        ProbeSpec(
            "Blockchain.info",
            "https://api.blockchain.info/charts/fees-per-transaction?"
            "timespan=30days&format=json&sampled=false",
            ("BTC",),
            ("Fees",),
            "daily; bounded 30d",
            "json",
            "blockchain_hashrate.json",
        ),
        ProbeSpec(
            "Binance",
            "https://data-api.binance.vision/api/v3/klines?"
            "symbol=BTCUSDT&interval=1d&limit=365",
            ("BTC",),
            ("PriceUSD", "Volume24h"),
            "daily; bounded 365d",
            "binance_klines",
            "binance_klines.json",
        ),
        ProbeSpec(
            "Binance",
            "https://data-api.binance.vision/api/v3/klines?"
            "symbol=ETHUSDT&interval=1d&limit=365",
            ("ETH",),
            ("PriceUSD", "Volume24h"),
            "daily; bounded 365d",
            "binance_klines",
            "binance_klines.json",
        ),
        ProbeSpec(
            "Binance",
            "https://data-api.binance.vision/api/v3/klines?"
            "symbol=SOLUSDT&interval=1d&limit=365",
            ("SOL",),
            ("PriceUSD", "Volume24h"),
            "daily; bounded 365d",
            "binance_klines",
            "binance_klines.json",
        ),
        ProbeSpec(
            "Binance",
            "https://data-api.binance.vision/api/v3/klines?"
            "symbol=BNBUSDT&interval=1d&limit=365",
            ("BNB",),
            ("PriceUSD", "Volume24h"),
            "daily; bounded 365d",
            "binance_klines",
            "binance_klines.json",
        ),
        ProbeSpec(
            "Blockchair",
            "https://api.blockchair.com/stats",
            ("BTC", "ETH"),
            ("network stats",),
            "current",
            "json",
            "blockchair_stats.json",
        ),
        ProbeSpec(
            "PublicNode",
            "https://ethereum-rpc.publicnode.com",
            ("ETH",),
            ("Block number", "Recent block"),
            "RPC sample",
            "rpc",
            "rpc_eth.json",
        ),
        ProbeSpec(
            "Solana RPC",
            "https://api.mainnet-beta.solana.com",
            ("SOL",),
            ("Recent performance samples",),
            "RPC sample",
            "rpc",
            "rpc_solana.json",
        ),
        ProbeSpec(
            "BNB RPC",
            "https://bsc-dataseed.binance.org/",
            ("BNB",),
            ("Block number", "Recent block"),
            "RPC sample",
            "rpc",
            "rpc_bnb.json",
        ),
    )


def _top_level_keys(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return sorted(str(key) for key in payload.keys())[:100]
    if isinstance(payload, list):
        return ["[]"]
    return [type(payload).__name__]


def _safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows[:MAX_SAMPLE_ROWS]


def _iso_date(timestamp_seconds: float) -> str:
    return datetime.fromtimestamp(timestamp_seconds, UTC).date().isoformat()


def _time_series_summary(
    payload: Any,
    spec: ProbeSpec,
) -> tuple[
    str | None,
    str | None,
    int | None,
    int | None,
    float | None,
    list[dict[str, Any]],
]:
    dates: list[str] = []
    samples: list[dict[str, Any]] = []

    if spec.source == "CoinGecko":
        prices = payload.get("prices", []) if isinstance(payload, dict) else []
        for pair in prices:
            if (
                isinstance(pair, list)
                and len(pair) >= 2
                and isinstance(pair[0], (int, float))
            ):
                date = _iso_date(float(pair[0]) / 1000)
                dates.append(date)
                samples.append({"date": date, "value": round(float(pair[1]), 8)})
    elif spec.source == "Blockchain.info":
        values = payload.get("values", []) if isinstance(payload, dict) else []
        for item in values:
            if isinstance(item, dict) and isinstance(item.get("x"), (int, float)):
                date = _iso_date(float(item["x"]))
                dates.append(date)
                samples.append({"date": date, "value": item.get("y")})
    elif spec.source == "Binance":
        if isinstance(payload, list):
            for row in payload:
                if isinstance(row, list) and len(row) >= 6:
                    binance_date = datetime.fromtimestamp(
                        float(row[0]) / 1000,
                        UTC,
                    ).date()
                    date_text = binance_date.isoformat()
                    dates.append(date_text)
                    samples.append(
                        {
                            "date": date_text,
                            "open": row[1],
                            "close": row[4],
                            "volume": row[5],
                        }
                    )
    elif spec.source in {"mempool.space", "DefiLlama"}:
        rows = payload if isinstance(payload, list) else []
        if (
            spec.source == "mempool.space"
            and isinstance(payload, dict)
            and isinstance(payload.get("hashrates"), list)
        ):
            rows = [
                {
                    "date": item.get("timestamp"),
                    "value": item.get("avgHashrate"),
                }
                for item in payload["hashrates"]
                if isinstance(item, dict)
            ]
        for item in rows:
            if not isinstance(item, dict):
                continue
            date_value = item.get("date") or item.get("time")
            if isinstance(date_value, (int, float)):
                date = datetime.fromtimestamp(float(date_value), UTC).date().isoformat()
            elif isinstance(date_value, str):
                try:
                    date = (
                        datetime.fromtimestamp(
                            float(date_value),
                            UTC,
                        )
                        .date()
                        .isoformat()
                    )
                except ValueError:
                    date = date_value[:10]
            else:
                continue
            dates.append(date)
            samples.append(
                {"date": date, "value": item.get("value") or item.get("tvl")}
            )

    unique_dates = sorted(set(dates))
    if not unique_dates:
        return None, None, None, None, None, _safe_rows(samples)

    first_date = unique_dates[0]
    last_date = unique_dates[-1]
    first = datetime.fromisoformat(first_date).replace(tzinfo=UTC)
    last = datetime.fromisoformat(last_date).replace(tzinfo=UTC)
    missing_days = max(0, (last - first).days + 1 - len(unique_dates))
    staleness = max(0.0, (datetime.now(UTC) - last).total_seconds() / 3600)
    return (
        first_date,
        last_date,
        len(unique_dates),
        missing_days,
        round(staleness, 2),
        _safe_rows(samples),
    )


def _error_class(exc: Exception) -> ErrorClass:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        text = str(exc).lower()
        if "name or service" in text or "nodename" in text:
            return "DNS"
        return "transport"
    if isinstance(exc, (ssl.SSLError, httpx.ConnectTimeout)):
        return "TLS"
    if isinstance(exc, socket.gaierror):
        return "DNS"
    return "transport"


def _rate_headers(response: httpx.Response) -> dict[str, str]:
    names = (
        "retry-after",
        "ratelimit-limit",
        "ratelimit-remaining",
        "ratelimit-reset",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "cf-ray",
    )
    return {
        name: str(response.headers[name]) for name in names if name in response.headers
    }


def _rpc_payload(spec: ProbeSpec) -> dict[str, Any]:
    if spec.source == "PublicNode":
        return {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
    if spec.source == "BNB RPC":
        return {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getRecentPerformanceSamples",
        "params": [4],
    }


async def probe(
    client: httpx.AsyncClient,
    spec: ProbeSpec,
    *,
    offline_payload: Any | None = None,
) -> tuple[ProbeResult, bool]:
    """Run one bounded probe; return a result and whether probing should stop."""
    started = time.perf_counter()
    try:
        if offline_payload is not None:
            response_status = 200
            payload = offline_payload
            headers = httpx.Headers()
            elapsed = int((time.perf_counter() - started) * 1000)
            if isinstance(payload, dict) and "http_status" in payload:
                response_status = int(payload.pop("http_status"))
        else:
            if spec.kind == "rpc":
                response = await client.post(
                    spec.endpoint,
                    json=_rpc_payload(spec),
                )
            else:
                response = await client.get(spec.endpoint)
            elapsed = int((time.perf_counter() - started) * 1000)
            headers = response.headers
            response_status = response.status_code
            if response_status == 429:
                return (
                    ProbeResult(
                        spec.source,
                        spec.endpoint,
                        list(spec.chains),
                        list(spec.metrics),
                        spec.granularity,
                        False,
                        "HTTP status",
                        "HTTP 429 rate limited",
                        elapsed,
                        response_status,
                        _rate_headers(response),
                        [],
                        None,
                        None,
                        None,
                        None,
                        None,
                        [],
                        True,
                    ),
                    True,
                )
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = {"_non_json": True}
            if response_status >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {response_status}",
                    request=response.request,
                    response=response,
                )
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        error = _error_class(exc)
        detail = f"{type(exc).__name__}: {exc}"[:300]
        if isinstance(exc, httpx.HTTPStatusError):
            response_status = exc.response.status_code
            detail = f"HTTP {response_status}"
        else:
            response_status = None
        return (
            ProbeResult(
                spec.source,
                spec.endpoint,
                list(spec.chains),
                list(spec.metrics),
                spec.granularity,
                False,
                error,
                detail,
                elapsed,
                response_status,
                {},
                [],
                None,
                None,
                None,
                None,
                None,
                [],
                True,
            ),
            False,
        )

    time_summary: tuple[
        str | None,
        str | None,
        int | None,
        int | None,
        float | None,
        list[dict[str, Any]],
    ] = (None, None, None, None, None, [])
    if spec.granularity.startswith(("daily", "1d")):
        time_summary = _time_series_summary(payload, spec)
    elif spec.source == "mempool.space" and "hashrate" in spec.endpoint:
        time_summary = _time_series_summary(payload, spec)

    return (
        ProbeResult(
            spec.source,
            spec.endpoint,
            list(spec.chains),
            list(spec.metrics),
            spec.granularity,
            True,
            "none",
            None,
            elapsed,
            response_status,
            _rate_headers(
                httpx.Response(
                    response_status if response_status is not None else 200,
                    headers=headers,
                )
            ),
            _top_level_keys(payload),
            time_summary[0],
            time_summary[1],
            time_summary[2],
            time_summary[3],
            time_summary[4],
            time_summary[5],
            True,
        ),
        False,
    )


def _load_offline_fixture(spec: ProbeSpec) -> Any:
    path = FIXTURE_DIR / spec.offline_fixture
    return json.loads(path.read_text(encoding="utf-8"))


async def run_audit(
    sources: set[str] | None = None,
    *,
    offline_fixtures: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    specs = _probe_specs()
    if sources:
        specs = tuple(spec for spec in specs if spec.source in sources)

    if offline_fixtures:
        timeout = httpx.Timeout(10)
        transport = transport or httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=_load_offline_fixture(
                    specs[0],
                ),
                request=request,
            )
        )
    else:
        timeout = httpx.Timeout(12.0, connect=8.0)

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    started = time.perf_counter()
    results: list[ProbeResult] = []
    stopped_sources: set[str] = set()
    async with httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        follow_redirects=True,
        transport=transport,
    ) as client:
        for spec in specs:
            if spec.source in stopped_sources:
                continue
            print(f"probing={spec.source} | bounded={spec.granularity}", flush=True)
            if offline_fixtures:
                payload = _load_offline_fixture(spec)
                result, stop = await probe(client, spec, offline_payload=payload)
            else:
                result, stop = await probe(client, spec)
                await asyncio.sleep(1.0)
                if not stop and result.error_class in {
                    "timeout",
                    "transport",
                    "DNS",
                    "TLS",
                }:
                    await asyncio.sleep(1.0)
                    retried, stop = await probe(client, spec)
                    result = retried
            results.append(result)
            if stop:
                stopped_sources.add(spec.source)

    duration = round(time.perf_counter() - started, 2)
    return {
        "audit": "ChainCompass free public data source audit",
        "run_date": datetime.now(UTC).date().isoformat(),
        "network_condition": "Iran + VPN; results may differ from a server abroad",
        "user_agent": USER_AGENT,
        "bounded_history": True,
        "duration_seconds": duration,
        "offline_fixtures": offline_fixtures,
        "sources_probed": sorted({result.source for result in results}),
        "stopped_sources": sorted(stopped_sources),
        "results": [asdict(result) for result in results],
    }


def write_json(report: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"audit_{report['run_date']}.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2)[:500_000],
        encoding="utf-8",
    )
    return path


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# ChainCompass Free Data Audit",
        "",
        f"Run date: {report['run_date']}",
        "",
        "Network condition: Iran + VPN. Results may differ from a server abroad.",
        "",
        "## Reachability",
        "",
        "| Source | Endpoint | Reachable | Error | HTTP | Latency |",
        "|---|---|---|---|---:|---:|",
    ]
    for result in report["results"]:
        host = urlparse(result["endpoint"]).netloc or "RPC"
        error = result["error_detail"] or "none"
        http_status = (
            result["http_status"] if result["http_status"] is not None else "-"
        )
        latency = (
            f"{result['latency_ms']} ms" if result["latency_ms"] is not None else "-"
        )
        lines.append(
            f"| {result['source']} | {host} | "
            f"{'yes' if result['reachable'] else 'no'} | "
            f"{result['error_class']}: {error} | {http_status} | {latency} |"
        )
    lines.extend(
        [
            "",
            "## Coverage matrix",
            "",
            "| Metric | BTC | ETH | SOL | BNB |",
            "|---|---|---|---|---|",
            "| Price | CoinGecko/Binance; bounded | "
            "CoinGecko/Binance; bounded | "
            "CoinGecko/Binance; bounded | CoinGecko/Binance; bounded |",
            "| Volume | CoinGecko/Binance | CoinGecko/Binance | "
            "CoinGecko/Binance | CoinGecko/Binance |",
            "| Market cap | CoinGecko community endpoint | "
            "CoinGecko community endpoint | CoinGecko community endpoint | "
            "CoinGecko community endpoint |",
            "| Active addresses | NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED |",
            "| Tx count | NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED |",
            "| Fees | mempool.space / public fee sample | "
            "NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED | "
            "NOT AVAILABLE FREE / UNVERIFIED |",
            "| TVL | NOT AVAILABLE FREE | "
            "DefiLlama; UNVERIFIED depth | "
            "DefiLlama; UNVERIFIED depth | "
            "DefiLlama; UNVERIFIED depth |",
            "| Stablecoin supply | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |",
            "| Hashrate/validators | mempool.space and Blockchain.info; "
            "bounded BTC history | UNVERIFIED | UNVERIFIED | UNVERIFIED |",
            "",
            "## Source licenses and terms",
            "",
            "- DefiLlama: https://defillama.com/terms",
            "- CoinGecko: https://www.coingecko.com/en/api_terms",
            "- Coin Metrics: https://coinmetrics.io/terms/",
            "- mempool.space: https://mempool.space/docs/api/rest",
            "- Blockchain.info: https://www.blockchain.com/legal/privacy",
            "- Binance data-api: https://data-api.binance.vision/",
            "- Blockchair: https://blockchair.com/api/docs",
            "- PublicNode: https://www.publicnode.com/terms",
            "- Solana public RPC: https://solana.com/terms",
            "- BNB public RPC: https://www.bnbchain.org/en/terms",
            "",
            "## Rate-limit notes",
            "",
            "- The audit pauses one second between live probes and retries "
            "each request at most once.",
            "- A 429 stops further probing of that source and records "
            "Retry-After and rate-limit headers.",
            "- Rate limits are source-specific and may differ for VPN exit "
            "nodes and cloud servers.",
            "",
            "## DECISION",
            "",
            "- Primary: Binance public market klines and CoinGecko for basic "
            "price/volume/market-cap coverage, subject to live measurement.",
            "- Fallback: DefiLlama for TVL/stablecoin context; "
            "mempool.space/Blockchain.info for BTC security metrics.",
            "- ChainCompass will not offer unsupported active-address, "
            "transaction, fee, TVL, stablecoin, or validator coverage as facts "
            "unless a live/community-tier result proves it.",
            "- Network Health Score should initially use only measured, dated "
            "components. Missing components remain unavailable rather than "
            "imputed.",
            "",
            f"Live run duration: {report['duration_seconds']} seconds.",
            "",
            "This document is evidence from the machine's live run or offline "
            "fixture mode. UNVERIFIED items must not be presented as supported.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=USER_AGENT)
    parser.add_argument("--sources", default="")
    parser.add_argument("--offline-fixtures", action="store_true")
    args = parser.parse_args()

    sources = {item.strip() for item in args.sources.split(",") if item.strip()} or None
    report = asyncio.run(
        run_audit(sources=sources, offline_fixtures=args.offline_fixtures)
    )
    json_path = write_json(report)
    logging.basicConfig(level=logging.INFO)
    logging.info("Audit JSON written to %s", json_path)
    print(f"audit_duration_seconds={report['duration_seconds']}")
    print(f"reachable={sum(1 for row in report['results'] if row['reachable'])}")
    print(f"probes={len(report['results'])}")


if __name__ == "__main__":
    main()
