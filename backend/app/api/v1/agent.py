import asyncio
import json
import logging
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.guardrails import (
    MessageTooLongError,
    classify_input,
    detect_language,
    validate_message_length,
)
from app.agent.orchestrator import (
    AgentNotConfiguredError,
    AgentOrchestrator,
    AgentRun,
    ToolInvocation,
)
from app.agent.providers.base import LLMProvider, ProviderError
from app.agent.providers.factory import create_configured_provider
from app.agent.providers.fake import FakeProvider
from app.api.v1.auth.dependencies import CurrentUserDependency
from app.core.config import settings
from app.core.errors import APIError
from app.db.models.agent import ChatConversation, ChatMessage, LLMUsage
from app.db.models.auth import User
from app.db.session import get_session
from app.schemas.agent import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
    MessageCreate,
    MessageResponse,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)
session_dependency = Annotated[AsyncSession, Depends(get_session)]
MAX_CONVERSATIONS_PER_USER = 50
MAX_MESSAGES_PER_CONVERSATION = 200
MAX_TURN_MESSAGES = 1 + 1 + 4
MAX_HISTORY_MESSAGES = 20
MAX_MESSAGES_PER_HOUR = 20
MAX_MESSAGES_PER_DAY = 100
AGENT_RATE_WINDOW_HOUR = timedelta(hours=1)
AGENT_RATE_WINDOW_DAY = timedelta(days=1)
orchestrator = AgentOrchestrator()


def _get_provider(request: Request) -> LLMProvider | None:
    provider = getattr(request.app.state, "agent_provider", None)
    if not hasattr(request.app.state, "agent_provider"):
        provider = create_configured_provider()
        request.app.state.agent_provider = provider
    return provider


provider_dependency = Annotated[LLMProvider | None, Depends(_get_provider)]


async def _check_message_rate_limit(user_id: UUID) -> None:
    key = str(user_id)
    await check_rate_limit(
        "agent-hour",
        key,
        MAX_MESSAGES_PER_HOUR,
        AGENT_RATE_WINDOW_HOUR,
    )
    await check_rate_limit(
        "agent-day",
        key,
        MAX_MESSAGES_PER_DAY,
        AGENT_RATE_WINDOW_DAY,
    )


async def _check_daily_token_budget(session: AsyncSession, user_id: UUID) -> None:
    now = datetime.now(UTC)
    day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    used = await session.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(LLMUsage.prompt_tokens, 0)
                    + func.coalesce(LLMUsage.completion_tokens, 0)
                ),
                0,
            )
        ).where(LLMUsage.user_id == user_id, LLMUsage.created_at >= day_start)
    )
    if int(used or 0) >= settings.llm_daily_token_budget:
        retry_after = max(
            1,
            int((day_start + timedelta(days=1) - now).total_seconds()),
        )
        raise APIError(
            429,
            "token_budget_exceeded",
            "Daily language model token budget is exhausted",
            headers={"Retry-After": str(retry_after)},
        )


def _provider_name(provider: LLMProvider | None) -> str:
    return "fake" if isinstance(provider, FakeProvider) else settings.llm_provider


def _provider_model(provider: LLMProvider | None) -> str:
    if isinstance(provider, FakeProvider):
        return "fake"
    return settings.llm_model or "unconfigured"


def _sse(event: str, data: Mapping[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _tool_call_data(invocation: ToolInvocation) -> dict[str, object]:
    return {"name": invocation.name, "args": invocation.arguments}


def _tool_result_data(invocation: ToolInvocation) -> dict[str, object]:
    return {
        "name": invocation.name,
        "ok": invocation.result.get("ok") is True,
        "summary": (
            "data_returned"
            if invocation.result.get("ok") is True
            else "data_unavailable"
        ),
    }


def _text_chunks(text: str, size: int = 32) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def _history_message(row: ChatMessage) -> dict[str, object] | None:
    if row.role not in {"user", "assistant"}:
        return None
    return {"role": row.role, "content": row.content}


async def _persist_run(
    *,
    session: AsyncSession,
    conversation: ChatConversation,
    user: User,
    provider: LLMProvider | None,
    assistant_id: UUID,
    result: AgentRun,
) -> None:
    created_at = datetime.now(UTC)
    for index, invocation in enumerate(result.tool_invocations):
        session.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="tool",
                content=json.dumps(
                    invocation.result,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                refusal=False,
                created_at=created_at + timedelta(microseconds=index),
            )
        )
    session.add(
        ChatMessage(
            id=assistant_id,
            conversation_id=conversation.id,
            role="assistant",
            content=result.text,
            tool_calls=[
                {"name": item.name, "arguments": item.arguments}
                for item in result.tool_invocations
            ]
            or None,
            grounding_status=result.grounding_status,
            refusal=result.refusal,
            created_at=created_at
            + timedelta(microseconds=len(result.tool_invocations)),
        )
    )
    session.add(
        LLMUsage(
            user_id=user.id,
            conversation_id=conversation.id,
            provider=_provider_name(provider),
            model=_provider_model(provider),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            latency_ms=result.latency_ms,
            status=result.grounding_status,
        )
    )
    conversation.updated_at = datetime.now(UTC)
    await session.commit()


async def _persist_failed_usage(
    *,
    session: AsyncSession,
    conversation: ChatConversation,
    user: User,
    provider: LLMProvider | None,
    status: str,
    started_at: datetime,
) -> None:
    session.add(
        LLMUsage(
            user_id=user.id,
            conversation_id=conversation.id,
            provider=_provider_name(provider),
            model=_provider_model(provider),
            latency_ms=max(
                0, round((datetime.now(UTC) - started_at).total_seconds() * 1000)
            ),
            status=status,
        )
    )
    await session.commit()


@router.post("/conversations", response_model=ConversationSummary, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: CurrentUserDependency,
    session: session_dependency,
) -> ChatConversation:
    locked_user = await session.scalar(
        select(User).where(User.id == user.id).with_for_update()
    )
    if locked_user is None:
        raise APIError(401, "invalid_access_token", "Access token is invalid")
    count = await session.scalar(
        select(func.count(ChatConversation.id)).where(
            ChatConversation.user_id == user.id
        )
    )
    if int(count or 0) >= MAX_CONVERSATIONS_PER_USER:
        raise APIError(409, "conversation_limit_reached", "Conversation limit reached")
    conversation = ChatConversation(
        user_id=user.id,
        title=body.title.strip() if body.title and body.title.strip() else None,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user: CurrentUserDependency,
    session: session_dependency,
) -> ConversationListResponse:
    rows = (
        await session.scalars(
            select(ChatConversation)
            .where(ChatConversation.user_id == user.id)
            .order_by(ChatConversation.updated_at.desc())
            .limit(MAX_CONVERSATIONS_PER_USER)
        )
    ).all()
    return ConversationListResponse(
        conversations=[ConversationSummary.model_validate(row) for row in rows]
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    conversation_id: UUID,
    user: CurrentUserDependency,
    session: session_dependency,
) -> ConversationDetailResponse:
    conversation = await session.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
        )
    )
    if conversation is None:
        raise APIError(404, "conversation_not_found", "Conversation not found")
    rows = (
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
            .limit(MAX_MESSAGES_PER_CONVERSATION)
        )
    ).all()
    return ConversationDetailResponse(
        **ConversationSummary.model_validate(conversation).model_dump(),
        messages=[MessageResponse.model_validate(row) for row in rows],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user: CurrentUserDependency,
    session: session_dependency,
) -> Response:
    conversation = await session.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
        )
    )
    if conversation is None:
        raise APIError(404, "conversation_not_found", "Conversation not found")
    await session.delete(conversation)
    await session.commit()
    return Response(status_code=204)


@router.post(
    "/conversations/{conversation_id}/messages",
    responses={401: {}, 404: {}, 422: {}, 429: {}, 503: {}},
)
async def post_message(
    conversation_id: UUID,
    body: MessageCreate,
    user: CurrentUserDependency,
    session: session_dependency,
    provider: provider_dependency,
) -> StreamingResponse:
    try:
        validate_message_length(body.content)
    except MessageTooLongError:
        raise APIError(
            422, "message_too_long", "Message exceeds the allowed length"
        ) from None
    await _check_message_rate_limit(user.id)
    language = detect_language(body.content)
    refusal = classify_input(body.content) is not None
    conversation = await session.scalar(
        select(ChatConversation)
        .where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
        )
        .with_for_update()
    )
    if conversation is None:
        raise APIError(404, "conversation_not_found", "Conversation not found")
    if not refusal and provider is None:
        raise APIError(
            503,
            "llm_not_configured",
            "The language model provider is not configured",
        )
    if not refusal:
        await _check_daily_token_budget(session, user.id)
    message_count = await session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.conversation_id == conversation.id
        )
    )
    if int(message_count or 0) + MAX_TURN_MESSAGES > MAX_MESSAGES_PER_CONVERSATION:
        raise APIError(
            409, "message_limit_reached", "Conversation message limit reached"
        )
    previous_rows = (
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(MAX_HISTORY_MESSAGES)
        )
    ).all()
    history = [
        message
        for row in reversed(previous_rows)
        if (message := _history_message(row)) is not None
    ]
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    session.add(
        ChatMessage(
            id=user_message_id,
            conversation_id=conversation.id,
            role="user",
            content=body.content,
            refusal=False,
        )
    )
    if conversation.title is None:
        conversation.title = body.content[:80]
    conversation.updated_at = datetime.now(UTC)
    await session.commit()

    started_at = datetime.now(UTC)
    response_headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }

    async def stream_events() -> AsyncIterator[str]:
        yield _sse(
            "meta",
            {
                "user_message_id": str(user_message_id),
                "assistant_message_id": str(assistant_message_id),
                "language": language,
            },
        )
        try:
            result = await orchestrator.run(
                text=body.content,
                history=history,
                session=session,
                provider=provider,
            )
            for invocation in result.tool_invocations:
                yield _sse("tool_call", _tool_call_data(invocation))
                yield _sse("tool_result", _tool_result_data(invocation))
            await _persist_run(
                session=session,
                conversation=conversation,
                user=user,
                provider=provider,
                assistant_id=assistant_message_id,
                result=result,
            )
            for chunk in _text_chunks(result.text):
                yield _sse("token", {"text": chunk})
            yield _sse(
                "final",
                {
                    "grounding_status": result.grounding_status,
                    "refusal": result.refusal,
                    "tool_names": list(result.tool_names),
                },
            )
            logger.info(
                "agent message completed status=%s latency_ms=%d provider=%s",
                result.grounding_status,
                result.latency_ms,
                _provider_name(provider),
            )
            yield _sse("done", {})
        except AgentNotConfiguredError:
            await _persist_failed_usage(
                session=session,
                conversation=conversation,
                user=user,
                provider=provider,
                status="failed",
                started_at=started_at,
            )
            yield _sse("error", {"code": "llm_not_configured"})
            yield _sse("done", {})
        except ProviderError as exc:
            await _persist_failed_usage(
                session=session,
                conversation=conversation,
                user=user,
                provider=provider,
                status="failed",
                started_at=started_at,
            )
            logger.info(
                "agent message failed provider=%s error=%s",
                _provider_name(provider),
                exc.code,
            )
            yield _sse("error", {"code": exc.code})
            yield _sse("done", {})
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Agent persistence failed: %s", type(exc).__name__)
            yield _sse("error", {"code": "agent_storage_error"})
            yield _sse("done", {})
        except asyncio.CancelledError:
            await session.rollback()
            try:
                session.add(
                    LLMUsage(
                        user_id=user.id,
                        conversation_id=conversation.id,
                        provider=_provider_name(provider),
                        model=_provider_model(provider),
                        latency_ms=max(
                            0,
                            round(
                                (datetime.now(UTC) - started_at).total_seconds() * 1000
                            ),
                        ),
                        status="cancelled",
                    )
                )
                await asyncio.shield(session.commit())
            except SQLAlchemyError:
                await session.rollback()
            raise

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers=response_headers,
    )
