from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.score_config import CHAINS, VERSION
from app.db.models.health import MarketRegime
from app.ml.dataset import DatasetRow

RowKey = tuple[str, date]


@dataclass(frozen=True)
class VolStateLookup:
    by_row: Mapping[RowKey, str]
    distinct_values: tuple[str, ...]
    missing_eligible_rows: int


def build_vol_state_lookup(
    rows: Sequence[DatasetRow],
    stored_values: Mapping[RowKey, str | None],
) -> VolStateLookup:
    by_row: dict[RowKey, str] = {}
    distinct_values: set[str] = set()
    missing = 0
    for row in rows:
        key = (row.chain, row.obs_date)
        value = stored_values.get(key)
        if value is None:
            by_row[key] = "missing"
            missing += 1
        else:
            by_row[key] = value
            distinct_values.add(value)
    return VolStateLookup(
        by_row=by_row,
        distinct_values=tuple(sorted(distinct_values)),
        missing_eligible_rows=missing,
    )


async def load_vol_state_lookup(
    session: AsyncSession,
    rows: Sequence[DatasetRow],
) -> VolStateLookup:
    if not rows:
        return build_vol_state_lookup(rows, {})
    first_date = min(row.obs_date for row in rows)
    last_date = max(row.obs_date for row in rows)
    result = await session.execute(
        select(
            MarketRegime.chain_id,
            MarketRegime.as_of_date,
            MarketRegime.vol_state,
        ).where(
            MarketRegime.chain_id.in_(CHAINS),
            MarketRegime.version == VERSION,
            MarketRegime.as_of_date >= first_date,
            MarketRegime.as_of_date <= last_date,
        )
    )
    stored_values: dict[RowKey, str | None] = {
        (chain, as_of_date): value for chain, as_of_date, value in result
    }
    return build_vol_state_lookup(rows, stored_values)
