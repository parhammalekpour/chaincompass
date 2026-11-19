from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingestion.http import PoliteHttpClient
from app.ingestion.provider import ChainContext, Point


def btc_fees_to_usd(
    fee_points: list[Point],
    btc_closes: dict[date, Decimal],
) -> tuple[list[Point], int]:
    converted = [
        Point(point.date, point.value * btc_closes[point.date])
        for point in fee_points
        if point.date in btc_closes
    ]
    return converted, len(fee_points) - len(converted)


class BtcNetworkProvider:
    source_code = "blockchain_info"
    provider_code = "btcnet"
    overlap_days = 3
    chart_urls = {
        "hashrate": "https://api.blockchain.info/charts/hash-rate",
        "fees_usd": "https://api.blockchain.info/charts/transaction-fees",
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

    async def close(self) -> None:
        await self.http.close()

    async def fetch(
        self,
        chain: ChainContext,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> list[Point]:
        if chain.code != "btc" or metric not in self.chart_urls:
            return []
        points: list[Point] = []
        current_day = datetime.now(UTC).date()
        cursor = start_date
        while cursor <= end_date:
            window_end = min(cursor + timedelta(days=364), end_date)
            start = int(datetime.combine(cursor, datetime.min.time(), UTC).timestamp())
            end = int(
                datetime.combine(window_end, datetime.max.time(), UTC).timestamp()
            )
            payload = await self.http.get_json(
                self.chart_urls[metric],
                {
                    "start": start,
                    "end": end,
                    "format": "json",
                    "sampled": "false",
                },
            )
            if not isinstance(payload, dict):
                raise ValueError("Blockchain.info chart response was not an object")
            unit = payload.get("unit")
            if metric == "hashrate" and (
                not isinstance(unit, str) or "TH/s" not in unit
            ):
                raise ValueError("Blockchain.info hashrate chart unit is not TH/s")
            if metric == "fees_usd" and unit != "BTC":
                raise ValueError("Blockchain.info transaction-fees unit is not BTC")
            values = payload.get("values")
            if not isinstance(values, list):
                raise ValueError("Blockchain.info chart response has no values list")
            for row in values:
                point = self._point(row, metric)
                if (
                    point is not None
                    and cursor <= point.date <= window_end
                    and point.date < current_day
                ):
                    points.append(point)
            cursor = window_end + timedelta(days=1)
        return points

    @staticmethod
    def _point(row: Any, metric: str) -> Point | None:
        if not isinstance(row, dict):
            return None
        timestamp = row.get("x")
        raw_value = row.get("y")
        if not isinstance(timestamp, (int, float, Decimal)) or raw_value is None:
            return None
        try:
            obs_date = datetime.fromtimestamp(int(timestamp), UTC).date()
            value = Decimal(str(raw_value))
            if metric == "hashrate":
                value *= Decimal("1000000000000")
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            return None
        return Point(obs_date, value)
