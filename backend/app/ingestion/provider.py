from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Point:
    date: date
    value: Decimal


@dataclass(frozen=True)
class ChainContext:
    code: str
    symbol: str


class MetricProvider(Protocol):
    overlap_days: int

    async def fetch(
        self,
        chain: ChainContext,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> list[Point]: ...
