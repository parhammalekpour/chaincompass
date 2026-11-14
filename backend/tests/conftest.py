import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.auth import router as auth_router
from app.api.v1.auth.dependencies import require_role, require_verified_user
from app.api.v1.auth.router import get_session
from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models.auth import User
from app.main import create_app
from app.services.email import OutgoingEmail
from app.services.rate_limit import reset_rate_limiter


class CapturingEmailSender:
    def __init__(self) -> None:
        self.messages: list[OutgoingEmail] = []
        self.fail = False

    async def send(self, message: OutgoingEmail) -> None:
        if self.fail:
            raise RuntimeError("test email transport failure")
        self.messages.append(message)


@pytest.fixture
def captured_email_sender(monkeypatch: pytest.MonkeyPatch) -> CapturingEmailSender:
    sender = CapturingEmailSender()
    monkeypatch.setattr(auth_router, "email_sender", sender)
    reset_rate_limiter()
    return sender


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def auth_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    schema = f"auth_test_{uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with admin_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        await admin_engine.dispose()
        if os.environ.get("CI", "").lower() == "true":
            # CI must exercise these tests; an unavailable DB is a failure.
            pytest.fail(f"PostgreSQL is not reachable in CI: {type(exc).__name__}")
        pytest.skip("PostgreSQL is not reachable")

    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_engine = create_async_engine(
        settings.database_url,
        connect_args={"server_settings": {"search_path": schema}},
        poolclass=NullPool,
    )
    try:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(test_engine, expire_on_commit=False)
    finally:
        await test_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def auth_client(
    auth_session_factory: async_sessionmaker[AsyncSession],
    captured_email_sender: CapturingEmailSender,
) -> AsyncIterator[AsyncClient]:
    application = create_app()

    @application.get("/_admin-check")
    async def admin_check(
        user: User = Depends(require_role("admin")),
    ) -> dict[str, str]:
        return {"role": user.role}

    @application.get("/_verified-check")
    async def verified_check(
        user: User = Depends(require_verified_user),
    ) -> dict[str, str]:
        return {"email": user.email}

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with auth_session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client
    application.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def clean_auth_tables(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async with auth_session_factory() as session:
        await session.execute(text("DELETE FROM email_tokens"))
        await session.execute(text("DELETE FROM oauth_accounts"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()
    yield
