from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.auth.dependencies import get_session
from app.core.security import create_access_token
from app.db.models.agent import ChatConversation, ChatMessage, LLMUsage
from app.db.models.auth import User
from app.main import create_app


@dataclass(frozen=True)
class AgentTestContext:
    client: AsyncClient
    app: FastAPI
    session_factory: async_sessionmaker[AsyncSession]
    user_id: UUID
    user_email: str
    token: str
    other_user_id: UUID
    other_token: str


@pytest_asyncio.fixture(loop_scope="session")
async def agent_context(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AgentTestContext]:
    suffix = uuid4().hex
    email = f"agent-{suffix}@example.test"
    other_email = f"agent-other-{suffix}@example.test"
    async with auth_session_factory() as session:
        user = User(email=email, locale="en")
        other_user = User(email=other_email, locale="fa")
        session.add_all([user, other_user])
        await session.commit()
        await session.refresh(user)
        await session.refresh(other_user)
        user_id = user.id
        other_user_id = other_user.id

    application = create_app()
    application.state.agent_provider = None

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with auth_session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield AgentTestContext(
            client=client,
            app=application,
            session_factory=auth_session_factory,
            user_id=user_id,
            user_email=email,
            token=create_access_token(str(user_id), "user"),
            other_user_id=other_user_id,
            other_token=create_access_token(str(other_user_id), "user"),
        )
    application.dependency_overrides.clear()
    async with auth_session_factory() as session:
        await session.execute(
            delete(ChatMessage).where(
                ChatMessage.conversation_id.in_(
                    select_conversation_ids(user_id, other_user_id)
                )
            )
        )
        await session.execute(
            delete(LLMUsage).where(LLMUsage.user_id.in_([user_id, other_user_id]))
        )
        await session.execute(
            delete(ChatConversation).where(
                ChatConversation.user_id.in_([user_id, other_user_id])
            )
        )
        await session.execute(delete(User).where(User.email.in_([email, other_email])))
        await session.commit()


def select_conversation_ids(user_id: UUID, other_user_id: UUID):
    return select(ChatConversation.id).where(
        ChatConversation.user_id.in_([user_id, other_user_id])
    )
