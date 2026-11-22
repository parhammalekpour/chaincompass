from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.fundamental_report import (
    FundamentalReportSnapshot,
    RegimePoint,
    build_fundamental_report,
)
from app.analytics.score_config import COMPONENTS, VERSION
from app.db.models.health import HealthScore, MarketRegime, RiskFlag
from app.db.models.ingestion import ComputedFeature


async def load_fundamental_report(
    session: AsyncSession,
    chain: str,
    as_of: date | None = None,
) -> dict[str, object]:
    score_query = select(HealthScore).where(
        HealthScore.chain_id == chain,
        HealthScore.version == VERSION,
    )
    if as_of is not None:
        score_query = score_query.where(HealthScore.as_of_date == as_of)
    else:
        score_query = score_query.order_by(HealthScore.as_of_date.desc()).limit(1)
    current_score = await session.scalar(score_query)
    if current_score is None:
        return {"ok": False, "error": {"code": "no_data"}}

    report_date = current_score.as_of_date
    score_dates = (
        report_date,
        date.fromordinal(report_date.toordinal() - 30),
        date.fromordinal(report_date.toordinal() - 90),
    )
    score_rows = (
        await session.scalars(
            select(HealthScore).where(
                HealthScore.chain_id == chain,
                HealthScore.version == VERSION,
                HealthScore.as_of_date.in_(score_dates),
            )
        )
    ).all()
    scores = {row.as_of_date: row.score for row in score_rows}

    component_names = tuple(spec.feature for spec in COMPONENTS if chain in spec.chains)
    feature_rows = (
        await session.scalars(
            select(ComputedFeature).where(
                ComputedFeature.chain_id == chain,
                ComputedFeature.as_of_date == report_date,
                ComputedFeature.feature.in_(component_names),
            )
        )
    ).all()
    feature_values: dict[str, Decimal] = {
        row.feature: row.value for row in feature_rows
    }
    component_percentiles: dict[str, Decimal] = {}
    for component in current_score.components:
        feature = component.get("feature")
        value = component.get("value")
        percentile = component.get("percentile")
        if isinstance(feature, str) and isinstance(value, str):
            feature_values[feature] = Decimal(value)
        if isinstance(feature, str) and isinstance(percentile, str):
            component_percentiles[feature] = Decimal(percentile)

    regime_rows = (
        await session.scalars(
            select(MarketRegime)
            .where(
                MarketRegime.chain_id == chain,
                MarketRegime.version == VERSION,
                MarketRegime.as_of_date <= report_date,
            )
            .order_by(MarketRegime.as_of_date.desc())
        )
    ).all()
    regimes = tuple(
        RegimePoint(
            as_of_date=row.as_of_date,
            regime=row.regime,
            vol_state=row.vol_state,
        )
        for row in regime_rows
    )
    flags = (
        await session.scalars(
            select(RiskFlag)
            .where(
                RiskFlag.chain_id == chain,
                RiskFlag.version == VERSION,
                RiskFlag.as_of_date == report_date,
            )
            .order_by(RiskFlag.flag)
        )
    ).all()

    return build_fundamental_report(
        FundamentalReportSnapshot(
            chain=chain,
            as_of_date=report_date,
            scores=scores,
            confidence=current_score.confidence_label,
            coverage=current_score.coverage,
            regime_rows=regimes,
            flags=tuple((row.flag, row.severity) for row in flags),
            feature_values=feature_values,
            component_percentiles=component_percentiles,
        )
    )
