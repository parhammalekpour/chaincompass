import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.session import engine as application_engine

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20261121_0009_agent.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location(
        "agent_migration_0009", MIGRATION_FILE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load agent schema migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_agent_migration_upgrades_and_downgrades_cleanly() -> None:
    schema = f"agent_migration_test_{uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with admin_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        await admin_engine.dispose()
        if os.environ.get("CI", "").lower() == "true":
            pytest.fail(f"PostgreSQL is not reachable in CI: {type(exc).__name__}")
        pytest.skip("PostgreSQL is not reachable")

    test_engine = None
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        test_engine = create_async_engine(
            settings.database_url,
            connect_args={"server_settings": {"search_path": schema}},
            poolclass=NullPool,
        )
        async with test_engine.begin() as connection:
            await connection.execute(
                text("CREATE TABLE users (id UUID PRIMARY KEY NOT NULL)")
            )
            module = _migration_module()

            def upgrade(sync_connection) -> None:
                with Operations.context(MigrationContext.configure(sync_connection)):
                    module.upgrade()

            await connection.run_sync(upgrade)
            table_names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
            assert {"users", "chat_conversations", "chat_messages", "llm_usage"} <= set(
                table_names
            )
            user_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("users")
                }
            )
            assert user_columns == {"id"}

            def downgrade(sync_connection) -> None:
                with Operations.context(MigrationContext.configure(sync_connection)):
                    module.downgrade()

            await connection.run_sync(downgrade)
            table_names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
            assert table_names == ["users"]
    finally:
        if test_engine is not None:
            await test_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()
        await application_engine.dispose()
