from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingestion.http import PoliteHttpClient
from app.ingestion.provider import ChainContext, Point


class DefiLlamaProvider:
    source_code = "defillama"
    provider_code = "defillama"
    overlap_days = 3
    chain_names = {"eth": "ethereum", "sol": "solana", "bnb": "bsc"}
    endpoints = {
        "tvl_usd": "https://api.llama.fi/v2/historicalChainTvl/",
        "stablecoin_supply_usd": "https://stablecoins.llama.fi/stablecoincharts/",
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
        base_url = self.endpoints.get(metric)
        chain_name = self.chain_names.get(chain.code)
        if base_url is None or chain_name is None:
            return []
        payload = await self.http.get_json(
            base_url + chain_name,
            {
                "start": int(
                    datetime.combine(start_date, datetime.min.time(), UTC).timestamp()
                ),
                "end": int(
                    datetime.combine(end_date, datetime.max.time(), UTC).timestamp()
                ),
            },
        )
        if not isinstance(payload, list):
            raise ValueError("DefiLlama response was not a list")
        points: list[Point] = []
        current_day = datetime.now(UTC).date()
        for row in payload:
            point = self._point(row, metric)
            if point is not None and start_date <= point.date <= end_date:
                if point.date < current_day:
                    points.append(point)
        return points

    @classmethod
    def _point(cls, row: Any, metric: str) -> Point | None:
        if not isinstance(row, dict):
            return None
        timestamp = row.get("date")
        if not isinstance(timestamp, (int, float, Decimal, str)):
            return None
        try:
            obs_date = datetime.fromtimestamp(
                int(Decimal(str(timestamp))),
                UTC,
            ).date()
            raw_value = (
                row.get("tvl") if metric == "tvl_usd" else cls._stablecoin_value(row)
            )
            value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            return None
        return Point(obs_date, value)

    @staticmethod
    def _stablecoin_value(row: dict[str, Any]) -> str | Decimal | int | float | None:
        totals = row.get("totalCirculatingUSD")
        if isinstance(totals, dict):
            pegged_usd = totals.get("peggedUSD")
            if isinstance(pegged_usd, (str, Decimal, int, float)):
                return pegged_usd
            values = [
                value
                for value in totals.values()
                if isinstance(value, (str, Decimal, int, float))
            ]
            return sum((Decimal(str(value)) for value in values), Decimal(0))
        if isinstance(totals, (str, Decimal, int, float)):
            return totals
        return None
