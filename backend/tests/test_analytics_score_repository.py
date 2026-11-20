from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.score_config import COMPONENTS, VERSION
from app.analytics.score_repository import (
    compute_scores_and_store,
    score_status,
)
from app.db.models.health import HealthScore, MarketRegime, RiskFlag
from app.db.models.ingestion import ComputedFeature, IngestionRun
from app.ingestion.seed import seed_reference_data

pytestmark = pytest.mark.asyncio(loop_scope="session")
START = date(2020, 1, 1)


async def _analytics_checksum(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, str]:
    async with session_factory() as session:
        scores = (
            await session.execute(
                select(
                    HealthScore.chain_id,
                    HealthScore.as_of_date,
                    HealthScore.version,
                    HealthScore.score,
                    HealthScore.coverage,
                    HealthScore.confidence_label,
                    HealthScore.pillars,
                    HealthScore.components,
                ).order_by(
                    HealthScore.chain_id,
                    HealthScore.as_of_date,
                    HealthScore.version,
                )
            )
        ).all()
        regimes = (
            await session.execute(
                select(
                    MarketRegime.chain_id,
                    MarketRegime.as_of_date,
                    MarketRegime.version,
                    MarketRegime.regime,
                    MarketRegime.raw_regime,
                    MarketRegime.vol_state,
                    MarketRegime.days_in_regime,
                ).order_by(
                    MarketRegime.chain_id,
                    MarketRegime.as_of_date,
                    MarketRegime.version,
                )
            )
        ).all()
        flags = (
            await session.execute(
                select(
                    RiskFlag.chain_id,
                    RiskFlag.as_of_date,
                    RiskFlag.flag,
                    RiskFlag.version,
                    RiskFlag.severity,
                    RiskFlag.value,
                    RiskFlag.threshold,
                ).order_by(
                    RiskFlag.chain_id,
                    RiskFlag.as_of_date,
                    RiskFlag.flag,
                    RiskFlag.version,
                )
            )
        ).all()
    payload = json.dumps(
        {
            "scores": scores,
            "regimes": regimes,
            "flags": flags,
        },
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return len(scores) + len(regimes) + len(flags), hashlib.md5(payload).hexdigest()


@pytest.mark.asyncio
async def test_score_backfill_update_status_and_reproducibility(
    auth_session_factory: async_sessionmaker[AsyncSession],
    clean_ingestion_tables,
) -> None:
    async with auth_session_factory() as session:
        await seed_reference_data(session)
        feature_sources = {
            spec.feature: (spec.source_metric, spec.source)
            for spec in COMPONENTS
            if "btc" in spec.chains
        }
        feature_sources.update(
            {
                "ret_90d": ("price_close_usd", "binance"),
                "realized_vol_30d": ("price_close_usd", "binance"),
            }
        )
        session.add_all(
            ComputedFeature(
                chain_id="btc",
                feature=feature,
                as_of_date=START + timedelta(days=index),
                value=Decimal(index + 1),
                n_obs=1,
                window_days=120,
                source_metric=source_metric,
                source=source,
            )
            for index in range(365)
            for feature, (source_metric, source) in feature_sources.items()
        )
        session.add(
            ComputedFeature(
                chain_id="btc",
                feature="market_cap_usd_chg90",
                as_of_date=START + timedelta(days=364),
                value=Decimal("999999"),
                n_obs=30,
                window_days=120,
                source_metric="market_cap_usd",
                source="coin_metrics",
            )
        )
        await session.commit()

    today = START + timedelta(days=365)
    first = await compute_scores_and_store(
        mode="backfill",
        chain="btc",
        today=today,
        session_factory=auth_session_factory,
    )
    checksum_after_first = await _analytics_checksum(auth_session_factory)

    assert first.rows_by_chain["btc"].scores == 1
    assert first.rows_by_chain["btc"].regimes == 365
    assert first.rows_by_chain["btc"].risk_flags == 365
    assert checksum_after_first[0] == 731

    update = await compute_scores_and_store(
        mode="update",
        chain="btc",
        today=today,
        session_factory=auth_session_factory,
    )
    checksum_after_update = await _analytics_checksum(auth_session_factory)
    assert update.rows_deleted > 0
    assert checksum_after_update == checksum_after_first

    second = await compute_scores_and_store(
        mode="backfill",
        chain="btc",
        today=today,
        session_factory=auth_session_factory,
    )
    checksum_after_second = await _analytics_checksum(auth_session_factory)
    assert second.rows_upserted == first.rows_upserted
    assert checksum_after_second == checksum_after_first

    statuses = await score_status(
        chain="btc",
        session_factory=auth_session_factory,
    )
    assert len(statuses) == 1
    assert statuses[0].first_date == START + timedelta(days=364)
    assert statuses[0].last_date == START + timedelta(days=364)
    assert statuses[0].rows == 1
    assert statuses[0].coverage == "0.7000"
    assert statuses[0].confidence_label == "Medium"
    assert statuses[0].regime == "uptrend"
    assert statuses[0].vol_state is not None
    assert [(flag.flag, flag.severity) for flag in statuses[0].flags] == [
        ("high_volatility", "medium")
    ]

    async with auth_session_factory() as session:
        score = await session.get(
            HealthScore,
            ("btc", START + timedelta(days=364), VERSION),
        )
        assert score is not None
        assert isinstance(score.score, Decimal)
        assert isinstance(score.coverage, Decimal)
        assert all(
            component["feature"] != "market_cap_usd_chg90"
            for component in score.components
        )
        successful_runs = await session.scalar(
            select(func.count())
            .select_from(IngestionRun)
            .where(IngestionRun.job == "scores", IngestionRun.status == "ok")
        )
    assert successful_runs == 3
