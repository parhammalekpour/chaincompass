from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin

from app.ingestion.http import PoliteHttpClient
from app.ingestion.provider import ChainContext, Point


class CoinMetricsProvider:
    source_code = "coin_metrics"
    provider_code = "coinmetrics"
    overlap_days = 7
    metric_names = {
        "market_cap_usd": "CapMrktCurUSD",
        "active_addresses": "AdrActCnt",
        "tx_count": "TxCnt",
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
        self.base_url = "https://community-api.coinmetrics.io/v4/"

    async def close(self) -> None:
        await self.http.close()

    async def fetch(
        self,
        chain: ChainContext,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> list[Point]:
        metric_name = self.metric_names.get(metric)
        if metric_name is None:
            return []
        url = urljoin(self.base_url, "timeseries/asset-metrics")
        params: dict[str, str | int] | None = {
            "assets": chain.code,
            "metrics": metric_name,
            "frequency": "1d",
            "start_time": start_date.isoformat(),
            "end_time": end_date.isoformat(),
            "page_size": 10000,
        }
        points: list[Point] = []
        current_day = datetime.now(UTC).date()
        while url:
            payload = await self.http.get_json(url, params)
            params = None
            if not isinstance(payload, dict):
                raise ValueError("Coin Metrics response was not an object")
            data = payload.get("data")
            if not isinstance(data, list):
                raise ValueError("Coin Metrics response has no data list")
            for row in data:
                if not isinstance(row, dict):
                    continue
                point = self._point(row, metric_name)
                if (
                    point is not None
                    and start_date <= point.date <= end_date
                    and point.date < current_day
                ):
                    points.append(point)
            next_page = payload.get("next_page_url")
            url = (
                urljoin(self.base_url, next_page) if isinstance(next_page, str) else ""
            )
        return points

    @staticmethod
    def _point(row: dict[str, Any], metric_name: str) -> Point | None:
        timestamp = row.get("time")
        value = row.get(metric_name)
        if not isinstance(timestamp, str) or value is None:
            return None
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            obs_date = parsed.astimezone(UTC).date()
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
        return Point(obs_date, decimal_value)
