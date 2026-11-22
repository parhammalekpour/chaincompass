from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.analytics.score_config import RISK_FLAGS

RISK_FLAG_CODES = frozenset(spec.flag for spec in RISK_FLAGS)


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RegimeChangeParams(StrictSchema):
    pass


class RiskFlagParams(StrictSchema):
    flag: str | None

    @field_validator("flag")
    @classmethod
    def validate_flag(cls, value: str | None) -> str | None:
        if value is not None and value not in RISK_FLAG_CODES:
            raise ValueError("Unsupported risk flag code")
        return value


class ScoreCrossParams(StrictSchema):
    direction: Literal["below", "above"]
    threshold: int = Field(ge=1, le=99)


class AlertRuleCreate(StrictSchema):
    chain: Literal["btc", "eth", "sol", "bnb"]
    type: Literal["regime_change", "risk_flag", "score_cross"]
    params: dict[str, object]


class AlertRulePatch(StrictSchema):
    is_active: bool


class AlertRuleResponse(BaseModel):
    id: UUID
    chain: str
    type: str
    params: dict[str, object]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WatchlistItemResponse(BaseModel):
    slug: str
    added_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItemResponse]


class AlertRulesResponse(BaseModel):
    rules: list[AlertRuleResponse]


class AlertEventResponse(BaseModel):
    id: UUID
    rule_id: UUID
    chain: str
    type: str
    payload: dict[str, object]
    as_of_date: date
    created_at: datetime
    read_at: datetime | None


class AlertEventsResponse(BaseModel):
    events: list[AlertEventResponse]


class AlertUnreadCountResponse(BaseModel):
    count: int


class AlertMarkReadRequest(StrictSchema):
    ids: list[Annotated[UUID, Field(strict=False)]] | None = Field(
        default=None, min_length=1
    )
    all: bool = False

    @model_validator(mode="after")
    def validate_selection(self) -> "AlertMarkReadRequest":
        if self.all == (self.ids is not None):
            raise ValueError("Provide either ids or all")
        return self


class AlertMarkReadResponse(BaseModel):
    updated: int


def validated_rule_params(
    rule_type: str, params: dict[str, object]
) -> dict[str, object]:
    schema: type[BaseModel]
    if rule_type == "regime_change":
        schema = RegimeChangeParams
    elif rule_type == "risk_flag":
        schema = RiskFlagParams
    elif rule_type == "score_cross":
        schema = ScoreCrossParams
    else:
        raise ValueError("Unsupported alert rule type")
    return schema.model_validate(params).model_dump(mode="json")
