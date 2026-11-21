"""SELECT-only loading for the registered research studies."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.scenarios import PricePoint
from app.analytics.score_config import CHAINS, REGIME_FEATURES
from app.analytics.scoring import FeatureRecord
from app.db.models.health import HealthScore, MarketRegime
from app.db.models.ingestion import ComputedFeature, Observation
from app.db.session import SessionFactory
from app.research.health_score import ScorePoint


@dataclass(frozen=True)
class ResearchData:
    prices_by_chain: dict[str, tuple[PricePoint, ...]]
    scores_by_chain: dict[str, tuple[ScorePoint, ...]]
    features_by_chain: dict[str, tuple[FeatureRecord, ...]]
    stored_regimes_by_chain: dict[str, tuple[tuple[date, str], ...]]


async def load_research_data(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
) -> ResearchData:
    prices: dict[str, list[PricePoint]] = defaultdict(list)
    scores: dict[str, list[ScorePoint]] = defaultdict(list)
    features: dict[str, list[FeatureRecord]] = defaultdict(list)
    regimes: dict[str, list[tuple[date, str]]] = defaultdict(list)

    async with session_factory() as session:
        price_rows = await session.execute(
            select(
                Observation.chain_code,
                Observation.obs_date,
                Observation.value,
            )
            .where(
                Observation.chain_code.in_(CHAINS),
                Observation.metric_code == "price_close_usd",
                Observation.source_code == "binance",
            )
            .order_by(Observation.chain_code, Observation.obs_date)
        )
        for chain, obs_date, value in price_rows:
            prices[chain].append((obs_date, value))

        score_rows = await session.execute(
            select(
                HealthScore.chain_id,
                HealthScore.as_of_date,
                HealthScore.score,
            )
            .where(
                HealthScore.chain_id.in_(CHAINS),
                HealthScore.version == "v1",
            )
            .order_by(HealthScore.chain_id, HealthScore.as_of_date)
        )
        for chain, as_of_date, score in score_rows:
            scores[chain].append((as_of_date, score))

        feature_rows = await session.execute(
            select(
                ComputedFeature.chain_id,
                ComputedFeature.feature,
                ComputedFeature.as_of_date,
                ComputedFeature.value,
                ComputedFeature.source_metric,
                ComputedFeature.source,
            )
            .where(ComputedFeature.chain_id.in_(CHAINS))
            .order_by(
                ComputedFeature.chain_id,
                ComputedFeature.feature,
                ComputedFeature.as_of_date,
            )
        )
        for chain, feature, as_of_date, value, metric, source in feature_rows:
            features[chain].append(
                FeatureRecord(
                    chain=chain,
                    feature=feature,
                    as_of_date=as_of_date,
                    value=value,
                    source_metric=metric,
                    source=source,
                )
            )

        regime_rows = await session.execute(
            select(
                MarketRegime.chain_id,
                MarketRegime.as_of_date,
                MarketRegime.regime,
            )
            .where(
                MarketRegime.chain_id.in_(CHAINS),
                MarketRegime.version == "v1",
            )
            .order_by(MarketRegime.chain_id, MarketRegime.as_of_date)
        )
        for chain, as_of_date, regime in regime_rows:
            regimes[chain].append((as_of_date, regime))

    return ResearchData(
        prices_by_chain={chain: tuple(prices.get(chain, ())) for chain in CHAINS},
        scores_by_chain={chain: tuple(scores.get(chain, ())) for chain in CHAINS},
        features_by_chain={
            chain: tuple(
                record
                for record in features.get(chain, ())
                if record.feature in REGIME_FEATURES
                and (record.source_metric, record.source)
                == REGIME_FEATURES[record.feature]
            )
            for chain in CHAINS
        },
        stored_regimes_by_chain={
            chain: tuple(regimes.get(chain, ())) for chain in CHAINS
        },
    )
