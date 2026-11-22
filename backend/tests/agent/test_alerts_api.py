from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.alerts import AlertEvent, AlertRule
from app.db.models.ingestion import Chain
from tests.agent.conftest import AgentTestContext


@pytest_asyncio.fixture
async def alerts_context(
    agent_context: AgentTestContext,
) -> AsyncIterator[AgentTestContext]:
    async with agent_context.session_factory() as session:
        if await session.get(Chain, "btc") is None:
            session.add(
                Chain(
                    code="btc",
                    name="Bitcoin",
                    native_symbol="BTC",
                    consensus="pow",
                    enabled=True,
                )
            )
            await session.commit()
    yield agent_context


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_watchlist_auth_idempotency_unknown_slug_and_user_scope(
    alerts_context: AgentTestContext,
) -> None:
    client = alerts_context.client
    assert (await client.get("/api/v1/watchlist")).status_code == 401
    response = await client.put(
        "/api/v1/watchlist/btc", headers=headers(alerts_context.token)
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "btc"
    first_added_at = response.json()["added_at"]
    response = await client.put(
        "/api/v1/watchlist/btc", headers=headers(alerts_context.token)
    )
    assert response.status_code == 200
    assert response.json()["added_at"] == first_added_at
    other = await client.get(
        "/api/v1/watchlist", headers=headers(alerts_context.other_token)
    )
    assert other.json() == {"items": []}
    unknown = await client.put(
        "/api/v1/watchlist/unknown", headers=headers(alerts_context.token)
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "chain_not_found"
    deleted = await client.delete(
        "/api/v1/watchlist/btc", headers=headers(alerts_context.token)
    )
    assert deleted.status_code == 204
    assert (
        await client.delete(
            "/api/v1/watchlist/btc", headers=headers(alerts_context.token)
        )
    ).status_code == 204


@pytest.mark.asyncio
async def test_alert_rule_validation_duplicate_patch_and_cross_user_404(
    alerts_context: AgentTestContext,
) -> None:
    client = alerts_context.client
    token = headers(alerts_context.token)
    other_token = headers(alerts_context.other_token)
    body = {"chain": "btc", "type": "regime_change", "params": {}}
    created = await client.post("/api/v1/alerts/rules", json=body, headers=token)
    assert created.status_code == 201
    rule_id = created.json()["id"]
    duplicate = await client.post("/api/v1/alerts/rules", json=body, headers=token)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "alert_rule_duplicate"
    invalid_flag = await client.post(
        "/api/v1/alerts/rules",
        json={
            "chain": "btc",
            "type": "risk_flag",
            "params": {"flag": "not_a_flag"},
        },
        headers=token,
    )
    assert invalid_flag.status_code == 422
    assert invalid_flag.json()["error"]["code"] == "alert_rule_params_invalid"
    strict_threshold = await client.post(
        "/api/v1/alerts/rules",
        json={
            "chain": "btc",
            "type": "score_cross",
            "params": {"direction": "below", "threshold": "50"},
        },
        headers=token,
    )
    assert strict_threshold.status_code == 422
    foreign_patch = await client.patch(
        f"/api/v1/alerts/rules/{rule_id}",
        json={"is_active": False},
        headers=other_token,
    )
    assert foreign_patch.status_code == 404
    patched = await client.patch(
        f"/api/v1/alerts/rules/{rule_id}",
        json={"is_active": False},
        headers=token,
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    assert (
        await client.delete(f"/api/v1/alerts/rules/{rule_id}", headers=other_token)
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/alerts/rules/{rule_id}", headers=token)
    ).status_code == 204


@pytest.mark.asyncio
async def test_alert_rule_limit_and_event_read_scope(
    alerts_context: AgentTestContext,
) -> None:
    client = alerts_context.client
    token = headers(alerts_context.token)
    other_token = headers(alerts_context.other_token)
    rules: list[AlertRule] = []
    other_rules: list[AlertRule] = []
    for index in range(20):
        response = await client.post(
            "/api/v1/alerts/rules",
            json={
                "chain": "btc",
                "type": "score_cross",
                "params": {
                    "direction": "below",
                    "threshold": index + 1,
                },
            },
            headers=token,
        )
        assert response.status_code == 201
        async with alerts_context.session_factory() as session:
            own_rule = await session.get(AlertRule, response.json()["id"])
            assert own_rule is not None
            rules.append(own_rule)

    limited = await client.post(
        "/api/v1/alerts/rules",
        json={"chain": "btc", "type": "regime_change", "params": {}},
        headers=token,
    )
    assert limited.status_code == 409
    assert limited.json()["error"]["code"] == "alert_rule_limit_reached"

    async with alerts_context.session_factory() as session:
        for index in range(2):
            other_rule = AlertRule(
                user_id=alerts_context.other_user_id,
                chain_id="btc",
                type="regime_change",
                params={},
                params_key=f"other-{index}",
            )
            session.add(other_rule)
            other_rules.append(other_rule)
        await session.flush()
        own_events = [
            AlertEvent(
                rule_id=rules[index].id,
                user_id=alerts_context.user_id,
                chain_id="btc",
                as_of_date=date(2026, 11, 20 + index),
                type="score_cross",
                payload={"score": "42"},
            )
            for index in range(2)
        ]
        foreign_event = AlertEvent(
            rule_id=other_rules[0].id,
            user_id=alerts_context.other_user_id,
            chain_id="btc",
            as_of_date=date(2026, 11, 22),
            type="regime_change",
            payload={"from": "range", "to": "stress"},
        )
        session.add_all([*own_events, foreign_event])
        await session.commit()
        own_ids = [str(event.id) for event in own_events]
        foreign_id = str(foreign_event.id)

    count = await client.get("/api/v1/alerts/events/unread-count", headers=token)
    assert count.json() == {"count": 2}
    too_many = await client.get("/api/v1/alerts/events?limit=51", headers=token)
    assert too_many.status_code == 422
    mark_response = await client.post(
        "/api/v1/alerts/events/read",
        json={"ids": [own_ids[0], foreign_id]},
        headers=token,
    )
    assert mark_response.json() == {"updated": 1}
    count = await client.get("/api/v1/alerts/events/unread-count", headers=token)
    assert count.json() == {"count": 1}
    events = await client.get(
        "/api/v1/alerts/events?unread_only=true",
        headers=other_token,
    )
    assert len(events.json()["events"]) == 1
    mark_all = await client.post(
        "/api/v1/alerts/events/read", json={"all": True}, headers=token
    )
    assert mark_all.json() == {"updated": 1}
    assert (
        await client.get("/api/v1/alerts/events/unread-count", headers=token)
    ).json() == {"count": 0}
    async with alerts_context.session_factory() as session:
        foreign = await session.scalar(
            select(AlertEvent).where(AlertEvent.id == foreign_event.id)
        )
        assert foreign is not None
        assert foreign.read_at is None
