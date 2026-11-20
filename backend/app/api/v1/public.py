from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.registry import (
    FeatureInput,
    get_public_series_inputs,
    public_series_inputs,
)
from app.analytics.score_config import (
    CHAINS,
    COMPONENTS,
    HIGH_CONFIDENCE_COVERAGE,
    HIGH_VOLATILITY_STATE_THRESHOLD,
    HYSTERESIS_DAYS,
    LOW_VOLATILITY_STATE_THRESHOLD,
    MEDIUM_CONFIDENCE_COVERAGE,
    MIN_PERCENTILE_OBSERVATIONS,
    NO_SCORE_COVERAGE,
    PERCENTILE_WINDOW_DAYS,
    PILLARS,
    REGIME_DOWNTREND,
    REGIME_RANGE,
    REGIME_STRESS,
    REGIME_UPTREND,
    RISK_FLAGS,
    STRESS_DRAWDOWN_THRESHOLD,
    VERSION,
    VOL_STATE_HIGH,
    VOL_STATE_LOW,
    VOL_STATE_NORMAL,
    maximum_coverage_by_chain,
)
from app.core.errors import APIError
from app.db.models.health import HealthScore, MarketRegime, RiskFlag
from app.db.models.ingestion import ComputedFeature, Observation, SeriesCoverage
from app.db.session import get_session
from app.ingestion.seed import CHAINS as SEEDED_CHAINS
from app.ingestion.service import IngestionService
from app.schemas.public_api import (
    ChainDetailResponse,
    ChainsResponse,
    ChainSummary,
    ComponentMethodology,
    DataCoverageItem,
    ErrorResponse,
    FlagDetail,
    FlagSummary,
    FreshnessResponse,
    LastFullCoverage,
    MethodologyResponse,
    PillarMethodology,
    PriceResponse,
    RegimeRulesMethodology,
    RegimeSegment,
    RegimesResponse,
    RegimeSummary,
    RiskRuleMethodology,
    ScoreDetail,
    ScoreHistoryItem,
    ScoreHistoryResponse,
    ScoreSummary,
    SeriesMeta,
    SeriesPoint,
    SeriesResponse,
    SourceMethodology,
    VolatilityOverlayMethodology,
)
from app.services.rate_limit import check_rate_limit, client_ip

DEFAULT_RANGE_DAYS = 365
MAX_HISTORY_SPAN_DAYS = 3650
MAX_SERIES_POINTS = 5000
PUBLIC_RATE_LIMIT = 120
PUBLIC_RATE_WINDOW = timedelta(minutes=1)
PUBLIC_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=600"
MAX_COVERAGE = maximum_coverage_by_chain()
CHAIN_INFO = {code: (name, symbol) for code, name, symbol, _, _ in SEEDED_CHAINS}
PUBLIC_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


async def public_request_policy(request: Request, response: Response) -> None:
    await check_rate_limit(
        "public-data",
        client_ip(request),
        PUBLIC_RATE_LIMIT,
        PUBLIC_RATE_WINDOW,
    )
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL


router = APIRouter(
    tags=["public-data"],
    dependencies=[Depends(public_request_policy)],
)


def _generated_at() -> datetime:
    return datetime.now(UTC)


def _require_chain(slug: str) -> tuple[str, str, str]:
    if slug not in CHAIN_INFO:
        raise APIError(404, "chain_not_found", f"Unknown chain: {slug}")
    name, symbol = CHAIN_INFO[slug]
    return slug, name, symbol


def _coverage_max(chain: str) -> Decimal:
    return MAX_COVERAGE[chain]


def _score_summary(row: HealthScore, chain: str) -> ScoreSummary:
    maximum = _coverage_max(chain)
    return ScoreSummary(
        value=row.score,
        as_of_date=row.as_of_date,
        coverage=row.coverage,
        coverage_max=maximum,
        is_partial=row.coverage < maximum,
        confidence_label=row.confidence_label,
        version=row.version,
    )


def _score_detail(row: HealthScore, chain: str) -> ScoreDetail:
    summary = _score_summary(row, chain)
    return ScoreDetail(
        **summary.model_dump(),
        pillars=row.pillars,
        components=row.components,
    )


def _regime_summary(row: MarketRegime | None) -> RegimeSummary | None:
    if row is None:
        return None
    return RegimeSummary(
        label=row.regime,
        days_in_regime=row.days_in_regime,
        vol_state=row.vol_state,
    )


def _freshness(price_date: date | None, reference_date: date) -> FreshnessResponse:
    lag_days = (reference_date - price_date).days if price_date is not None else None
    return FreshnessResponse(
        price_last_date=price_date,
        lag_days=lag_days,
        stale=(
            lag_days > IngestionService.staleness_days["price_close_usd"]
            if lag_days is not None
            else False
        ),
    )


def _summary_flags(rows: Sequence[RiskFlag]) -> list[FlagSummary]:
    return [FlagSummary(flag=row.flag, severity=row.severity) for row in rows]


def _detail_flags(rows: Sequence[RiskFlag]) -> list[FlagDetail]:
    return [
        FlagDetail(
            flag=row.flag,
            severity=row.severity,
            value=row.value,
            threshold=row.threshold,
        )
        for row in rows
    ]


async def _latest_score(session: AsyncSession, chain: str) -> HealthScore | None:
    rows = await session.scalars(
        select(HealthScore)
        .where(HealthScore.chain_id == chain, HealthScore.version == VERSION)
        .order_by(HealthScore.as_of_date.desc())
        .limit(1)
    )
    return rows.first()


async def _price_at(
    session: AsyncSession,
    chain: str,
    reference_date: date,
) -> tuple[PriceResponse, FreshnessResponse]:
    observation = await session.scalar(
        select(Observation)
        .where(
            Observation.chain_code == chain,
            Observation.metric_code == "price_close_usd",
            Observation.source_code == "binance",
            Observation.obs_date <= reference_date,
        )
        .order_by(Observation.obs_date.desc())
        .limit(1)
    )
    if observation is None:
        return (
            PriceResponse(close_usd=None, as_of_date=None, ret_30d=None),
            _freshness(None, reference_date),
        )

    ret_30d = await session.scalar(
        select(ComputedFeature.value).where(
            ComputedFeature.chain_id == chain,
            ComputedFeature.feature == "ret_30d",
            ComputedFeature.as_of_date == observation.obs_date,
            ComputedFeature.source_metric == "price_close_usd",
            ComputedFeature.source == "binance",
        )
    )
    return (
        PriceResponse(
            close_usd=observation.value,
            as_of_date=observation.obs_date,
            ret_30d=ret_30d,
        ),
        _freshness(observation.obs_date, reference_date),
    )


async def _data_coverage(
    session: AsyncSession,
    chain: str,
    as_of_date: date | None = None,
) -> list[DataCoverageItem]:
    inputs = public_series_inputs(chain)
    if as_of_date is None:
        rows = (
            await session.scalars(
                select(SeriesCoverage).where(SeriesCoverage.chain_code == chain)
            )
        ).all()
        coverage_by_key = {
            (row.metric_code, row.source_code): (
                row.first_date,
                row.last_date,
                row.points,
                row.missing_days,
                row.status,
            )
            for row in rows
        }
    else:
        observed_rows = (
            await session.execute(
                select(
                    Observation.metric_code,
                    Observation.source_code,
                    func.min(Observation.obs_date),
                    func.max(Observation.obs_date),
                    func.count(Observation.obs_date),
                )
                .where(
                    Observation.chain_code == chain,
                    Observation.obs_date <= as_of_date,
                )
                .group_by(Observation.metric_code, Observation.source_code)
            )
        ).all()
        coverage_by_key = {}
        for metric, source, first, last, count in observed_rows:
            missing = (
                max(0, (last - first).days + 1 - int(count))
                if first is not None and last is not None
                else 0
            )
            coverage_by_key[(metric, source)] = (
                first,
                last,
                int(count),
                missing,
                "ok",
            )
    output: list[DataCoverageItem] = []
    for item in inputs:
        coverage = coverage_by_key.get((item.metric, item.source))
        if coverage is None:
            first = last = None
            points = missing = 0
            status = (
                "discontinued"
                if item.chain == "bnb" and item.source == "coin_metrics"
                else "unavailable"
                if item.availability_note
                else "never_run"
            )
        else:
            first, last, points, missing, status = coverage
            if as_of_date is not None and last is not None:
                stale_days = IngestionService.staleness_days.get(item.metric, 3)
                status = "stale" if (as_of_date - last).days > stale_days else "ok"
        note = " ".join(
            part
            for part in (item.availability_note, item.unit_note)
            if part is not None
        )
        output.append(
            DataCoverageItem(
                metric=item.metric,
                source=item.source,
                role=item.role,
                first_date=first,
                last_date=last,
                points=points,
                missing=missing,
                status=status,
                derived=item.derived,
                note=note,
            )
        )
    return output


async def _last_full_coverage(
    session: AsyncSession,
    chain: str,
    as_of_date: date,
) -> LastFullCoverage | None:
    row = await session.scalar(
        select(HealthScore)
        .where(
            HealthScore.chain_id == chain,
            HealthScore.version == VERSION,
            HealthScore.coverage == _coverage_max(chain),
            HealthScore.as_of_date <= as_of_date,
        )
        .order_by(HealthScore.as_of_date.desc())
        .limit(1)
    )
    if row is None:
        return None
    return LastFullCoverage(
        value=row.score,
        as_of_date=row.as_of_date,
        coverage=row.coverage,
        confidence_label=row.confidence_label,
    )


@router.get(
    "/chains",
    response_model=ChainsResponse,
    summary="List supported chains and latest public analytics",
    responses=PUBLIC_ERRORS,
)
async def list_chains(
    session: AsyncSession = Depends(get_session),
) -> ChainsResponse:
    score_dates = (
        select(
            HealthScore.chain_id.label("chain_id"),
            func.max(HealthScore.as_of_date).label("as_of_date"),
        )
        .where(HealthScore.version == VERSION)
        .group_by(HealthScore.chain_id)
        .subquery()
    )
    score_rows = (
        await session.scalars(
            select(HealthScore).join(
                score_dates,
                and_(
                    HealthScore.chain_id == score_dates.c.chain_id,
                    HealthScore.as_of_date == score_dates.c.as_of_date,
                    HealthScore.version == VERSION,
                ),
            )
        )
    ).all()
    score_by_chain = {row.chain_id: row for row in score_rows}

    regimes_by_chain: dict[str, MarketRegime] = {}
    flags_by_chain: dict[str, list[RiskFlag]] = defaultdict(list)
    if score_by_chain:
        same_date = [
            and_(
                MarketRegime.chain_id == chain,
                MarketRegime.as_of_date == score.as_of_date,
            )
            for chain, score in score_by_chain.items()
        ]
        regime_rows = (
            await session.scalars(
                select(MarketRegime).where(
                    MarketRegime.version == VERSION,
                    or_(*same_date),
                )
            )
        ).all()
        regimes_by_chain = {row.chain_id: row for row in regime_rows}
        flag_dates = [
            and_(
                RiskFlag.chain_id == chain,
                RiskFlag.as_of_date == score.as_of_date,
            )
            for chain, score in score_by_chain.items()
        ]
        flag_rows = (
            await session.scalars(
                select(RiskFlag)
                .where(RiskFlag.version == VERSION, or_(*flag_dates))
                .order_by(RiskFlag.flag)
            )
        ).all()
        for row in flag_rows:
            flags_by_chain[row.chain_id].append(row)

    price_dates = (
        select(
            Observation.chain_code.label("chain_code"),
            func.max(Observation.obs_date).label("obs_date"),
        )
        .where(
            Observation.metric_code == "price_close_usd",
            Observation.source_code == "binance",
            Observation.chain_code.in_(CHAINS),
        )
        .group_by(Observation.chain_code)
        .subquery()
    )
    price_rows = (
        await session.scalars(
            select(Observation).join(
                price_dates,
                and_(
                    Observation.chain_code == price_dates.c.chain_code,
                    Observation.obs_date == price_dates.c.obs_date,
                    Observation.metric_code == "price_close_usd",
                    Observation.source_code == "binance",
                ),
            )
        )
    ).all()
    price_by_chain = {row.chain_code: row for row in price_rows}
    price_feature_rows: Sequence[ComputedFeature] = []
    if price_rows:
        price_feature_rows = (
            await session.scalars(
                select(ComputedFeature).where(
                    ComputedFeature.chain_id.in_(
                        [row.chain_code for row in price_rows]
                    ),
                    ComputedFeature.feature == "ret_30d",
                    ComputedFeature.source_metric == "price_close_usd",
                    ComputedFeature.source == "binance",
                    ComputedFeature.as_of_date.in_(
                        [row.obs_date for row in price_rows]
                    ),
                )
            )
        ).all()
    ret_by_date = {
        (row.chain_id, row.as_of_date): row.value for row in price_feature_rows
    }

    today = datetime.now(UTC).date()
    chains: list[ChainSummary] = []
    for chain in CHAINS:
        name, symbol = CHAIN_INFO[chain]
        price_row = price_by_chain.get(chain)
        price_date = price_row.obs_date if price_row is not None else None
        score_row = score_by_chain.get(chain)
        chains.append(
            ChainSummary(
                slug=chain,
                name=name,
                symbol=symbol,
                price=PriceResponse(
                    close_usd=price_row.value if price_row is not None else None,
                    as_of_date=price_date,
                    ret_30d=(
                        ret_by_date.get((chain, price_date))
                        if price_date is not None
                        else None
                    ),
                ),
                score=(
                    _score_summary(score_row, chain) if score_row is not None else None
                ),
                regime=_regime_summary(regimes_by_chain.get(chain)),
                flags=_summary_flags(flags_by_chain.get(chain, [])),
                freshness=_freshness(price_date, today),
            )
        )
    return ChainsResponse(generated_at=_generated_at(), chains=chains)


@router.get(
    "/chains/{slug}",
    response_model=ChainDetailResponse,
    response_model_exclude_unset=True,
    summary="Get a chain snapshot and public data coverage",
    responses=PUBLIC_ERRORS,
)
async def get_chain(
    slug: str,
    as_of: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ChainDetailResponse:
    chain, name, symbol = _require_chain(slug)
    today = datetime.now(UTC).date()
    if as_of is not None and as_of > today:
        raise APIError(422, "future_as_of_date", "as_of cannot be in the future")

    score = (
        await session.scalar(
            select(HealthScore).where(
                HealthScore.chain_id == chain,
                HealthScore.as_of_date == as_of,
                HealthScore.version == VERSION,
            )
        )
        if as_of is not None
        else await _latest_score(session, chain)
    )
    if as_of is not None and score is None:
        raise APIError(
            404,
            "no_snapshot_for_date",
            f"No score snapshot for {chain} on {as_of.isoformat()}",
        )

    price_reference = as_of or today
    price, freshness = await _price_at(session, chain, price_reference)
    regime: MarketRegime | None = None
    flags: Sequence[RiskFlag] = []
    if score is not None:
        regime = await session.scalar(
            select(MarketRegime).where(
                MarketRegime.chain_id == chain,
                MarketRegime.as_of_date == score.as_of_date,
                MarketRegime.version == VERSION,
            )
        )
        flags = (
            await session.scalars(
                select(RiskFlag)
                .where(
                    RiskFlag.chain_id == chain,
                    RiskFlag.as_of_date == score.as_of_date,
                    RiskFlag.version == VERSION,
                )
                .order_by(RiskFlag.flag)
            )
        ).all()

    payload: dict[str, Any] = {
        "generated_at": _generated_at(),
        "analysis_only": True,
        "slug": chain,
        "name": name,
        "symbol": symbol,
        "price": price,
        "score": _score_detail(score, chain) if score is not None else None,
        "regime": _regime_summary(regime),
        "flags": _detail_flags(flags),
        "freshness": freshness,
        "data_coverage": await _data_coverage(
            session,
            chain,
            as_of_date=as_of,
        ),
        "methodology_version": VERSION,
    }
    if score is not None and score.coverage < _coverage_max(chain):
        payload["last_full_coverage"] = await _last_full_coverage(
            session,
            chain,
            score.as_of_date,
        )
    return ChainDetailResponse(**payload)


async def _date_range(
    session: AsyncSession,
    chain: str,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date]:
    latest = await session.scalar(
        select(func.max(HealthScore.as_of_date)).where(
            HealthScore.chain_id == chain,
            HealthScore.version == VERSION,
        )
    )
    upper = to_date or latest or datetime.now(UTC).date()
    lower = from_date or upper - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if lower > upper:
        raise APIError(
            422,
            "invalid_date_range",
            "from must be on or before to",
        )
    if (upper - lower).days + 1 > MAX_HISTORY_SPAN_DAYS:
        raise APIError(
            422,
            "range_too_large",
            f"Date range cannot exceed {MAX_HISTORY_SPAN_DAYS} days",
        )
    return lower, upper


@router.get(
    "/chains/{slug}/score-history",
    response_model=ScoreHistoryResponse,
    summary="Get daily Health Score history",
    responses=PUBLIC_ERRORS,
)
async def get_score_history(
    slug: str,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> ScoreHistoryResponse:
    chain, _, _ = _require_chain(slug)
    start, end = await _date_range(session, chain, from_date, to_date)
    rows = (
        await session.scalars(
            select(HealthScore)
            .where(
                HealthScore.chain_id == chain,
                HealthScore.version == VERSION,
                HealthScore.as_of_date >= start,
                HealthScore.as_of_date <= end,
            )
            .order_by(HealthScore.as_of_date)
        )
    ).all()
    maximum = _coverage_max(chain)
    return ScoreHistoryResponse(
        generated_at=_generated_at(),
        chain=chain,
        items=[
            ScoreHistoryItem(
                as_of_date=row.as_of_date,
                score=row.score,
                coverage=row.coverage,
                is_partial=row.coverage < maximum,
                confidence_label=row.confidence_label,
            )
            for row in rows
        ],
    )


@router.get(
    "/chains/{slug}/regimes",
    response_model=RegimesResponse,
    summary="Get run-length segments of reported regimes",
    responses=PUBLIC_ERRORS,
)
async def get_regime_segments(
    slug: str,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> RegimesResponse:
    chain, _, _ = _require_chain(slug)
    start, end = await _date_range(session, chain, from_date, to_date)
    rows = (
        await session.scalars(
            select(MarketRegime)
            .where(
                MarketRegime.chain_id == chain,
                MarketRegime.version == VERSION,
                MarketRegime.as_of_date >= start,
                MarketRegime.as_of_date <= end,
            )
            .order_by(MarketRegime.as_of_date)
        )
    ).all()
    segments: list[RegimeSegment] = []
    if rows:
        segment_regime = rows[0].regime
        segment_start = rows[0].as_of_date
        segment_end = rows[0].as_of_date
        for row in rows[1:]:
            if (
                row.regime != segment_regime
                or row.as_of_date != segment_end + timedelta(days=1)
            ):
                segments.append(
                    RegimeSegment(
                        regime=segment_regime,
                        start_date=segment_start,
                        end_date=segment_end,
                        days=(segment_end - segment_start).days + 1,
                    )
                )
                segment_regime = row.regime
                segment_start = row.as_of_date
            segment_end = row.as_of_date
        segments.append(
            RegimeSegment(
                regime=segment_regime,
                start_date=segment_start,
                end_date=segment_end,
                days=(segment_end - segment_start).days + 1,
            )
        )

    latest = await session.scalar(
        select(MarketRegime)
        .where(MarketRegime.chain_id == chain, MarketRegime.version == VERSION)
        .order_by(MarketRegime.as_of_date.desc())
        .limit(1)
    )
    return RegimesResponse(
        generated_at=_generated_at(),
        chain=chain,
        segments=segments,
        latest_vol_state=latest.vol_state if latest is not None else None,
    )


def _resolve_series_input(
    chain: str,
    metric: str,
    source: str | None,
) -> FeatureInput:
    candidates = get_public_series_inputs(chain, metric)
    if not candidates:
        raise APIError(
            404,
            "series_not_available",
            f"{metric} is not in the public series registry for {chain}",
        )
    if source is None and len(candidates) > 1:
        valid = ", ".join(sorted(item.source for item in candidates))
        raise APIError(
            422,
            "source_required",
            f"source is required for {metric}; valid sources: {valid}",
        )
    selected_source = source or candidates[0].source
    for item in candidates:
        if item.source == selected_source:
            return item
    valid = ", ".join(sorted(item.source for item in candidates))
    raise APIError(
        404,
        "series_not_available",
        f"{metric} from {selected_source} is not registered for {chain}; "
        f"valid sources: {valid}",
    )


@router.get(
    "/chains/{slug}/series",
    response_model=SeriesResponse,
    summary="Get points for one allow-listed raw series",
    responses=PUBLIC_ERRORS,
)
async def get_series(
    slug: str,
    metric: str = Query(min_length=1, max_length=64),
    source: str | None = Query(default=None, min_length=1, max_length=64),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> SeriesResponse:
    chain, _, _ = _require_chain(slug)
    item = _resolve_series_input(chain, metric, source)
    coverage = await session.get(
        SeriesCoverage,
        (chain, item.metric, item.source),
    )
    status = (
        coverage.status
        if coverage is not None
        else "unavailable"
        if item.availability_note
        else "never_run"
    )
    if status in {"unavailable", "discontinued"}:
        reason = item.availability_note or (
            f"{item.metric} from {item.source} is marked {status}"
        )
        raise APIError(
            404,
            "series_not_available",
            reason,
        )

    latest_date = coverage.last_date if coverage is not None else None
    if latest_date is None:
        latest_date = await session.scalar(
            select(func.max(Observation.obs_date)).where(
                Observation.chain_code == chain,
                Observation.metric_code == item.metric,
                Observation.source_code == item.source,
            )
        )
    upper = to_date or latest_date or datetime.now(UTC).date()
    lower = from_date or upper - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if lower > upper:
        raise APIError(422, "invalid_date_range", "from must be on or before to")
    points = (
        await session.scalars(
            select(Observation)
            .where(
                Observation.chain_code == chain,
                Observation.metric_code == item.metric,
                Observation.source_code == item.source,
                Observation.obs_date >= lower,
                Observation.obs_date <= upper,
            )
            .order_by(Observation.obs_date)
            .limit(MAX_SERIES_POINTS + 1)
        )
    ).all()
    if len(points) > MAX_SERIES_POINTS:
        raise APIError(
            422,
            "too_many_points",
            f"Series responses are limited to {MAX_SERIES_POINTS} points",
        )

    return SeriesResponse(
        generated_at=_generated_at(),
        meta=SeriesMeta(
            chain=chain,
            metric=item.metric,
            source=item.source,
            role=item.role,
            derived=item.derived,
            status=status,
            first_date=coverage.first_date if coverage is not None else None,
            last_date=coverage.last_date if coverage is not None else None,
            points=coverage.points if coverage is not None else 0,
            missing=coverage.missing_days if coverage is not None else 0,
            unit_note=item.unit_note,
        ),
        points=[
            SeriesPoint(date=point.obs_date, value=point.value) for point in points
        ],
    )


def _source_methodology() -> list[SourceMethodology]:
    return [
        SourceMethodology(
            name="Binance",
            homepage_url="https://www.binance.com/",
            used_for=["daily spot prices and quote-volume proxies"],
            terms_note="USDT is used as a USD proxy; redistribution terms apply.",
        ),
        SourceMethodology(
            name="DefiLlama",
            homepage_url="https://defillama.com/",
            used_for=[
                "TVL, stablecoin supply, DEX volume, and context-only protocol fees"
            ],
            terms_note=(
                "Public API; attribution terms should be reviewed. Series units "
                "are UNVERIFIED."
            ),
        ),
        SourceMethodology(
            name="Coin Metrics Community",
            homepage_url="https://coinmetrics.io/",
            used_for=[
                "BTC/ETH active addresses and transaction counts; context market cap"
            ],
            terms_note="Non-commercial Community API; attribution is required.",
        ),
        SourceMethodology(
            name="CoinGecko",
            homepage_url="https://www.coingecko.com/",
            used_for=["context-only market-cap snapshots"],
            terms_note="Free API attribution required; terms apply.",
        ),
        SourceMethodology(
            name="mempool.space",
            homepage_url="https://mempool.space/",
            used_for=["BTC network-health and RPC diagnostics, not score inputs"],
            terms_note=(
                "Public API; attribution and rate-limit terms should be reviewed."
            ),
        ),
        SourceMethodology(
            name="Blockchain.info",
            homepage_url="https://www.blockchain.com/",
            used_for=["BTC hashrate and derived USD network fees"],
            terms_note=(
                "API/chart terms apply; attribution requirements require review."
            ),
        ),
    ]


@router.get(
    "/methodology",
    response_model=MethodologyResponse,
    summary="Get the configured v1 score methodology",
    responses=PUBLIC_ERRORS,
)
async def get_methodology() -> MethodologyResponse:
    pillars = [
        PillarMethodology(
            name=pillar.name,
            weight=pillar.weight,
            components=[
                ComponentMethodology(
                    feature=component.feature,
                    weight=component.weight,
                    direction=component.direction,
                    chains=list(component.chains),
                    derived_label=component.derived_label,
                )
                for component in COMPONENTS
                if component.pillar == pillar.name
            ],
        )
        for pillar in PILLARS
    ]
    return MethodologyResponse(
        generated_at=_generated_at(),
        version=VERSION,
        percentile_window_days=PERCENTILE_WINDOW_DAYS,
        minimum_percentile_observations=MIN_PERCENTILE_OBSERVATIONS,
        pillars=pillars,
        minimum_score_coverage=NO_SCORE_COVERAGE,
        confidence_thresholds={
            "high": HIGH_CONFIDENCE_COVERAGE,
            "medium": MEDIUM_CONFIDENCE_COVERAGE,
        },
        coverage_max=MAX_COVERAGE,
        regime_rules=RegimeRulesMethodology(
            stress_drawdown_lte=STRESS_DRAWDOWN_THRESHOLD,
            uptrend="price_vs_sma200 > 0 AND ret_90d > 0",
            downtrend="price_vs_sma200 < 0 AND ret_90d < 0",
            otherwise="range",
            priority=[
                REGIME_STRESS,
                REGIME_UPTREND,
                REGIME_DOWNTREND,
                REGIME_RANGE,
            ],
            hysteresis_days=HYSTERESIS_DAYS,
        ),
        volatility_overlay=VolatilityOverlayMethodology(
            feature="realized_vol_90d",
            low_lte=LOW_VOLATILITY_STATE_THRESHOLD,
            high_gte=HIGH_VOLATILITY_STATE_THRESHOLD,
            low_state=VOL_STATE_LOW,
            normal_state=VOL_STATE_NORMAL,
            high_state=VOL_STATE_HIGH,
        ),
        risk_flags=[
            RiskRuleMethodology(
                flag=rule.flag,
                feature=rule.feature,
                value_kind=rule.value_kind,
                comparison=rule.comparison,
                threshold=rule.threshold,
                severity=rule.severity,
                high_severity_threshold=rule.high_severity_threshold,
                chains=list(rule.chains),
            )
            for rule in RISK_FLAGS
        ],
        sources=_source_methodology(),
        limitations=[
            "Scores are relative to each chain's own trailing history.",
            "Chains use different component sets; cross-chain comparisons "
            "are indicative only.",
            "Regime labels confirm only after five consecutive raw labels, so "
            "regime changes lag by design.",
            "DefiLlama series unit semantics are UNVERIFIED.",
            "Analysis only: not financial advice, not a prediction, and no "
            "buy/sell calls.",
        ],
    )
