from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PlainSerializer, WithJsonSchema


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")


DecimalString = Annotated[
    Decimal,
    PlainSerializer(_decimal_string, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string"}),
]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AnalysisResponse(BaseModel):
    generated_at: datetime
    analysis_only: Literal[True] = True


class PriceResponse(BaseModel):
    close_usd: DecimalString | None
    as_of_date: date | None
    ret_30d: DecimalString | None


class ScoreSummary(BaseModel):
    value: DecimalString
    as_of_date: date
    coverage: DecimalString
    coverage_max: DecimalString
    is_partial: bool
    confidence_label: str
    version: str


class ScoreDetail(ScoreSummary):
    pillars: dict[str, Any]
    components: list[dict[str, Any]]


class RegimeSummary(BaseModel):
    label: str
    days_in_regime: int
    vol_state: str | None


class FlagSummary(BaseModel):
    flag: str
    severity: str


class FlagDetail(FlagSummary):
    value: DecimalString
    threshold: DecimalString


class FreshnessResponse(BaseModel):
    price_last_date: date | None
    lag_days: int | None
    stale: bool


class ChainSummary(BaseModel):
    slug: str
    name: str
    symbol: str
    price: PriceResponse
    score: ScoreSummary | None
    regime: RegimeSummary | None
    flags: list[FlagSummary]
    freshness: FreshnessResponse


class ChainsResponse(AnalysisResponse):
    chains: list[ChainSummary]


class LastFullCoverage(BaseModel):
    value: DecimalString
    as_of_date: date
    coverage: DecimalString
    confidence_label: str


class DataCoverageItem(BaseModel):
    metric: str
    source: str
    role: Literal["score", "context"]
    first_date: date | None
    last_date: date | None
    points: int
    missing: int
    status: str
    derived: bool
    note: str


class ChainDetailResponse(AnalysisResponse):
    slug: str
    name: str
    symbol: str
    price: PriceResponse
    score: ScoreDetail | None
    regime: RegimeSummary | None
    flags: list[FlagDetail]
    freshness: FreshnessResponse
    last_full_coverage: LastFullCoverage | None = None
    data_coverage: list[DataCoverageItem]
    methodology_version: str


class ScoreHistoryItem(BaseModel):
    as_of_date: date
    score: DecimalString
    coverage: DecimalString
    is_partial: bool
    confidence_label: str


class ScoreHistoryResponse(AnalysisResponse):
    chain: str
    items: list[ScoreHistoryItem]


class RegimeSegment(BaseModel):
    regime: str
    start_date: date
    end_date: date
    days: int


class RegimesResponse(AnalysisResponse):
    chain: str
    segments: list[RegimeSegment]
    latest_vol_state: str | None


class SeriesMeta(BaseModel):
    chain: str
    metric: str
    source: str
    role: Literal["score", "context"]
    derived: bool
    status: str
    first_date: date | None
    last_date: date | None
    points: int
    missing: int
    unit_note: str


class SeriesPoint(BaseModel):
    date: date
    value: DecimalString


class SeriesResponse(AnalysisResponse):
    meta: SeriesMeta
    points: list[SeriesPoint]


class ScenarioBasePrice(BaseModel):
    close_usd: DecimalString
    date: date


class ScenarioValue(BaseModel):
    name: Literal["pessimistic", "base", "optimistic"]
    quantile: Literal["p10", "p50", "p90"]
    return_value: DecimalString = Field(serialization_alias="return")
    illustrative_price_usd: DecimalString


class ScenarioHorizon(BaseModel):
    days: int
    available: bool
    reason: str | None
    low_sample: bool
    n_windows: int
    n_independent: int
    first_window_start: date | None
    last_window_end: date | None
    share_negative: DecimalString | None
    scenarios: list[ScenarioValue]


class ScenariosResponse(AnalysisResponse):
    chain: str
    version: str
    as_of_date: date
    base_price: ScenarioBasePrice
    horizons: list[ScenarioHorizon]
    not_a_forecast: Literal[True]
    method_note: str
    disclaimer: str


class PillarMethodology(BaseModel):
    name: str
    weight: int
    components: list[ComponentMethodology]


class ComponentMethodology(BaseModel):
    feature: str
    weight: int
    direction: str
    chains: list[str]
    derived_label: str | None


class RiskRuleMethodology(BaseModel):
    flag: str
    feature: str | None
    value_kind: str
    comparison: str
    threshold: DecimalString
    severity: str
    high_severity_threshold: DecimalString | None
    chains: list[str]


class RegimeRulesMethodology(BaseModel):
    stress_drawdown_lte: DecimalString
    uptrend: str
    downtrend: str
    otherwise: str
    priority: list[str]
    hysteresis_days: int


class VolatilityOverlayMethodology(BaseModel):
    feature: str
    low_lte: DecimalString
    high_gte: DecimalString
    low_state: str
    normal_state: str
    high_state: str


class SourceMethodology(BaseModel):
    name: str
    homepage_url: str
    used_for: list[str]
    terms_note: str


class ScenarioQuantileMethodology(BaseModel):
    name: Literal["pessimistic", "base", "optimistic"]
    quantile: Literal["p10", "p50", "p90"]
    probability: DecimalString


class ScenarioMethodology(BaseModel):
    version: str
    horizons_days: list[int]
    quantiles: list[ScenarioQuantileMethodology]
    minimum_independent_windows: int
    low_sample_below_independent_windows: int


class MethodologyResponse(AnalysisResponse):
    version: str
    percentile_window_days: int
    minimum_percentile_observations: int
    pillars: list[PillarMethodology]
    minimum_score_coverage: DecimalString
    confidence_thresholds: dict[str, DecimalString]
    coverage_max: dict[str, DecimalString]
    regime_rules: RegimeRulesMethodology
    volatility_overlay: VolatilityOverlayMethodology
    risk_flags: list[RiskRuleMethodology]
    sources: list[SourceMethodology]
    limitations: list[str]
    scenarios: ScenarioMethodology
