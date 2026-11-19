from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.config import settings
from app.ingestion.http import USER_AGENT

MARKET_URL = "https://api.coingecko.com/api/v3/coins/markets"
CHAIN_BY_ID = {
    "bitcoin": "btc",
    "ethereum": "eth",
    "solana": "sol",
    "binancecoin": "bnb",
}


class CoinGeckoRateLimited(Exception):
    pass


class CoinGeckoRequestFailed(Exception):
    pass


@dataclass(frozen=True)
class MarketSnapshot:
    snapshot_at: datetime
    obs_date: date
    values: dict[str, Decimal]
    rows_rejected: int
    missing_chains: tuple[str, ...]


def previous_utc_date(snapshot_at: datetime) -> date:
    if snapshot_at.tzinfo is None:
        raise ValueError("snapshot timestamp must be timezone-aware")
    return snapshot_at.astimezone(UTC).date() - timedelta(days=1)


def parse_market_caps(payload: Any) -> tuple[dict[str, Decimal], int]:
    if not isinstance(payload, list):
        raise ValueError("CoinGecko market response must be a list")
    values: dict[str, Decimal] = {}
    rejected = 0
    for row in payload:
        if not isinstance(row, dict):
            rejected += 1
            continue
        asset_id = row.get("id")
        if not isinstance(asset_id, str):
            rejected += 1
            continue
        chain = CHAIN_BY_ID.get(asset_id)
        raw_value = row.get("market_cap")
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError):
            rejected += 1
            continue
        if (
            chain is None
            or not value.is_finite()
            or value <= 0
            or value.adjusted() > 25
            or chain in values
        ):
            rejected += 1
            continue
        values[chain] = value
    return values, rejected


class CoinGeckoClient:
    def __init__(
        self,
        *,
        api_key: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if api_key:
            headers["x-cg-demo-api-key"] = api_key
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def fetch(self) -> Any:
        params = {
            "vs_currency": "usd",
            "ids": "bitcoin,ethereum,solana,binancecoin",
        }
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(MARKET_URL, params=params)
            except httpx.RequestError as exc:
                if attempt >= self.max_retries:
                    raise CoinGeckoRequestFailed(
                        f"network request failed: {type(exc).__name__}"
                    ) from exc
                await asyncio.sleep((2**attempt) + random.uniform(0, 0.25))
                continue
            if response.status_code == 429:
                if attempt >= self.max_retries:
                    raise CoinGeckoRateLimited("HTTP 429 after retries")
                await _wait_retry_after(
                    response.headers.get("Retry-After"),
                    attempt,
                )
                continue
            if response.status_code >= 500 and attempt < self.max_retries:
                await asyncio.sleep((2**attempt) + random.uniform(0, 0.25))
                continue
            if response.status_code >= 400:
                raise CoinGeckoRequestFailed(
                    f"HTTP {response.status_code} from CoinGecko"
                )
            try:
                return json.loads(response.content, parse_float=Decimal)
            except json.JSONDecodeError as exc:
                raise CoinGeckoRequestFailed(
                    "CoinGecko response was not valid JSON"
                ) from exc
        raise CoinGeckoRequestFailed("request attempts exhausted")


async def _wait_retry_after(value: str | None, attempt: int) -> None:
    if value:
        try:
            await asyncio.sleep(max(0.0, float(value)))
            return
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                await asyncio.sleep(
                    max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
                )
                return
            except (TypeError, ValueError, OverflowError):
                pass
    await asyncio.sleep((2**attempt) + random.uniform(0, 0.25))


def make_market_snapshot(
    payload: Any,
    snapshot_at: datetime,
) -> MarketSnapshot:
    values, rejected = parse_market_caps(payload)
    return MarketSnapshot(
        snapshot_at=snapshot_at.astimezone(UTC),
        obs_date=previous_utc_date(snapshot_at),
        values=values,
        rows_rejected=rejected,
        missing_chains=tuple(sorted(set(CHAIN_BY_ID.values()) - values.keys())),
    )


def configured_api_key() -> str:
    return settings.coingecko_api_key
