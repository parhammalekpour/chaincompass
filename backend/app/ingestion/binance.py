from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from app.ingestion.http import PoliteHttpClient
from app.ingestion.provider import ChainContext, Point


class BinanceKlinesProvider:
    source_code = "binance"
    provider_code = "binance"
    overlap_days = 3
    symbols = {
        "btc": "BTCUSDT",
        "eth": "ETHUSDT",
        "sol": "SOLUSDT",
        "bnb": "BNBUSDT",
    }

    def __init__(
        self,
        *,
        http: PoliteHttpClient | None = None,
        minimum_interval_seconds: float = 1.0,
    ) -> None:
        self.http = http or PoliteHttpClient(
            minimum_interval_seconds=minimum_interval_seconds
        )
        self.base_url = "https://data-api.binance.vision/api/v3/klines"

    async def close(self) -> None:
        await self.http.close()

    async def fetch(
        self,
        chain: ChainContext,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> list[Point]:
        symbol = self.symbols.get(chain.code)
        if symbol is None:
            return []
        start_ms = int(
            datetime.combine(start_date, datetime.min.time(), UTC).timestamp() * 1000
        )
        end_ms = int(
            datetime.combine(end_date, datetime.max.time(), UTC).timestamp() * 1000
        )
        points: list[Point] = []
        cursor = start_ms
        while cursor <= end_ms:
            payload = await self.http.get_json(
                self.base_url,
                {
                    "symbol": symbol,
                    "interval": "1d",
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            if not isinstance(payload, list) or not payload:
                break
            for row in payload:
                if not isinstance(row, list) or len(row) < 11:
                    continue
                try:
                    open_ms = int(row[0])
                    close = Decimal(str(row[4]))
                    quote_volume = Decimal(str(row[7]))
                except (InvalidOperation, TypeError, ValueError, KeyError):
                    continue
                obs_date = datetime.fromtimestamp(open_ms / 1000, UTC).date()
                yesterday = datetime.now(UTC).date()
                yesterday = yesterday.fromordinal(yesterday.toordinal() - 1)
                if obs_date > yesterday:
                    continue
                if obs_date < start_date or obs_date > end_date:
                    continue
                value = close if metric == "price_close_usd" else quote_volume
                points.append(Point(date=obs_date, value=value))
            last_open_ms = int(payload[-1][0])
            next_cursor = last_open_ms + 86_400_000
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(payload) < 1000:
                break
        return points
