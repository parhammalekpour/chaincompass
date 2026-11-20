from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from app.analytics.registry import get_feature_input
from app.analytics.score_config import (
    CHAINS,
    COMPONENTS,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    COVERAGE_QUANTUM,
    DECIMAL_PRECISION,
    HIGH_CONFIDENCE_COVERAGE,
    HIGH_VOLATILITY_STATE_THRESHOLD,
    HYSTERESIS_DAYS,
    LOW_VOLATILITY_STATE_THRESHOLD,
    MEDIUM_CONFIDENCE_COVERAGE,
    MIDRANK_EQUAL_FACTOR,
    MIN_PERCENTILE_OBSERVATIONS,
    NO_SCORE_COVERAGE,
    PERCENTILE_QUANTUM,
    PERCENTILE_SCALE,
    PERCENTILE_WINDOW_DAYS,
    PILLAR_QUANTUM,
    PILLARS,
    REGIME_DOWNTREND,
    REGIME_FEATURES,
    REGIME_RANGE,
    REGIME_STRESS,
    REGIME_UPTREND,
    RISK_FEATURES,
    RISK_FLAGS,
    SCORE_QUANTUM,
    SEVERITY_HIGH,
    STRESS_DRAWDOWN_THRESHOLD,
    VALUE_QUANTUM,
    VERSION,
    VOL_STATE_HIGH,
    VOL_STATE_LOW,
    VOL_STATE_NORMAL,
    WEIGHT_DENOMINATOR,
)


@dataclass(frozen=True)
class FeatureRecord:
    chain: str
    feature: str
    as_of_date: date
    value: Decimal
    source_metric: str
    source: str


@dataclass(frozen=True)
class ComponentValue:
    feature: str
    value: Decimal
    percentile: Decimal
    weight: int
    direction: str
    derived_label: str | None


@dataclass(frozen=True)
class PillarValue:
    name: str
    score: Decimal | None
    weight_used: int
    available: bool


@dataclass(frozen=True)
class ScoreValue:
    chain: str
    as_of_date: date
    score: Decimal | None
    coverage: Decimal
    confidence_label: str
    pillars: tuple[PillarValue, ...]
    components: tuple[ComponentValue, ...]
    version: str = VERSION


@dataclass(frozen=True)
class RegimeValue:
    chain: str
    as_of_date: date
    regime: str
    raw_regime: str
    vol_state: str | None
    days_in_regime: int
    version: str = VERSION


@dataclass(frozen=True)
class RiskFlagValue:
    chain: str
    as_of_date: date
    flag: str
    severity: str
    value: Decimal
    threshold: Decimal
    version: str = VERSION


@dataclass(frozen=True)
class AnalyticsOutput:
    scores: tuple[ScoreValue, ...]
    regimes: tuple[RegimeValue, ...]
    risk_flags: tuple[RiskFlagValue, ...]


def _validate_records(
    chain: str,
    records: Iterable[FeatureRecord],
) -> dict[str, dict[date, FeatureRecord]]:
    if chain not in CHAINS:
        raise ValueError(f"unsupported chain: {chain}")
    by_feature: dict[str, dict[date, FeatureRecord]] = {}
    for record in records:
        if record.chain != chain:
            raise ValueError("all feature records must belong to the requested chain")
        if not isinstance(record.value, Decimal):
            raise TypeError("score inputs must be Decimal values")
        if not record.value.is_finite():
            raise ValueError("score inputs must be finite")
        daily = by_feature.setdefault(record.feature, {})
        if record.as_of_date in daily:
            raise ValueError(
                f"duplicate feature date: {record.feature}/{record.as_of_date}"
            )
        daily[record.as_of_date] = record
    return by_feature


def _validate_component_registry(chain: str) -> None:
    for component in COMPONENTS:
        if chain not in component.chains:
            continue
        registered = get_feature_input(
            chain,
            component.source_metric,
            component.source,
        )
        if registered is None or registered.role != "score":
            raise ValueError(
                f"score component is not registry-approved: {chain}/{component.feature}"
            )

    for spec in RISK_FLAGS:
        if chain not in spec.chains or spec.feature is None:
            continue
        if spec.source_metric is None or spec.source is None:
            raise ValueError(f"risk flag input is incomplete: {spec.flag}")
        registered = get_feature_input(chain, spec.source_metric, spec.source)
        if registered is None or registered.role != "score":
            raise ValueError(
                f"risk input is not registry-approved: {chain}/{spec.feature}"
            )

    for feature, (source_metric, source) in REGIME_FEATURES.items():
        if feature == "realized_vol_90d" or feature == "ret_90d":
            registered = get_feature_input(chain, source_metric, source)
            if registered is None or registered.role != "score":
                raise ValueError(
                    f"regime input is not registry-approved: {chain}/{feature}"
                )


def point_in_time_percentiles(
    records: Sequence[FeatureRecord],
    *,
    as_of_dates: Iterable[date] | None = None,
    direction: str = "higher_is_better",
) -> dict[date, Decimal]:
    if direction not in {"higher_is_better", "lower_is_better"}:
        raise ValueError(f"unsupported percentile direction: {direction}")
    ordered = sorted(records, key=lambda record: record.as_of_date)
    by_date: dict[date, FeatureRecord] = {}
    for record in ordered:
        if not isinstance(record.value, Decimal):
            raise TypeError("percentile inputs must be Decimal values")
        if not record.value.is_finite():
            raise ValueError("percentile inputs must be finite")
        if record.as_of_date in by_date:
            raise ValueError(f"duplicate percentile date: {record.as_of_date}")
        by_date[record.as_of_date] = record

    targets = sorted(set(as_of_dates if as_of_dates is not None else by_date))
    active_records: deque[FeatureRecord] = deque()
    active_values: list[Decimal] = []
    next_record = 0
    percentiles: dict[date, Decimal] = {}

    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        for as_of in targets:
            while (
                next_record < len(ordered) and ordered[next_record].as_of_date <= as_of
            ):
                record = ordered[next_record]
                active_records.append(record)
                insort(active_values, record.value)
                next_record += 1

            first_date = as_of - timedelta(days=PERCENTILE_WINDOW_DAYS - 1)
            while active_records and active_records[0].as_of_date < first_date:
                expired = active_records.popleft()
                position = bisect_left(active_values, expired.value)
                if (
                    position >= len(active_values)
                    or active_values[position] != expired.value
                ):
                    raise RuntimeError("percentile window state is inconsistent")
                active_values.pop(position)

            current = by_date.get(as_of)
            if current is None or len(active_values) < MIN_PERCENTILE_OBSERVATIONS:
                continue
            count_less = bisect_left(active_values, current.value)
            count_equal = bisect_right(active_values, current.value) - count_less
            rank = (
                (Decimal(count_less) + MIDRANK_EQUAL_FACTOR * Decimal(count_equal))
                / Decimal(len(active_values))
                * PERCENTILE_SCALE
            )
            if direction == "lower_is_better":
                rank = PERCENTILE_SCALE - rank
            percentiles[as_of] = rank.quantize(
                PERCENTILE_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            )

    return percentiles


def _component_records(
    chain: str,
    by_feature: Mapping[str, Mapping[date, FeatureRecord]],
    feature: str,
    source_metric: str,
    source: str,
) -> list[FeatureRecord]:
    registered = get_feature_input(chain, source_metric, source)
    if registered is None or registered.role != "score":
        return []
    return [
        record
        for record in by_feature.get(feature, {}).values()
        if record.source_metric == source_metric and record.source == source
    ]


def _confidence_label(coverage: Decimal) -> str:
    if coverage >= HIGH_CONFIDENCE_COVERAGE:
        return CONFIDENCE_HIGH
    if coverage >= MEDIUM_CONFIDENCE_COVERAGE:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


def _score_for_date(
    chain: str,
    as_of: date,
    by_feature: Mapping[str, Mapping[date, FeatureRecord]],
    percentiles: Mapping[tuple[str, str], Mapping[date, Decimal]],
) -> ScoreValue:
    components: list[ComponentValue] = []
    for spec in COMPONENTS:
        if chain not in spec.chains:
            continue
        record = by_feature.get(spec.feature, {}).get(as_of)
        percentile = percentiles.get((spec.feature, spec.direction), {}).get(as_of)
        if (
            record is None
            or percentile is None
            or record.source_metric != spec.source_metric
            or record.source != spec.source
        ):
            continue
        components.append(
            ComponentValue(
                feature=spec.feature,
                value=record.value,
                percentile=percentile,
                weight=spec.weight,
                direction=spec.direction,
                derived_label=spec.derived_label,
            )
        )

    component_by_feature = {component.feature: component for component in components}
    pillar_values: list[PillarValue] = []
    available_pillars: list[tuple[int, Decimal]] = []
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        for pillar in PILLARS:
            pillar_components = [
                (component_by_feature[spec.feature], spec)
                for spec in COMPONENTS
                if chain in spec.chains
                and spec.pillar == pillar.name
                and spec.feature in component_by_feature
            ]
            weight_used = sum(spec.weight for _, spec in pillar_components)
            if weight_used == 0:
                pillar_values.append(PillarValue(pillar.name, None, 0, False))
                continue
            pillar_score = sum(
                (
                    component.percentile * Decimal(spec.weight)
                    for component, spec in pillar_components
                ),
                Decimal(0),
            ) / Decimal(weight_used)
            pillar_score = _quantize(pillar_score, PILLAR_QUANTUM)
            pillar_values.append(
                PillarValue(pillar.name, pillar_score, weight_used, True)
            )
            available_pillars.append((pillar.weight, pillar_score))

        nominal_component_weight = sum(
            spec.weight for spec in COMPONENTS if chain in spec.chains
        )
        available_weight = sum(component.weight for component in components)
        coverage = _quantize(
            Decimal(available_weight) / WEIGHT_DENOMINATOR,
            COVERAGE_QUANTUM,
        )
        score: Decimal | None = None
        if coverage >= NO_SCORE_COVERAGE and available_pillars:
            pillar_weight = sum(weight for weight, _ in available_pillars)
            score = _quantize(
                sum(
                    (value * Decimal(weight) for weight, value in available_pillars),
                    Decimal(0),
                )
                / Decimal(pillar_weight),
                SCORE_QUANTUM,
            )
    if available_weight > nominal_component_weight:
        raise RuntimeError("available component weight exceeds registry maximum")

    return ScoreValue(
        chain=chain,
        as_of_date=as_of,
        score=score,
        coverage=coverage,
        confidence_label=_confidence_label(coverage),
        pillars=tuple(pillar_values),
        components=tuple(components),
    )


def _raw_regime(
    drawdown: Decimal | None,
    price_vs_sma200: Decimal | None,
    ret_90d: Decimal | None,
) -> str:
    if drawdown is not None and drawdown <= STRESS_DRAWDOWN_THRESHOLD:
        return REGIME_STRESS
    if price_vs_sma200 is not None and ret_90d is not None:
        if price_vs_sma200 > 0 and ret_90d > 0:
            return REGIME_UPTREND
        if price_vs_sma200 < 0 and ret_90d < 0:
            return REGIME_DOWNTREND
    return REGIME_RANGE


def _volatility_state(percentile: Decimal | None) -> str | None:
    if percentile is None:
        return None
    if percentile >= HIGH_VOLATILITY_STATE_THRESHOLD:
        return VOL_STATE_HIGH
    if percentile <= LOW_VOLATILITY_STATE_THRESHOLD:
        return VOL_STATE_LOW
    return VOL_STATE_NORMAL


def _regime_values(
    chain: str,
    by_feature: Mapping[str, Mapping[date, FeatureRecord]],
    volatility_percentiles: Mapping[date, Decimal],
) -> tuple[RegimeValue, ...]:
    classifier_features = ("drawdown_365d", "price_vs_sma200", "ret_90d")
    dates = sorted(
        {
            as_of
            for feature in classifier_features
            for as_of in by_feature.get(feature, {})
        }
    )
    raw_values: list[tuple[date, str]] = []
    for as_of in dates:
        drawdown = by_feature.get("drawdown_365d", {}).get(as_of)
        price_vs_sma = by_feature.get("price_vs_sma200", {}).get(as_of)
        return_90d = by_feature.get("ret_90d", {}).get(as_of)
        raw_values.append(
            (
                as_of,
                _raw_regime(
                    drawdown.value if drawdown is not None else None,
                    price_vs_sma.value if price_vs_sma is not None else None,
                    return_90d.value if return_90d is not None else None,
                ),
            )
        )

    results: list[RegimeValue] = []
    reported: str | None = None
    pending: str | None = None
    pending_days = 0
    days_in_regime = 0
    previous_date: date | None = None
    for as_of, raw in raw_values:
        consecutive = previous_date is not None and as_of == previous_date + timedelta(
            days=1
        )
        if reported is None:
            reported = raw
            days_in_regime = 1
            pending = None
            pending_days = 0
        elif not consecutive:
            pending = None
            pending_days = 0
            days_in_regime = 1
            if raw != reported:
                pending = raw
                pending_days = 1
        elif raw == reported:
            pending = None
            pending_days = 0
            days_in_regime += 1
        else:
            if pending == raw:
                pending_days += 1
            else:
                pending = raw
                pending_days = 1
            days_in_regime += 1
            if pending_days >= HYSTERESIS_DAYS:
                reported = raw
                days_in_regime = 1
                pending = None
                pending_days = 0

        results.append(
            RegimeValue(
                chain=chain,
                as_of_date=as_of,
                regime=reported,
                raw_regime=raw,
                vol_state=_volatility_state(volatility_percentiles.get(as_of)),
                days_in_regime=days_in_regime,
            )
        )
        previous_date = as_of
    return tuple(results)


def evaluate_risk_flags(
    chain: str,
    as_of: date,
    feature_values: Mapping[str, Decimal],
    percentiles: Mapping[str, Decimal],
    coverage: Decimal,
) -> tuple[RiskFlagValue, ...]:
    flags: list[RiskFlagValue] = []
    _validate_component_registry(chain)
    for spec in RISK_FLAGS:
        if chain not in spec.chains:
            continue
        value: Decimal | None
        if spec.value_kind == "coverage":
            value = coverage
        elif spec.value_kind == "percentile":
            if spec.feature is None:
                continue
            value = percentiles.get(spec.feature)
        else:
            if (
                spec.feature is None
                or spec.source_metric is None
                or spec.source is None
            ):
                continue
            registered = get_feature_input(chain, spec.source_metric, spec.source)
            if registered is None or registered.role != "score":
                continue
            value = feature_values.get(spec.feature)
        if value is None:
            continue

        matched = (
            value < spec.threshold
            if spec.comparison == "lt"
            else value <= spec.threshold
            if spec.comparison == "lte"
            else value >= spec.threshold
        )
        if not matched:
            continue
        severity = spec.severity
        if (
            spec.high_severity_threshold is not None
            and value <= spec.high_severity_threshold
        ):
            severity = SEVERITY_HIGH
        flags.append(
            RiskFlagValue(
                chain=chain,
                as_of_date=as_of,
                flag=spec.flag,
                severity=severity,
                value=_quantize(value, VALUE_QUANTUM),
                threshold=_quantize(spec.threshold, VALUE_QUANTUM),
            )
        )
    return tuple(flags)


def compute_analytics(
    chain: str,
    records: Iterable[FeatureRecord],
) -> AnalyticsOutput:
    by_feature = _validate_records(chain, records)
    _validate_component_registry(chain)

    score_features = {spec.feature for spec in COMPONENTS if chain in spec.chains}
    score_dates = sorted(
        {as_of for feature in score_features for as_of in by_feature.get(feature, {})}
    )
    risk_dates = sorted(
        set(score_dates)
        | {
            as_of
            for spec in RISK_FLAGS
            if chain in spec.chains and spec.feature is not None
            for as_of in by_feature.get(spec.feature, {})
        }
    )

    percentile_inputs: dict[
        tuple[str, str],
        tuple[str, str],
    ] = {}
    for component_spec in COMPONENTS:
        if chain in component_spec.chains:
            percentile_inputs[(component_spec.feature, component_spec.direction)] = (
                component_spec.source_metric,
                component_spec.source,
            )
    for risk_spec in RISK_FLAGS:
        if (
            chain in risk_spec.chains
            and risk_spec.value_kind == "percentile"
            and risk_spec.feature is not None
            and risk_spec.source_metric is not None
            and risk_spec.source is not None
        ):
            percentile_inputs[(risk_spec.feature, "higher_is_better")] = (
                risk_spec.source_metric,
                risk_spec.source,
            )
    percentile_inputs[("realized_vol_90d", "higher_is_better")] = REGIME_FEATURES[
        "realized_vol_90d"
    ]

    percentiles: dict[tuple[str, str], dict[date, Decimal]] = {}
    for (feature, direction), input_spec in sorted(percentile_inputs.items()):
        source_records = _component_records(
            chain,
            by_feature,
            feature,
            input_spec[0],
            input_spec[1],
        )
        if not source_records:
            continue
        percentiles[(feature, direction)] = point_in_time_percentiles(
            source_records,
            as_of_dates=set(score_dates) | set(risk_dates),
            direction=direction,
        )

    scores: list[ScoreValue] = []
    for as_of in score_dates:
        scores.append(_score_for_date(chain, as_of, by_feature, percentiles))

    vol90_percentiles = percentiles.get(
        ("realized_vol_90d", "higher_is_better"),
        {},
    )
    regime_records = {
        feature: {
            record.as_of_date: record
            for record in _component_records(
                chain,
                by_feature,
                feature,
                source_metric,
                source,
            )
        }
        for feature, (source_metric, source) in REGIME_FEATURES.items()
    }
    regimes = _regime_values(chain, regime_records, vol90_percentiles)

    risk_flags: list[RiskFlagValue] = []
    score_by_date = {score.as_of_date: score for score in scores}
    for as_of in risk_dates:
        coverage = score_by_date.get(as_of)
        if coverage is None:
            coverage = _score_for_date(chain, as_of, by_feature, percentiles)
        feature_values: dict[str, Decimal] = {}
        for feature, (source_metric, source) in RISK_FEATURES.items():
            record = by_feature.get(feature, {}).get(as_of)
            registered = get_feature_input(chain, source_metric, source)
            if (
                record is not None
                and registered is not None
                and registered.role == "score"
                and record.source_metric == source_metric
                and record.source == source
            ):
                feature_values[feature] = record.value
        percentile_values = {
            feature: values[as_of]
            for (feature, direction), values in percentiles.items()
            if direction == "higher_is_better" and as_of in values
        }
        risk_flags.extend(
            evaluate_risk_flags(
                chain,
                as_of,
                feature_values,
                percentile_values,
                coverage.coverage,
            )
        )

    return AnalyticsOutput(
        scores=tuple(scores),
        regimes=regimes,
        risk_flags=tuple(risk_flags),
    )


def maximum_coverage(chain: str) -> Decimal:
    if chain not in CHAINS:
        raise ValueError(f"unsupported chain: {chain}")
    return _quantize(
        Decimal(sum(spec.weight for spec in COMPONENTS if chain in spec.chains))
        / WEIGHT_DENOMINATOR,
        COVERAGE_QUANTUM,
    )


def score_components_are_registry_approved(chain: str) -> bool:
    try:
        _validate_component_registry(chain)
    except ValueError:
        return False
    return True
