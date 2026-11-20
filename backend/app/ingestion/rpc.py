from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models.ingestion import RpcProbe
from app.db.session import SessionFactory
from app.ingestion.http import USER_AGENT

BLOCK_AGE_CLOCK_SKEW_TOLERANCE_SECONDS = 60
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass(frozen=True)
class RpcEndpoints:
    btc_tip: str
    eth: str
    sol: str
    bnb: str

    @classmethod
    def from_settings(cls) -> RpcEndpoints:
        return cls(
            btc_tip=settings.rpc_btc_tip_url,
            eth=settings.rpc_eth_url,
            sol=settings.rpc_sol_url,
            bnb=settings.rpc_bnb_url,
        )


@dataclass(frozen=True)
class RpcProbeResult:
    chain_id: str
    provider_label: str
    checked_at: datetime
    ok: bool
    latency_ms: int
    block_height: int | None
    block_age_seconds: int | None
    error_code: str | None


class RpcProbeError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code[:64]
        super().__init__(self.error_code)


def _positive_int(value: Any, *, hexadecimal: bool = False) -> int:
    if isinstance(value, bool):
        raise RpcProbeError("invalid_response")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = (
                int(value, 16)
                if hexadecimal and value.lower().startswith("0x")
                else int(value)
            )
        except ValueError as exc:
            raise RpcProbeError("invalid_response") from exc
    else:
        raise RpcProbeError("invalid_response")
    if parsed <= 0:
        raise RpcProbeError("invalid_response")
    return parsed


class RpcProbeClient:
    def __init__(
        self,
        *,
        endpoints: RpcEndpoints | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.endpoints = endpoints or RpcEndpoints.from_settings()
        self.now = now or (lambda: datetime.now(UTC))
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def probe(self, chain_id: str) -> RpcProbeResult:
        started = time.perf_counter()
        provider_label = {
            "btc": "mempool.space",
            "eth": "publicnode",
            "sol": "solana-mainnet-beta",
            "bnb": "bsc-dataseed",
        }.get(chain_id)
        if provider_label is None:
            raise ValueError(f"unsupported chain: {chain_id}")

        height: int | None = None
        age_seconds: int | None = None
        error_code: str | None = None
        ok = False
        try:
            if chain_id == "btc":
                height = await self._btc_tip_height()
            elif chain_id in {"eth", "bnb"}:
                url = self.endpoints.eth if chain_id == "eth" else self.endpoints.bnb
                block = await self._json_rpc(
                    url,
                    "eth_getBlockByNumber",
                    ["latest", False],
                )
                if not isinstance(block, dict):
                    raise RpcProbeError("invalid_response")
                height = _positive_int(block.get("number"), hexadecimal=True)
                timestamp = _positive_int(block.get("timestamp"), hexadecimal=True)
                age_seconds, error_code = self._block_age(timestamp)
            else:
                slot_result = await self._json_rpc(
                    self.endpoints.sol,
                    "getSlot",
                    [{"commitment": "finalized"}],
                )
                height = _positive_int(slot_result)
                try:
                    block_time = await self._json_rpc(
                        self.endpoints.sol,
                        "getBlockTime",
                        [height],
                    )
                    timestamp = _positive_int(block_time)
                    age_seconds, error_code = self._block_age(timestamp)
                except (RpcProbeError, httpx.RequestError):
                    error_code = "block_time_unavailable"
            ok = True
        except RpcProbeError as exc:
            error_code = exc.error_code
        except httpx.TimeoutException:
            error_code = "timeout"
        except httpx.RequestError:
            error_code = "network_error"
        except (ValueError, TypeError, OverflowError):
            error_code = "invalid_response"

        return RpcProbeResult(
            chain_id=chain_id,
            provider_label=provider_label,
            checked_at=self.now().astimezone(UTC),
            ok=ok,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            block_height=height,
            block_age_seconds=age_seconds,
            error_code=error_code,
        )

    async def _btc_tip_height(self) -> int:
        response = await self.client.get(self.endpoints.btc_tip)
        if response.status_code == 429:
            raise RpcProbeError("http_429")
        if response.status_code >= 400:
            raise RpcProbeError(f"http_{response.status_code}")
        return _positive_int(response.text.strip())

    async def _json_rpc(
        self,
        url: str,
        method: str,
        params: list[Any],
    ) -> Any:
        response = await self.client.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        if response.status_code == 429:
            raise RpcProbeError("http_429")
        if response.status_code >= 400:
            raise RpcProbeError(f"http_{response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise RpcProbeError("invalid_response") from exc
        if (
            not isinstance(payload, dict)
            or "error" in payload
            or "result" not in payload
        ):
            raise RpcProbeError(
                "rpc_error" if isinstance(payload, dict) else "invalid_response"
            )
        return payload["result"]

    def _block_age(self, timestamp: int) -> tuple[int | None, str | None]:
        age = int(self.now().astimezone(UTC).timestamp()) - timestamp
        if age >= 0:
            return age, None
        if age >= -BLOCK_AGE_CLOCK_SKEW_TOLERANCE_SECONDS:
            return 0, "clock_skew_clamped"
        raise RpcProbeError("invalid_response")


async def probe_all(
    *,
    client: RpcProbeClient | None = None,
) -> list[RpcProbeResult]:
    owns_client = client is None
    probe_client = client or RpcProbeClient()
    try:
        results: list[RpcProbeResult] = []
        chains = ("btc", "eth", "sol", "bnb")
        for index, chain_id in enumerate(chains):
            results.append(await probe_client.probe(chain_id))
            if index < len(chains) - 1:
                await asyncio.sleep(1)
        return results
    finally:
        if owns_client:
            await probe_client.close()


async def probe_and_store(
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    client: RpcProbeClient | None = None,
) -> list[RpcProbeResult]:
    results = await probe_all(client=client)
    async with session_factory() as session:
        session.add_all(
            [
                RpcProbe(
                    id=uuid4(),
                    chain_id=result.chain_id,
                    provider_label=result.provider_label,
                    checked_at=result.checked_at,
                    ok=result.ok,
                    latency_ms=result.latency_ms,
                    block_height=result.block_height,
                    block_age_seconds=result.block_age_seconds,
                    error_code=result.error_code,
                )
                for result in results
            ]
        )
        await session.commit()
    return results


async def prune_probes(
    days: int = 30,
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> int:
    if days <= 0:
        raise ValueError("retention days must be greater than zero")
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(RpcProbe)
            .where(RpcProbe.checked_at < cutoff)
        )
        await session.execute(delete(RpcProbe).where(RpcProbe.checked_at < cutoff))
        await session.commit()
    return int(count or 0)


async def run_rpc_probe_job(
    *,
    client: RpcProbeClient | None = None,
) -> list[RpcProbeResult]:
    return await probe_and_store(client=client)
