import asyncio
import math
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import Request

from app.core.config import settings
from app.core.errors import APIError


class RateLimiter(Protocol):
    async def consume(
        self, key: str, limit: int, window: timedelta, now: datetime
    ) -> int | None: ...


class InMemorySlidingWindow:
    def __init__(self) -> None:
        self._events: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def consume(
        self, key: str, limit: int, window: timedelta, now: datetime
    ) -> int | None:
        async with self._lock:
            events = self._events[key]
            cutoff = now - window
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(1, math.ceil((events[0] + window - now).total_seconds()))
            events.append(now)
            return None

    async def clear(self) -> None:
        async with self._lock:
            self._events.clear()


rate_limiter: RateLimiter = InMemorySlidingWindow()


def rate_limit_clock() -> datetime:
    return datetime.now(UTC)


def reset_rate_limiter() -> None:
    global rate_limiter
    rate_limiter = InMemorySlidingWindow()


def client_ip(request: Request) -> str:
    if settings.trust_proxy:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    bucket: str,
    key: str,
    limit: int,
    window: timedelta,
) -> None:
    retry_after = await rate_limiter.consume(
        f"{bucket}:{key}", limit, window, rate_limit_clock()
    )
    if retry_after is not None:
        raise APIError(
            429,
            "rate_limited",
            "Too many requests",
            headers={"Retry-After": str(retry_after)},
        )
