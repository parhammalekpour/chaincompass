from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine
from app.research.repository import load_research_data


@pytest.mark.asyncio
async def test_research_loader_uses_existing_database_read_only() -> None:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        if os.environ.get("CI", "").lower() == "true":
            pytest.fail(f"PostgreSQL is not reachable in CI: {type(exc).__name__}")
        pytest.skip("PostgreSQL is not reachable")

    data = await load_research_data()

    assert set(data.prices_by_chain) == {"btc", "eth", "sol", "bnb"}
    assert set(data.scores_by_chain) == {"btc", "eth", "sol", "bnb"}
