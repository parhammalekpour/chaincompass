from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.analytics.registry import get_feature_input
from app.analytics.score_config import (
    CHAINS,
    COMPONENTS,
    DEEP_DRAWDOWN_THRESHOLD,
    HASHRATE_DECLINE_THRESHOLD,
    HIGH_DEEP_DRAWDOWN_THRESHOLD,
    HIGH_VOLATILITY_RISK_THRESHOLD,
    HYSTERESIS_DAYS,
    LIQUIDITY_DRYING_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    STABLECOIN_CONTRACTION_THRESHOLD,
    TVL_OUTFLOW_THRESHOLD,
    USAGE_DECLINE_THRESHOLD,
    VERSION,
)
from app.analytics.scoring import (
    FeatureRecord,
    _raw_regime,
    _regime_values,
    _volatility_state,
    compute_analytics,
    evaluate_risk_flags,
    maximum_coverage,
    point_in_time_percentiles,
    score_components_are_registry_approved,
)

START = date(2020, 1, 1)


def _record(
    feature: str,
    as_of: date,
    value: Decimal,
    *,
    chain: str = "btc",
    source_metric: str = "price_close_usd",
    source: str = "binance",
) -> FeatureRecord:
    return FeatureRecord(chain, feature, as_of, value, source_metric, source)


def _component_records(
    chain: str,
    *,
    days: int,
    omit_at_end: set[str] | None = None,
) -> list[FeatureRecord]:
    records: list[FeatureRecord] = []
    omit_at_end = omit_at_end or set()
    for spec in COMPONENTS:
        if chain not in spec.chains:
            continue
        for index in range(days):
            if index == days - 1 and spec.feature in omit_at_end:
                continue
            records.append(
                FeatureRecord(
                    chain=chain,
                    feature=spec.feature,
                    as_of_date=START + timedelta(days=index),
                    value=Decimal(index + 1),
                    source_metric=spec.source_metric,
                    source=spec.source,
                )
            )
    return records


def _output_bytes(output, cutoff: date) -> bytes:
    snapshot = {
        "scores": [
            {
                **asdict(item),
                "score": str(item.score) if item.score is not None else None,
                "coverage": str(item.coverage),
                "pillars": [
                    {
                        **asdict(pillar),
                        "score": (
                            str(pillar.score) if pillar.score is not None else None
                        ),
                    }
                    for pillar in item.pillars
                ],
                "components": [
                    {
                        **asdict(component),
                        "value": str(component.value),
                        "percentile": str(component.percentile),
                    }
                    for component in item.components
                ],
            }
            for item in output.scores
            if item.as_of_date <= cutoff
        ],
        "regimes": [
            asdict(item) for item in output.regimes if item.as_of_date <= cutoff
        ],
        "risk_flags": [
            {
                **asdict(item),
                "value": str(item.value),
                "threshold": str(item.threshold),
            }
            for item in output.risk_flags
            if item.as_of_date <= cutoff
        ],
    }
    return json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()


def test_percentile_uses_midrank_minimum_history_and_direction() -> None:
    records = [
        _record(
            "sample",
            START + timedelta(days=index),
            Decimal(1 if index < 363 else 2),
        )
        for index in range(365)
    ]
    as_of = records[-1].as_of_date

    higher = point_in_time_percentiles(records)
    lower = point_in_time_percentiles(records, direction="lower_is_better")
    insufficient = point_in_time_percentiles(records[:-1])

    assert higher[as_of] == Decimal("99.726027397260")
    assert lower[as_of] == Decimal("0.273972602740")
    assert insufficient == {}

    cutoff = START + timedelta(days=1095)
    window_records = [
        _record("sample", cutoff - timedelta(days=1095), Decimal("999999")),
        *[
            _record(
                "sample",
                cutoff - timedelta(days=offset),
                Decimal(1 if offset else 2),
            )
            for offset in range(364, -1, -1)
        ],
    ]
    assert point_in_time_percentiles(window_records)[cutoff] == Decimal(
        "99.863013698630"
    )


def test_missing_component_reduces_coverage_and_pillar_weights_renormalize() -> None:
    chain = "btc"
    complete = compute_analytics(chain, _component_records(chain, days=365))
    omitted_feature = "active_addresses_chg90"
    missing = compute_analytics(
        chain,
        _component_records(
            chain,
            days=365,
            omit_at_end={omitted_feature},
        ),
    )
    complete_target = complete.scores[-1]
    missing_target = missing.scores[-1]
    adoption = next(
        pillar for pillar in missing_target.pillars if pillar.name == "adoption"
    )

    assert complete_target.coverage == Decimal("0.7000")
    assert missing_target.coverage == Decimal("0.5500")
    assert adoption.available and adoption.weight_used == 15
    assert all(item.feature != omitted_feature for item in missing_target.components)
    assert missing_target.score is not None
    volatility = next(
        item
        for item in complete_target.components
        if item.feature == "realized_vol_90d"
    )
    assert volatility.percentile == Decimal("0.136986301370")


def test_weighted_score_matches_hand_computed_value_and_two_place_rounding() -> None:
    records = _component_records("btc", days=365)
    records = [
        replace(record, value=Decimal(2))
        if record.feature == "active_addresses_chg90"
        and record.as_of_date == START + timedelta(days=364)
        else replace(record, value=Decimal(1))
        for record in records
    ]

    result = compute_analytics("btc", records).scores[-1]
    adoption = next(pillar for pillar in result.pillars if pillar.name == "adoption")

    assert adoption.score == Decimal("74.931506849315")
    assert result.score == Decimal("60.68")


def test_coverage_below_point_four_has_no_score_row_value() -> None:
    market_features = {
        spec.feature for spec in COMPONENTS if spec.pillar == "market_condition"
    }
    records = [
        record
        for record in _component_records("btc", days=365)
        if record.feature in market_features
    ]
    result = compute_analytics("btc", records)
    latest = result.scores[-1]

    assert latest.coverage == Decimal("0.3000")
    assert latest.score is None

    threshold_records = [
        record
        for record in _component_records("btc", days=365)
        if next(spec for spec in COMPONENTS if spec.feature == record.feature).pillar
        in {"market_condition", "security_economics"}
    ]
    threshold_result = compute_analytics("btc", threshold_records).scores[-1]
    assert threshold_result.coverage == Decimal("0.4000")
    assert threshold_result.score is not None


def test_registry_derived_maximum_coverage_matches_amendment() -> None:
    expected_coverage = {
        "btc": Decimal("0.7000"),
        "eth": Decimal("0.9000"),
        "sol": Decimal("0.6000"),
        "bnb": Decimal("0.6000"),
    }
    assert {chain: maximum_coverage(chain) for chain in CHAINS} == expected_coverage
    assert all(score_components_are_registry_approved(chain) for chain in CHAINS)
    labels = {
        chain: compute_analytics(
            chain,
            _component_records(chain, days=365),
        )
        .scores[-1]
        .confidence_label
        for chain in CHAINS
    }
    assert labels == {
        "btc": "Medium",
        "eth": "High",
        "sol": "Medium",
        "bnb": "Medium",
    }


def test_context_and_unavailable_inputs_never_become_score_components() -> None:
    score_records = _component_records("btc", days=365)
    context_records = [
        _record(
            "market_cap_usd_chg90",
            START + timedelta(days=index),
            Decimal(index + 1),
            source_metric="market_cap_usd",
            source="coin_metrics",
        )
        for index in range(365)
    ]
    context_records.extend(
        _record(
            "protocol_fees_usd_chg90",
            START + timedelta(days=index),
            Decimal(index + 1),
            source_metric="protocol_fees_usd",
            source="defillama",
        )
        for index in range(365)
    )
    context_records.extend(
        _record(
            feature,
            START + timedelta(days=index),
            Decimal(index + 1),
            source_metric=metric,
            source=source,
        )
        for feature, metric, source in (
            ("dex_volume_usd_chg90", "dex_volume_usd", "defillama"),
            ("coingecko_market_cap_usd_chg90", "market_cap_usd", "coingecko"),
            ("tvl_usd_chg90", "tvl_usd", "defillama"),
        )
        for index in range(365)
    )
    expected = compute_analytics("btc", score_records)
    output = compute_analytics("btc", score_records + context_records)

    cutoff = START + timedelta(days=364)
    assert _output_bytes(output, cutoff) == _output_bytes(expected, cutoff)
    assert output.scores[-1].components
    assert all(
        component.feature
        not in {
            "market_cap_usd_chg90",
            "protocol_fees_usd_chg90",
            "dex_volume_usd_chg90",
            "coingecko_market_cap_usd_chg90",
            "tvl_usd_chg90",
        }
        for item in output.scores
        for component in item.components
    )
    for score in output.scores:
        for component in score.components:
            spec = next(
                item for item in COMPONENTS if item.feature == component.feature
            )
            registry_input = get_feature_input(
                "btc",
                spec.source_metric,
                spec.source,
            )
            assert registry_input is not None and registry_input.role == "score"


def test_regime_priority_hysteresis_and_days_in_regime() -> None:
    assert (
        _raw_regime(
            Decimal("-0.50"),
            Decimal("0.1"),
            Decimal("0.1"),
        )
        == "stress"
    )
    assert _raw_regime(None, Decimal("0.1"), Decimal("0.1")) == "uptrend"
    assert _raw_regime(None, Decimal("-0.1"), Decimal("-0.1")) == "downtrend"
    assert _raw_regime(None, Decimal("0.1"), Decimal("-0.1")) == "range"

    by_feature: dict[str, dict[date, FeatureRecord]] = {
        "price_vs_sma200": {},
        "ret_90d": {},
    }
    for index in range(HYSTERESIS_DAYS + 1):
        as_of = START + timedelta(days=index)
        value = Decimal("-1") if index == 0 else Decimal("1")
        by_feature["price_vs_sma200"][as_of] = _record(
            "price_vs_sma200",
            as_of,
            value,
        )
        by_feature["ret_90d"][as_of] = _record("ret_90d", as_of, value)

    regimes = _regime_values("btc", by_feature, {})
    assert [item.raw_regime for item in regimes] == [
        "downtrend",
        "uptrend",
        "uptrend",
        "uptrend",
        "uptrend",
        "uptrend",
    ]
    assert [item.regime for item in regimes[:5]] == ["downtrend"] * 5
    assert regimes[5].regime == "uptrend"
    assert regimes[5].days_in_regime == 1
    assert _volatility_state(Decimal("80")) == "high"
    assert _volatility_state(Decimal("20")) == "low"
    assert _volatility_state(None) is None


@pytest.mark.parametrize(
    ("flag", "feature", "threshold", "comparison", "chains"),
    [
        (
            "deep_drawdown",
            "drawdown_365d",
            DEEP_DRAWDOWN_THRESHOLD,
            "lte",
            CHAINS,
        ),
        (
            "liquidity_drying",
            "volume_ratio_30_365",
            LIQUIDITY_DRYING_THRESHOLD,
            "lt",
            CHAINS,
        ),
        (
            "usage_decline",
            "active_addresses_chg90",
            USAGE_DECLINE_THRESHOLD,
            "lte",
            ("btc", "eth"),
        ),
        (
            "tvl_outflow",
            "tvl_usd_chg90",
            TVL_OUTFLOW_THRESHOLD,
            "lte",
            ("eth", "sol", "bnb"),
        ),
        (
            "stablecoin_contraction",
            "stablecoin_supply_usd_chg90",
            STABLECOIN_CONTRACTION_THRESHOLD,
            "lte",
            ("eth", "sol", "bnb"),
        ),
        (
            "hashrate_decline",
            "hashrate_chg90",
            HASHRATE_DECLINE_THRESHOLD,
            "lte",
            ("btc",),
        ),
    ],
)
def test_risk_flag_threshold_boundaries(
    flag: str,
    feature: str,
    threshold: Decimal,
    comparison: str,
    chains: tuple[str, ...],
) -> None:
    chain = chains[0]
    at_threshold = evaluate_risk_flags(
        chain,
        START,
        {feature: threshold},
        {},
        Decimal("1"),
    )
    beyond = evaluate_risk_flags(
        chain,
        START,
        {feature: threshold - Decimal("0.000000000001")},
        {},
        Decimal("1"),
    )
    at_threshold_names = {item.flag for item in at_threshold}
    beyond_names = {item.flag for item in beyond}

    assert (flag in at_threshold_names) == (comparison == "lte")
    assert flag in beyond_names


def test_volatility_and_low_confidence_flag_boundaries_and_severity() -> None:
    below_volatility = evaluate_risk_flags(
        "btc",
        START,
        {},
        {"realized_vol_30d": HIGH_VOLATILITY_RISK_THRESHOLD - Decimal("0.01")},
        Decimal("0.50"),
    )
    at_volatility = evaluate_risk_flags(
        "btc",
        START,
        {},
        {"realized_vol_30d": HIGH_VOLATILITY_RISK_THRESHOLD},
        Decimal("0.50"),
    )
    medium_drawdown = evaluate_risk_flags(
        "btc",
        START,
        {"drawdown_365d": DEEP_DRAWDOWN_THRESHOLD},
        {},
        Decimal("0.50"),
    )
    high_drawdown = evaluate_risk_flags(
        "btc",
        START,
        {"drawdown_365d": HIGH_DEEP_DRAWDOWN_THRESHOLD},
        {},
        Decimal("0.50"),
    )
    low_confidence = evaluate_risk_flags(
        "btc",
        START,
        {},
        {},
        LOW_CONFIDENCE_THRESHOLD - Decimal("0.0001"),
    )
    at_low_confidence_boundary = evaluate_risk_flags(
        "btc",
        START,
        {},
        {},
        LOW_CONFIDENCE_THRESHOLD,
    )

    assert "high_volatility" not in {item.flag for item in below_volatility}
    assert "high_volatility" in {item.flag for item in at_volatility}
    assert (
        next(item for item in medium_drawdown if item.flag == "deep_drawdown").severity
        == "medium"
    )
    assert (
        next(item for item in high_drawdown if item.flag == "deep_drawdown").severity
        == "high"
    )
    assert (
        next(item for item in low_confidence if item.flag == "low_confidence").severity
        == "info"
    )
    assert "low_confidence" not in {item.flag for item in at_low_confidence_boundary}


def test_score_regime_and_flags_are_point_in_time_and_deterministic() -> None:
    score_feature_inputs = {
        spec.feature: (spec.source_metric, spec.source)
        for spec in COMPONENTS
        if "btc" in spec.chains
    }
    score_feature_inputs.update(
        {
            "ret_90d": ("price_close_usd", "binance"),
            "realized_vol_30d": ("price_close_usd", "binance"),
        }
    )
    records: list[FeatureRecord] = []
    length = 1100
    for feature, (source_metric, source) in score_feature_inputs.items():
        records.extend(
            FeatureRecord(
                chain="btc",
                feature=feature,
                as_of_date=START + timedelta(days=index),
                value=Decimal(index % 97 + 1),
                source_metric=source_metric,
                source=source,
            )
            for index in range(length)
        )

    cutoff = START + timedelta(days=length - 1)
    initial = compute_analytics("btc", records)
    future = []
    for offset in range(1, 18):
        future.extend(
            FeatureRecord(
                chain="btc",
                feature=feature,
                as_of_date=cutoff + timedelta(days=offset),
                value=Decimal("999999999"),
                source_metric=source_metric,
                source=source,
            )
            for feature, (source_metric, source) in score_feature_inputs.items()
        )
    mutated_future = [
        FeatureRecord(
            chain=item.chain,
            feature=item.feature,
            as_of_date=item.as_of_date,
            value=Decimal("-1e20") * Decimal(index + 1),
            source_metric=item.source_metric,
            source=item.source,
        )
        for index, item in enumerate(future)
    ]

    appended = compute_analytics("btc", records + future)
    mutated = compute_analytics("btc", records + mutated_future)

    assert _output_bytes(appended, cutoff) == _output_bytes(initial, cutoff)
    assert _output_bytes(mutated, cutoff) == _output_bytes(initial, cutoff)
    assert initial.scores[-1].version == VERSION
    assert all(
        isinstance(component.value, Decimal)
        and isinstance(component.percentile, Decimal)
        for score in initial.scores
        for component in score.components
    )
    assert all(
        isinstance(score.coverage, Decimal)
        and (score.score is None or isinstance(score.score, Decimal))
        and all(
            pillar.score is None or isinstance(pillar.score, Decimal)
            for pillar in score.pillars
        )
        for score in initial.scores
    )
    assert all(
        isinstance(flag.value, Decimal) and isinstance(flag.threshold, Decimal)
        for flag in initial.risk_flags
    )
    assert list(score.as_of_date for score in initial.scores) == sorted(
        score.as_of_date for score in initial.scores
    )
    assert all(
        [component.feature for component in score.components]
        == sorted(
            [component.feature for component in score.components],
            key=lambda feature: next(
                index
                for index, spec in enumerate(COMPONENTS)
                if spec.feature == feature
            ),
        )
        for score in initial.scores
    )
