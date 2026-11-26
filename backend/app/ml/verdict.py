from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Informativeness:
    pooled_positive_count: int
    informative_chains: tuple[str, ...]
    pooled_pass: bool
    chain_count_pass: bool
    informative: bool


@dataclass(frozen=True)
class PairCriteria:
    ci_upper_by_length: Mapping[int, float]
    relative_improvement: float | None
    improved_chain_count: int
    informative_chain_count: int
    lower_brier_first_half: bool
    lower_brier_second_half: bool


@dataclass(frozen=True)
class PairAssessment:
    confidence_intervals_pass: bool
    relative_improvement_pass: bool
    chain_criterion_pass: bool
    halves_criterion_pass: bool
    tier_a: bool


@dataclass(frozen=True)
class Verdict:
    label: str
    tier_a_models: tuple[str, ...]
    tier_b_m1: bool
    informative: bool


def assess_informativeness(
    pooled_positive_count: int,
    positive_counts_by_chain: Mapping[str, int],
) -> Informativeness:
    informative_chains = tuple(
        chain
        for chain, positives in positive_counts_by_chain.items()
        if positives >= 20
    )
    pooled_pass = pooled_positive_count >= 100
    chain_count_pass = len(informative_chains) >= 2
    return Informativeness(
        pooled_positive_count=pooled_positive_count,
        informative_chains=informative_chains,
        pooled_pass=pooled_pass,
        chain_count_pass=chain_count_pass,
        informative=pooled_pass and chain_count_pass,
    )


def assess_pair(criteria: PairCriteria) -> PairAssessment:
    required = math.ceil(0.75 * criteria.informative_chain_count)
    confidence_intervals_pass = all(
        criteria.ci_upper_by_length.get(length, math.inf) < 0 for length in (30, 60)
    )
    relative_improvement_pass = (
        criteria.relative_improvement is not None
        and criteria.relative_improvement >= 0.02
    )
    chain_criterion_pass = criteria.improved_chain_count >= required
    halves_criterion_pass = (
        criteria.lower_brier_first_half and criteria.lower_brier_second_half
    )
    return PairAssessment(
        confidence_intervals_pass=confidence_intervals_pass,
        relative_improvement_pass=relative_improvement_pass,
        chain_criterion_pass=chain_criterion_pass,
        halves_criterion_pass=halves_criterion_pass,
        tier_a=(
            confidence_intervals_pass
            and relative_improvement_pass
            and chain_criterion_pass
            and halves_criterion_pass
        ),
    )


def decide_verdict(
    informativeness: Informativeness,
    tier_a_by_model: Mapping[str, bool],
    m1_calibration_slope: float | None,
    m1_ece: float,
) -> Verdict:
    tier_a_models = tuple(model for model, passed in tier_a_by_model.items() if passed)
    m1_tier_a = bool(tier_a_by_model.get("M1", False))
    tier_b_m1 = (
        informativeness.informative
        and m1_tier_a
        and m1_calibration_slope is not None
        and 0.8 <= m1_calibration_slope <= 1.2
        and m1_ece <= 0.05
    )
    if not informativeness.informative:
        label = "NOT INFORMATIVE"
    elif tier_b_m1:
        label = "TIER B MET"
    elif tier_a_models:
        label = "TIER A MET"
    else:
        label = "NEGATIVE"
    return Verdict(
        label=label,
        tier_a_models=tier_a_models,
        tier_b_m1=tier_b_m1,
        informative=informativeness.informative,
    )
