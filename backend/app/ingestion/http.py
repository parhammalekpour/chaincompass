from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "ChainCompass/0.1 (+https://github.com/parhammalekpour/chaincompass)"


class ProviderStopped(Exception):
    pass


class PoliteHttpClient:
    def __init__(
        self,
        *,
        minimum_interval_seconds: float = 1.0,
        max_retries: int = 2,
        timeout_seconds: float = 12.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.minimum_interval_seconds = minimum_interval_seconds
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self._last_request_at: float | None = None
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def get_json(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
    ) -> object:
        loop = asyncio.get_running_loop()
        if self._last_request_at is not None:
            elapsed = loop.time() - self._last_request_at
            remaining = self.minimum_interval_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

        for attempt in range(self.max_retries + 1):
            try:
                self._last_request_at = loop.time()
                response = await self.client.get(url, params=params)
            except httpx.TimeoutException:
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep((2**attempt) + random.uniform(0.0, 0.25))
                continue
            except httpx.RequestError:
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep((2**attempt) + random.uniform(0.0, 0.25))
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                logger.warning(
                    "Provider rate limited; retry-after=%s",
                    retry_after or "unset",
                )
                if retry_after:
                    try:
                        await asyncio.sleep(max(0.0, float(retry_after)))
                    except ValueError:
                        try:
                            retry_at = parsedate_to_datetime(retry_after)
                            if retry_at.tzinfo is None:
                                retry_at = retry_at.replace(tzinfo=UTC)
                            await asyncio.sleep(
                                max(
                                    0.0,
                                    (retry_at - datetime.now(UTC)).total_seconds(),
                                )
                            )
                        except (TypeError, ValueError, OverflowError):
                            logger.warning("Ignoring invalid Retry-After header")
                raise ProviderStopped("provider rate limited with HTTP 429")
            if response.status_code >= 400:
                body = " ".join(response.text.split())[:200]
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {body}",
                    request=response.request,
                    response=response,
                )
            try:
                return json.loads(response.content, parse_float=Decimal)
            except json.JSONDecodeError as exc:
                raise ValueError("Provider response was not JSON") from exc
        raise RuntimeError("Provider request exhausted retries")
