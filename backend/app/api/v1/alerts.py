import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.score_config import CHAINS
from app.api.v1.auth.dependencies import CurrentUserDependency
from app.core.errors import APIError
from app.db.models.alerts import AlertEvent, AlertRule, WatchlistItem
from app.db.models.auth import User
from app.db.models.ingestion import Chain
from app.db.session import get_session
from app.schemas.alerts import (
    AlertEventResponse,
    AlertEventsResponse,
    AlertMarkReadRequest,
    AlertMarkReadResponse,
    AlertRuleCreate,
    AlertRulePatch,
    AlertRuleResponse,
    AlertRulesResponse,
    AlertUnreadCountResponse,
    WatchlistItemResponse,
    WatchlistResponse,
    validated_rule_params,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(tags=["watchlist", "alerts"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
MAX_RULES_PER_USER = 20
WRITE_LIMIT = 60
WRITE_WINDOW = timedelta(minutes=1)


async def _write_limit(user: User) -> None:
    await check_rate_limit("alerts-write", str(user.id), WRITE_LIMIT, WRITE_WINDOW)


async def _get_chain(session: AsyncSession, slug: str) -> Chain:
    if slug not in CHAINS:
        raise APIError(404, "chain_not_found", "Chain was not found")
    chain = await session.get(Chain, slug)
    if chain is None or not chain.enabled:
        raise APIError(404, "chain_not_found", "Chain was not found")
    return chain


def _rule_response(rule: AlertRule) -> dict[str, object]:
    return {
        "id": rule.id,
        "chain": rule.chain_id,
        "type": rule.type,
        "params": rule.params,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _event_response(event: AlertEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "rule_id": event.rule_id,
        "chain": event.chain_id,
        "type": event.type,
        "payload": event.payload,
        "as_of_date": event.as_of_date,
        "created_at": event.created_at,
        "read_at": event.read_at,
    }


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(
    user: CurrentUserDependency, session: SessionDependency
) -> WatchlistResponse:
    rows = (
        await session.execute(
            select(WatchlistItem)
            .where(WatchlistItem.user_id == user.id)
            .order_by(WatchlistItem.created_at, WatchlistItem.chain_id)
        )
    ).scalars()
    return WatchlistResponse(
        items=[
            WatchlistItemResponse(slug=row.chain_id, added_at=row.created_at)
            for row in rows
        ]
    )


@router.put(
    "/watchlist/{slug}",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_200_OK,
)
async def add_watchlist_item(
    slug: str, user: CurrentUserDependency, session: SessionDependency
) -> WatchlistItemResponse:
    await _write_limit(user)
    await _get_chain(session, slug)
    statement = (
        insert(WatchlistItem)
        .values(user_id=user.id, chain_id=slug)
        .on_conflict_do_nothing(index_elements=["user_id", "chain_id"])
    )
    await session.execute(statement)
    await session.commit()
    row = await session.get(WatchlistItem, (user.id, slug))
    if row is None:
        raise RuntimeError("Watchlist item was not persisted")
    return WatchlistItemResponse(slug=slug, added_at=row.created_at)


@router.delete("/watchlist/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    slug: str, user: CurrentUserDependency, session: SessionDependency
) -> Response:
    await _write_limit(user)
    await _get_chain(session, slug)
    row = await session.get(WatchlistItem, (user.id, slug))
    if row is not None:
        await session.delete(row)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/alerts/rules", response_model=AlertRulesResponse)
async def get_alert_rules(
    user: CurrentUserDependency, session: SessionDependency
) -> AlertRulesResponse:
    rules = (
        await session.execute(
            select(AlertRule)
            .where(AlertRule.user_id == user.id)
            .order_by(AlertRule.created_at.desc(), AlertRule.id)
        )
    ).scalars()
    return AlertRulesResponse(
        rules=[AlertRuleResponse.model_validate(_rule_response(rule)) for rule in rules]
    )


@router.post(
    "/alerts/rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_rule(
    body: AlertRuleCreate,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> AlertRuleResponse:
    await _write_limit(user)
    await _get_chain(session, body.chain)
    try:
        params = validated_rule_params(body.type, body.params)
    except ValidationError:
        raise APIError(
            422, "alert_rule_params_invalid", "Alert rule parameters are invalid"
        ) from None
    params_key = json.dumps(params, sort_keys=True, separators=(",", ":"))

    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    rule_count = await session.scalar(
        select(func.count(AlertRule.id)).where(AlertRule.user_id == user.id)
    )
    if int(rule_count or 0) >= MAX_RULES_PER_USER:
        raise APIError(409, "alert_rule_limit_reached", "Alert rule limit reached")

    rule = AlertRule(
        user_id=user.id,
        chain_id=body.chain,
        type=body.type,
        params=params,
        params_key=params_key,
    )
    session.add(rule)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise APIError(
            409, "alert_rule_duplicate", "Alert rule already exists"
        ) from None
    await session.refresh(rule)
    return AlertRuleResponse.model_validate(_rule_response(rule))


@router.patch("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def patch_alert_rule(
    rule_id: UUID,
    body: AlertRulePatch,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> AlertRuleResponse:
    await _write_limit(user)
    rule = await session.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
    )
    if rule is None:
        raise APIError(404, "alert_rule_not_found", "Alert rule was not found")
    rule.is_active = body.is_active
    await session.commit()
    await session.refresh(rule)
    return AlertRuleResponse.model_validate(_rule_response(rule))


@router.delete("/alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> Response:
    await _write_limit(user)
    rule = await session.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
    )
    if rule is None:
        raise APIError(404, "alert_rule_not_found", "Alert rule was not found")
    await session.delete(rule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/alerts/events", response_model=AlertEventsResponse)
async def get_alert_events(
    user: CurrentUserDependency,
    session: SessionDependency,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> AlertEventsResponse:
    query = select(AlertEvent).where(AlertEvent.user_id == user.id)
    if unread_only:
        query = query.where(AlertEvent.read_at.is_(None))
    events = (
        await session.execute(
            query.order_by(
                AlertEvent.created_at.desc(),
                AlertEvent.as_of_date.desc(),
                AlertEvent.id.desc(),
            ).limit(limit)
        )
    ).scalars()
    return AlertEventsResponse(
        events=[
            AlertEventResponse.model_validate(_event_response(event))
            for event in events
        ]
    )


@router.get("/alerts/events/unread-count", response_model=AlertUnreadCountResponse)
async def get_unread_alert_count(
    user: CurrentUserDependency, session: SessionDependency
) -> AlertUnreadCountResponse:
    count = await session.scalar(
        select(func.count(AlertEvent.id)).where(
            AlertEvent.user_id == user.id, AlertEvent.read_at.is_(None)
        )
    )
    return AlertUnreadCountResponse(count=int(count or 0))


@router.post("/alerts/events/read", response_model=AlertMarkReadResponse)
async def mark_alert_events_read(
    body: AlertMarkReadRequest,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> AlertMarkReadResponse:
    await _write_limit(user)
    conditions = [AlertEvent.user_id == user.id, AlertEvent.read_at.is_(None)]
    if body.all:
        pass
    elif body.ids is not None:
        conditions.append(AlertEvent.id.in_(body.ids))
    else:
        raise APIError(
            422, "alert_event_selection_invalid", "Event selection is invalid"
        )
    result = await session.execute(
        update(AlertEvent)
        .where(*conditions)
        .values(read_at=datetime.now(UTC))
        .returning(AlertEvent.id)
    )
    updated = len(result.scalars().all())
    await session.commit()
    return AlertMarkReadResponse(updated=updated)
