import asyncio
import json
import re
from uuid import UUID

import pytest
from sqlalchemy import select

from app.agent import orchestrator as orchestrator_module
from app.agent.providers.base import ProviderError, ProviderResponse, ToolCall
from app.agent.providers.fake import FakeProvider
from app.api.v1 import agent as agent_api
from app.api.v1.agent import post_message
from app.core.logging import _safe_request_path
from app.db.models.agent import ChatConversation, ChatMessage, LLMUsage
from app.db.models.auth import User
from app.schemas.agent import MessageCreate
from app.services.rate_limit import reset_rate_limiter


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_conversation(context, token: str) -> UUID:
    response = await context.client.post(
        "/api/v1/agent/conversations",
        headers=_headers(token),
        json={},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_agent_requires_authentication_and_scopes_ownership(
    agent_context,
) -> None:
    unauthenticated = await agent_context.client.get("/api/v1/agent/conversations")
    assert unauthenticated.status_code == 401

    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    other_headers = _headers(agent_context.other_token)
    for response in (
        await agent_context.client.get(
            f"/api/v1/agent/conversations/{conversation_id}",
            headers=other_headers,
        ),
        await agent_context.client.delete(
            f"/api/v1/agent/conversations/{conversation_id}",
            headers=other_headers,
        ),
        await agent_context.client.post(
            f"/api/v1/agent/conversations/{conversation_id}/messages",
            headers=other_headers,
            json={"content": "Summarize network history."},
        ),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation_not_found"

    own_list = await agent_context.client.get(
        "/api/v1/agent/conversations",
        headers=_headers(agent_context.token),
    )
    other_list = await agent_context.client.get(
        "/api/v1/agent/conversations",
        headers=other_headers,
    )
    assert len(own_list.json()["conversations"]) == 1
    assert other_list.json()["conversations"] == []
    own_detail = await agent_context.client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=_headers(agent_context.token),
    )
    assert own_detail.status_code == 200
    deleted = await agent_context.client.delete(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=_headers(agent_context.token),
    )
    assert deleted.status_code == 204
    missing = await agent_context.client.get(
        f"/api/v1/agent/conversations/{conversation_id}",
        headers=_headers(agent_context.token),
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_conversation_and_message_limits_are_per_user(agent_context) -> None:
    async with agent_context.session_factory() as session:
        session.add_all(
            [
                ChatConversation(user_id=agent_context.user_id, title=str(index))
                for index in range(agent_api.MAX_CONVERSATIONS_PER_USER)
            ]
        )
        await session.commit()

    limited = await agent_context.client.post(
        "/api/v1/agent/conversations",
        headers=_headers(agent_context.token),
        json={},
    )
    assert limited.status_code == 409
    assert limited.json()["error"]["code"] == "conversation_limit_reached"

    other_conversation = await _create_conversation(
        agent_context,
        agent_context.other_token,
    )
    agent_context.app.state.agent_provider = FakeProvider(())
    async with agent_context.session_factory() as session:
        session.add_all(
            [
                ChatMessage(
                    conversation_id=other_conversation,
                    role="user",
                    content="stored",
                    refusal=False,
                )
                for _ in range(
                    agent_api.MAX_MESSAGES_PER_CONVERSATION
                    - agent_api.MAX_TURN_MESSAGES
                    + 1
                )
            ]
        )
        await session.commit()

    message_limited = await agent_context.client.post(
        f"/api/v1/agent/conversations/{other_conversation}/messages",
        headers=_headers(agent_context.other_token),
        json={"content": "Summarize network history."},
    )
    assert message_limited.status_code == 409
    assert message_limited.json()["error"]["code"] == "message_limit_reached"


@pytest.mark.asyncio
async def test_message_endpoint_returns_503_when_provider_is_unconfigured(
    agent_context,
) -> None:
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    response = await agent_context.client.post(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=_headers(agent_context.token),
        json={"content": "Summarize BTC score history."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "llm_not_configured",
            "message": "The language model provider is not configured",
        }
    }


@pytest.mark.asyncio
async def test_agent_rate_limit_returns_retry_after(agent_context, monkeypatch) -> None:
    reset_rate_limiter()
    monkeypatch.setattr(agent_api, "MAX_MESSAGES_PER_HOUR", 1)
    monkeypatch.setattr(agent_api, "MAX_MESSAGES_PER_DAY", 10)
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    for _ in range(2):
        response = await agent_context.client.post(
            f"/api/v1/agent/conversations/{conversation_id}/messages",
            headers=_headers(agent_context.token),
            json={"content": "Should I buy this asset?"},
        )
        if response.status_code == 429:
            break
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    assert response.json()["error"]["code"] == "rate_limited"
    other_conversation = await _create_conversation(
        agent_context,
        agent_context.other_token,
    )
    other_response = await agent_context.client.post(
        f"/api/v1/agent/conversations/{other_conversation}/messages",
        headers=_headers(agent_context.other_token),
        json={"content": "Should I buy this asset?"},
    )
    assert other_response.status_code == 200


@pytest.mark.asyncio
async def test_daily_message_rate_limit_is_enforced(agent_context, monkeypatch) -> None:
    reset_rate_limiter()
    monkeypatch.setattr(agent_api, "MAX_MESSAGES_PER_HOUR", 10)
    monkeypatch.setattr(agent_api, "MAX_MESSAGES_PER_DAY", 1)
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    for _ in range(2):
        response = await agent_context.client.post(
            f"/api/v1/agent/conversations/{conversation_id}/messages",
            headers=_headers(agent_context.token),
            json={"content": "Should I buy this asset?"},
        )
        if response.status_code == 429:
            break
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    assert response.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_message_length_limit_is_enforced(agent_context) -> None:
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    response = await agent_context.client.post(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=_headers(agent_context.token),
        json={"content": "x" * 2001},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "message_too_long"


@pytest.mark.asyncio
async def test_daily_token_budget_returns_retry_after(
    agent_context, monkeypatch
) -> None:
    monkeypatch.setattr(agent_api.settings, "llm_daily_token_budget", 1)
    agent_context.app.state.agent_provider = FakeProvider(())
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    async with agent_context.session_factory() as session:
        session.add(
            LLMUsage(
                user_id=agent_context.user_id,
                conversation_id=None,
                provider="fake",
                model="fake",
                prompt_tokens=1,
                completion_tokens=None,
                latency_ms=0,
                status="ok",
            )
        )
        await session.commit()

    response = await agent_context.client.post(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=_headers(agent_context.token),
        json={"content": "Summarize the stored history."},
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    assert response.json()["error"]["code"] == "token_budget_exceeded"


@pytest.mark.asyncio
async def test_agent_sse_order_persists_messages_and_usage_without_body_in_logs(
    agent_context,
    caplog,
) -> None:
    body = "Confidential agent test body 74291."
    provider = FakeProvider(
        [
            ProviderResponse(
                content=None,
                tool_calls=(ToolCall("call-1", "list_chains", {}),),
            ),
            ProviderResponse(content="The available history is recorded."),
        ]
    )
    agent_context.app.state.agent_provider = provider
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    response = await agent_context.client.post(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=_headers(agent_context.token),
        json={"content": body},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    events = re.findall(r"^event: ([a-z_]+)$", response.text, flags=re.MULTILINE)
    assert events[:3] == ["meta", "tool_call", "tool_result"]
    assert events[-2:] == ["final", "done"]
    assert all(event == "token" for event in events[3:-2])
    assert events[3:-2]
    assert '"summary":"data_returned"' in response.text
    meta = re.search(
        r"event: meta\ndata: (.+)",
        response.text,
    )
    assert meta is not None
    meta_data = json.loads(meta.group(1))
    assert meta_data["language"] == "en"
    assert UUID(meta_data["user_message_id"])
    assert UUID(meta_data["assistant_message_id"])
    assert body not in caplog.text
    assert agent_context.user_email not in caplog.text
    assert (
        _safe_request_path(f"/api/v1/agent/conversations/{conversation_id}/messages")
        == "/api/v1/agent/conversations/{conversation_id}/messages"
    )
    request_text = json.dumps(provider.requests, ensure_ascii=False)
    assert agent_context.user_email not in request_text
    assert str(agent_context.user_id) not in request_text
    assert body in request_text
    assert "admin" not in request_text.lower()
    assert all(
        message.get("role") in {"system", "user", "assistant", "tool"}
        and "account_role" not in message
        and "user_id" not in message
        and "email" not in message
        for messages, _ in provider.requests
        for message in messages
    )

    async with agent_context.session_factory() as session:
        messages = (
            await session.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            )
        ).all()
        usage = await session.scalar(
            select(LLMUsage).where(LLMUsage.conversation_id == conversation_id)
        )
    assert [message.role for message in messages] == ["user", "tool", "assistant"]
    assert messages[0].content == body
    assert messages[-1].grounding_status == "ok"
    assert usage is not None
    assert usage.status == "ok"
    assert not hasattr(LLMUsage, "content")


@pytest.mark.asyncio
async def test_agent_streams_tool_events_before_provider_retry_and_verified_tokens(
    agent_context,
    monkeypatch,
) -> None:
    second_call_started = asyncio.Event()
    release_second_call = asyncio.Event()

    class GatedFakeProvider(FakeProvider):
        async def chat(self, messages, tools, *, timeout):
            if len(self.requests) == 1:
                second_call_started.set()
                await release_second_call.wait()
            return await super().chat(messages, tools, timeout=timeout)

    async def execute_tool(name: str, arguments: object, session: object):
        assert name == "get_chain_snapshot"
        assert arguments == '{"slug":"btc"}'
        return {"ok": True, "data": {"score": "42"}}

    monkeypatch.setattr(orchestrator_module, "execute_tool", execute_tool)
    provider = GatedFakeProvider(
        [
            ProviderResponse(
                content=None,
                tool_calls=(
                    ToolCall("call-1", "get_chain_snapshot", '{"slug":"btc"}'),
                ),
            ),
            ProviderResponse(content="The score is 99."),
            ProviderResponse(content="The score is 42."),
        ]
    )
    async with agent_context.session_factory() as session:
        conversation = ChatConversation(user_id=agent_context.user_id)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        user = await session.get(User, agent_context.user_id)
        assert user is not None
        response = await post_message(
            conversation.id,
            MessageCreate(content="Summarize BTC score."),
            user,
            session,
            provider,
        )
        iterator = response.body_iterator

        def event_name(chunk: object) -> str:
            value = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
            return value.splitlines()[0].removeprefix("event: ")

        assert event_name(await iterator.__anext__()) == "meta"  # type: ignore[attr-defined]
        seen_events = ["meta"]
        tool_call = await asyncio.wait_for(
            iterator.__anext__(),  # type: ignore[attr-defined]
            timeout=1,
        )
        assert event_name(tool_call) == "tool_call"
        seen_events.append("tool_call")
        assert '"name":"get_chain_snapshot"' in str(tool_call)

        tool_result = await asyncio.wait_for(
            iterator.__anext__(),  # type: ignore[attr-defined]
            timeout=1,
        )
        assert event_name(tool_result) == "tool_result"
        seen_events.append("tool_result")

        next_event = asyncio.create_task(iterator.__anext__())  # type: ignore[attr-defined]
        await asyncio.wait_for(second_call_started.wait(), timeout=1)
        assert not next_event.done()
        release_second_call.set()

        event_names: list[str] = []
        while True:
            chunk = await asyncio.wait_for(next_event, timeout=1)
            event_names.append(event_name(chunk))
            seen_events.append(event_names[-1])
            if event_names[-1] == "done":
                break
            next_event = asyncio.create_task(
                iterator.__anext__()  # type: ignore[attr-defined]
            )

    assert event_names[0] == "token"
    assert event_names[-2:] == ["final", "done"]
    assert len(provider.requests) == 3
    assert seen_events.count("tool_call") == 1
    assert seen_events.count("tool_result") == 1


@pytest.mark.asyncio
async def test_provider_timeout_is_an_error_sse_event(agent_context) -> None:
    class TimeoutProvider:
        async def chat(self, messages, tools, *, timeout):
            del messages, tools, timeout
            raise ProviderError("provider_timeout")

    agent_context.app.state.agent_provider = TimeoutProvider()
    conversation_id = await _create_conversation(
        agent_context,
        agent_context.token,
    )
    response = await agent_context.client.post(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=_headers(agent_context.token),
        json={"content": "Summarize BTC score history."},
    )

    events = re.findall(r"^event: ([a-z_]+)$", response.text, flags=re.MULTILINE)
    assert events == ["meta", "error", "done"]
    assert '"code":"provider_timeout"' in response.text


@pytest.mark.asyncio
async def test_disconnect_cancels_provider_and_records_no_message_body(
    agent_context,
    monkeypatch,
) -> None:
    started = asyncio.Event()
    calls = 0

    class BlockingProvider:
        async def chat(self, messages, tools, *, timeout):
            del messages, tools, timeout
            nonlocal calls
            calls += 1
            if calls == 1:
                return ProviderResponse(
                    content=None,
                    tool_calls=(ToolCall("call-1", "list_chains", {}),),
                )
            started.set()
            await asyncio.Event().wait()
            return ProviderResponse(content="not reached")

    async def execute_tool(name: str, arguments: object, session: object):
        del name, arguments, session
        return {"ok": True, "data": {"chains": []}}

    monkeypatch.setattr(orchestrator_module, "execute_tool", execute_tool)
    agent_context.app.state.agent_provider = BlockingProvider()
    async with agent_context.session_factory() as session:
        conversation = ChatConversation(user_id=agent_context.user_id)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        user = await session.get(User, agent_context.user_id)
        assert user is not None
        response = await post_message(
            conversation.id,
            MessageCreate(content="Summarize network health data."),
            user,
            session,
            agent_context.app.state.agent_provider,
        )
        iterator = response.body_iterator
        await iterator.__anext__()  # type: ignore[attr-defined]
        assert "tool_call" in await iterator.__anext__()  # type: ignore[attr-defined]
        assert "tool_result" in await iterator.__anext__()  # type: ignore[attr-defined]
        pending = asyncio.create_task(iterator.__anext__())  # type: ignore[attr-defined]
        await asyncio.wait_for(started.wait(), timeout=1)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert pending.cancelled()

        usage = await session.scalar(
            select(LLMUsage).where(LLMUsage.conversation_id == conversation.id)
        )
        messages = (
            await session.scalars(
                select(ChatMessage).where(
                    ChatMessage.conversation_id == conversation.id
                )
            )
        ).all()
    assert usage is not None
    assert usage.status == "cancelled"
    assert [(message.role, message.content) for message in messages] == [
        ("user", "Summarize network health data.")
    ]
