from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.ml.baselines import BASELINE_NAMES, predict_baselines
from app.ml.bootstrap import (
    BootstrapInterval,
    moving_block_samples,
    paired_brier_intervals,
)
from app.ml.dataset import Dataset, Fold
from app.ml.leakage import LeakageResults
from app.ml.metrics import MetricSummary, compute_metrics, macro_average
from app.ml.models import MODEL_NAMES, fit_predict_fold
from app.ml.verdict import (
    PairCriteria,
    assess_informativeness,
    assess_pair,
    decide_verdict,
)
from app.ml.vol_state import VolStateLookup

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
LabelArray = NDArray[np.int8]
MODEL_AND_BASELINE_NAMES = BASELINE_NAMES + MODEL_NAMES
COMPARATOR_NAMES = ("B1", "B2", "B3")
BLOCK_LENGTHS = (30, 60)
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 12345
TOTAL_ALPHA = 0.05 / 3.0


def _metric_dict(summary: MetricSummary) -> dict[str, Any]:
    return {
        "rows": summary.count,
        "positives": summary.positive_count,
        "brier": summary.brier,
        "log_loss": summary.log_loss,
        "auc": summary.auc,
        "ece": summary.ece,
        "calibration_slope": summary.calibration_slope,
        "calibration_intercept": summary.calibration_intercept,
        "calibration_status": summary.calibration_status,
        "calibration_convergence_warnings": (summary.calibration_convergence_warnings),
        "reliability": list(summary.reliability),
    }


def _compute_group_metrics(
    labels: LabelArray,
    probabilities: Mapping[str, FloatArray],
    mask: NDArray[np.bool_],
) -> dict[str, MetricSummary]:
    return {
        model_name: compute_metrics(labels[mask], probabilities[model_name][mask])
        for model_name in MODEL_AND_BASELINE_NAMES
    }


def _interval_dict(interval: BootstrapInterval) -> dict[str, float | int]:
    return {
        "lower": interval.lower,
        "upper": interval.upper,
        "mean_difference": interval.mean_difference,
        "resamples": interval.resamples,
    }


def evaluate_study1(
    dataset: Dataset,
    folds: Sequence[Fold],
    vol_states: VolStateLookup,
    *,
    code_commit_hash: str,
    amendment_hashes: Mapping[str, str],
    leakage_results: LeakageResults,
) -> dict[str, Any]:
    rows = dataset.rows
    if not rows or not folds:
        raise ValueError("Study 1 requires dataset rows and walk-forward folds")

    evaluation_indices = sorted(
        {index for fold in folds for index in fold.test_indices},
        key=lambda index: (rows[index].obs_date, rows[index].chain),
    )
    test_rows = [rows[index] for index in evaluation_indices]
    if not test_rows:
        raise ValueError("walk-forward folds contain no test rows")
    labels = np.asarray([row.y for row in test_rows], dtype=np.int8)
    chain_counts = {
        chain: sum(row.y for row in test_rows if row.chain == chain)
        for chain in sorted({row.chain for row in test_rows})
    }
    informativeness = assess_informativeness(
        int(np.sum(labels)),
        chain_counts,
    )

    all_probabilities = {
        name: np.full(len(rows), np.nan, dtype=np.float64)
        for name in MODEL_AND_BASELINE_NAMES
    }
    convergence_warnings = {name: 0 for name in MODEL_NAMES}
    single_class_folds: dict[str, list[int]] = {name: [] for name in MODEL_NAMES}
    fold_diagnostics: list[dict[str, Any]] = []

    for fold in folds:
        train_rows = [rows[index] for index in fold.train_indices]
        fold_test_rows = [rows[index] for index in fold.test_indices]
        if not train_rows or not fold_test_rows:
            raise ValueError(f"fold {fold.index} has an empty train or test set")
        train_states = [
            vol_states.by_row.get((row.chain, row.obs_date), "missing")
            for row in train_rows
        ]
        test_states = [
            vol_states.by_row.get((row.chain, row.obs_date), "missing")
            for row in fold_test_rows
        ]
        baseline_probabilities = predict_baselines(
            train_rows,
            fold_test_rows,
            train_states,
            test_states,
        )
        fold_test_indices = np.asarray(fold.test_indices, dtype=np.intp)
        for name, probabilities in baseline_probabilities.items():
            all_probabilities[name][fold_test_indices] = probabilities

        train_features = np.asarray(
            [row.features for row in train_rows],
            dtype=np.float64,
        )
        test_features = np.asarray(
            [row.features for row in fold_test_rows],
            dtype=np.float64,
        )
        train_labels = np.asarray([row.y for row in train_rows], dtype=np.int8)
        train_positive_count = int(np.sum(train_labels))
        single_class = np.unique(train_labels).size == 1
        for model_name in MODEL_NAMES:
            prediction = fit_predict_fold(
                model_name,
                train_features,
                train_labels,
                test_features,
            )
            all_probabilities[model_name][fold_test_indices] = prediction.probabilities
            convergence_warnings[model_name] += prediction.convergence_warnings
            if prediction.used_single_class_fallback:
                single_class_folds[model_name].append(fold.index)

        fold_diagnostics.append(
            {
                "fold": fold.index,
                "test_start": fold.test_start.isoformat(),
                "test_end_exclusive": fold.test_end_exclusive.isoformat(),
                "training_rows": len(train_rows),
                "training_positives": train_positive_count,
                "test_rows": len(fold_test_rows),
                "test_positives": sum(row.y for row in fold_test_rows),
                "single_class_training": single_class,
                "single_class_fallback_models": [
                    name for name in MODEL_NAMES if single_class
                ],
            }
        )

    test_probabilities = {
        name: all_probabilities[name][evaluation_indices]
        for name in MODEL_AND_BASELINE_NAMES
    }
    if any(not np.all(np.isfinite(values)) for values in test_probabilities.values()):
        raise ValueError("a study model or baseline lacks finite test probabilities")

    test_dates = tuple(sorted({row.obs_date for row in test_rows}))
    date_positions = {obs_date: index for index, obs_date in enumerate(test_dates)}
    date_ids = np.asarray(
        [date_positions[row.obs_date] for row in test_rows],
        dtype=np.int64,
    )
    pooled_mask = np.ones(len(test_rows), dtype=np.bool_)
    pooled_metrics = _compute_group_metrics(labels, test_probabilities, pooled_mask)

    per_chain_metrics: dict[str, dict[str, MetricSummary]] = {}
    for chain in chain_counts:
        mask = np.asarray(
            [row.chain == chain for row in test_rows],
            dtype=np.bool_,
        )
        per_chain_metrics[chain] = _compute_group_metrics(
            labels,
            test_probabilities,
            mask,
        )
    macro_metric_dicts: dict[str, dict[str, Any]] = {}
    for name in MODEL_AND_BASELINE_NAMES:
        summaries = tuple(
            per_chain_metrics[chain][name]
            for chain in informativeness.informative_chains
        )
        if summaries:
            macro_metric_dicts[name] = _metric_dict(macro_average(summaries))
        else:
            macro_metric_dicts[name] = {
                "rows": 0,
                "positives": 0,
                "brier": None,
                "log_loss": None,
                "auc": None,
                "ece": None,
                "calibration_slope": None,
                "calibration_intercept": None,
                "calibration_status": "undefined: no informative chains",
                "calibration_convergence_warnings": 0,
                "reliability": [],
            }

    first_test_start = min(fold.test_start for fold in folds)
    last_test_end = max(fold.test_end_exclusive for fold in folds)
    half_days = (last_test_end - first_test_start).days // 2
    midpoint = first_test_start + timedelta(days=half_days)
    first_half_mask = np.asarray(
        [row.obs_date < midpoint for row in test_rows],
        dtype=np.bool_,
    )
    second_half_mask = np.asarray(
        [row.obs_date >= midpoint for row in test_rows],
        dtype=np.bool_,
    )
    half_metrics = {
        "first": _compute_group_metrics(labels, test_probabilities, first_half_mask),
        "second": _compute_group_metrics(labels, test_probabilities, second_half_mask),
    }

    years = sorted({row.obs_date.year for row in test_rows})
    yearly_metrics: dict[int, dict[str, MetricSummary]] = {}
    for year in years:
        mask = np.asarray(
            [row.obs_date.year == year for row in test_rows],
            dtype=np.bool_,
        )
        yearly_metrics[year] = _compute_group_metrics(
            labels,
            test_probabilities,
            mask,
        )

    pairs = tuple(
        (model_name, comparator_name)
        for model_name in MODEL_NAMES
        for comparator_name in COMPARATOR_NAMES
    )
    bootstrap_results: dict[str, dict[tuple[str, str], BootstrapInterval]] = {}
    for block_length in BLOCK_LENGTHS:
        samples = moving_block_samples(
            len(test_dates),
            block_length,
            resamples=N_BOOTSTRAP,
            seed=BOOTSTRAP_SEED,
        )
        bootstrap_results[str(block_length)] = paired_brier_intervals(
            labels,
            date_ids,
            test_probabilities,
            pairs,
            samples,
            total_alpha=TOTAL_ALPHA,
        )

    criteria_table: dict[str, dict[str, dict[str, Any]]] = {}
    tier_a_by_model: dict[str, bool] = {}
    required_chain_count = math.ceil(0.75 * len(informativeness.informative_chains))
    for model_name in MODEL_NAMES:
        criteria_table[model_name] = {}
        pair_results = []
        for comparator_name in COMPARATOR_NAMES:
            model_brier = pooled_metrics[model_name].brier
            comparator_brier = pooled_metrics[comparator_name].brier
            relative_improvement = (
                (comparator_brier - model_brier) / comparator_brier
                if comparator_brier > 0
                else None
            )
            improved_chains = sum(
                per_chain_metrics[chain][model_name].brier
                < per_chain_metrics[chain][comparator_name].brier
                for chain in informativeness.informative_chains
            )
            interval_uppers = {
                int(length): bootstrap_results[length][
                    (model_name, comparator_name)
                ].upper
                for length in (str(value) for value in BLOCK_LENGTHS)
            }
            assessment = assess_pair(
                PairCriteria(
                    ci_upper_by_length=interval_uppers,
                    relative_improvement=relative_improvement,
                    improved_chain_count=improved_chains,
                    informative_chain_count=len(informativeness.informative_chains),
                    lower_brier_first_half=(
                        half_metrics["first"][model_name].brier
                        < half_metrics["first"][comparator_name].brier
                    ),
                    lower_brier_second_half=(
                        half_metrics["second"][model_name].brier
                        < half_metrics["second"][comparator_name].brier
                    ),
                )
            )
            pair_results.append(assessment.tier_a)
            criteria_table[model_name][comparator_name] = {
                "ci_upper_by_block_length": interval_uppers,
                "confidence_intervals_pass": (assessment.confidence_intervals_pass),
                "relative_improvement": relative_improvement,
                "relative_improvement_pass": (assessment.relative_improvement_pass),
                "improved_informative_chains": improved_chains,
                "required_informative_chains": required_chain_count,
                "chain_criterion_pass": assessment.chain_criterion_pass,
                "lower_brier_first_half": (
                    half_metrics["first"][model_name].brier
                    < half_metrics["first"][comparator_name].brier
                ),
                "lower_brier_second_half": (
                    half_metrics["second"][model_name].brier
                    < half_metrics["second"][comparator_name].brier
                ),
                "halves_criterion_pass": assessment.halves_criterion_pass,
                "tier_a": assessment.tier_a,
            }
        tier_a_by_model[model_name] = all(pair_results)

    m1_calibration = pooled_metrics["M1"]
    verdict = decide_verdict(
        informativeness,
        tier_a_by_model,
        m1_calibration.calibration_slope,
        m1_calibration.ece,
    )

    metric_groups: dict[str, Any] = {
        "pooled": {
            name: _metric_dict(summary) for name, summary in pooled_metrics.items()
        },
        "per_chain": {
            chain: {name: _metric_dict(summary) for name, summary in summaries.items()}
            for chain, summaries in per_chain_metrics.items()
        },
        "macro_informative_chains": macro_metric_dicts,
        "halves": {
            half: {name: _metric_dict(summary) for name, summary in summaries.items()}
            for half, summaries in half_metrics.items()
        },
        "calendar_years": {
            str(year): {
                name: _metric_dict(summary) for name, summary in summaries.items()
            }
            for year, summaries in yearly_metrics.items()
        },
    }
    bootstrap_json = {
        length: {
            "block_length": int(length),
            "resamples": N_BOOTSTRAP,
            "seed": BOOTSTRAP_SEED,
            "intervals": {
                f"{model}_vs_{comparator}": _interval_dict(interval)
                for (model, comparator), interval in intervals.items()
            },
        }
        for length, intervals in bootstrap_results.items()
    }
    return {
        "metadata": {
            **dict(amendment_hashes),
            "code_commit_hash": code_commit_hash,
            "dataset_hash": dataset.sha256,
            "protocol_commit_hash": ("08da59e507fedddf227f9e80dfd66b34d859ef70"),
        },
        "dataset": {
            "eligible_rows": len(rows),
            "positive_labels": sum(row.y for row in rows),
            "test_rows": len(test_rows),
            "test_positive_labels": int(np.sum(labels)),
            "test_dates": len(test_dates),
        },
        "vol_state": {
            "distinct_values": list(vol_states.distinct_values),
            "missing_eligible_rows": vol_states.missing_eligible_rows,
            "missing_test_rows": sum(
                vol_states.by_row.get((row.chain, row.obs_date), "missing") == "missing"
                for row in test_rows
            ),
        },
        "leakage_checks": {
            "permutation_auc_mean": leakage_results.permutation_mean,
            "permutation_auc_minimum": leakage_results.permutation_minimum,
            "permutation_auc_maximum": leakage_results.permutation_maximum,
            "permutation_pass": 0.45 <= leakage_results.permutation_mean <= 0.55,
            "canary_auc": leakage_results.canary_auc,
            "canary_pass": leakage_results.canary_auc >= 0.99,
        },
        "informativeness": {
            "pooled_positive_count": informativeness.pooled_positive_count,
            "pooled_pass": informativeness.pooled_pass,
            "positive_counts_by_chain": chain_counts,
            "informative_chains": list(informativeness.informative_chains),
            "informative_chain_count": len(informativeness.informative_chains),
            "chain_count_pass": informativeness.chain_count_pass,
            "informative": informativeness.informative,
        },
        "metrics": metric_groups,
        "bootstrap": bootstrap_json,
        "criteria": criteria_table,
        "verdict": {
            "label": verdict.label,
            "tier_a_models": list(verdict.tier_a_models),
            "tier_b_m1": verdict.tier_b_m1,
        },
        "model_diagnostics": {
            name: {
                "single_class_folds": single_class_folds[name],
                "single_class_fold_count": len(single_class_folds[name]),
                "convergence_warnings": convergence_warnings[name],
                "pooled_calibration_convergence_warnings": (
                    pooled_metrics[name].calibration_convergence_warnings
                ),
            }
            for name in MODEL_NAMES
        },
        "fold_diagnostics": fold_diagnostics,
        "chronological_halves": {
            "midpoint": midpoint.isoformat(),
            "first_test_start": first_test_start.isoformat(),
            "last_test_end_exclusive": last_test_end.isoformat(),
        },
    }


def _format(value: object, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _metric_table(
    title: str,
    metric_groups: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    lines = [
        f"### {title}",
        "",
        "| Series | Rows | Positives | Brier | Log loss | AUC | ECE | Slope | "
        "Intercept |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in MODEL_AND_BASELINE_NAMES:
        summary = metric_groups[name]
        lines.append(
            f"| {name} | {_format(summary['rows'], 0)} "
            f"| {_format(summary['positives'], 0)} "
            f"| {_format(summary['brier'])} "
            f"| {_format(summary['log_loss'])} "
            f"| {_format(summary['auc'])} "
            f"| {_format(summary['ece'])} "
            f"| {_format(summary['calibration_slope'])} "
            f"| {_format(summary['calibration_intercept'])} |"
        )
    lines.append("")
    return lines


def render_results_markdown(results: Mapping[str, Any]) -> str:
    metadata = results["metadata"]
    dataset = results["dataset"]
    info = results["informativeness"]
    metrics = results["metrics"]
    lines = [
        "# Study 1: Historical Volatility-Risk",
        "",
        "Experimental historical volatility-risk study; not a forecast and not advice.",
        "",
        "## Run record",
        "",
        f"- Code commit: `{metadata['code_commit_hash']}`",
        f"- Dataset SHA-256: `{metadata['dataset_hash']}`",
        f"- Protocol commit: `{metadata['protocol_commit_hash']}`",
        f"- A1 commit: `{metadata['a1_commit_hash']}`",
        f"- A2 commit: `{metadata['a2_commit_hash']}`",
        f"- A3 commit: `{metadata['a3_commit_hash']}`",
        f"- Eligible rows / positives: {dataset['eligible_rows']} / "
        f"{dataset['positive_labels']}",
        f"- Test-union rows / positives / unique dates: {dataset['test_rows']} / "
        f"{dataset['test_positive_labels']} / {dataset['test_dates']}",
        "",
        "## Informativeness",
        "",
        f"- Pooled-positive criterion: {'PASS' if info['pooled_pass'] else 'FAIL'} "
        f"({info['pooled_positive_count']} positives; minimum 100).",
        f"- Informative chains: {', '.join(info['informative_chains']) or 'none'} "
        f"({info['informative_chain_count']}; minimum 2).",
        f"- Overall: {'INFORMATIVE' if info['informative'] else 'NOT INFORMATIVE'}.",
        f"- Chain positive counts: {info['positive_counts_by_chain']}.",
        "",
        "## Stored `vol_state`",
        "",
        f"- Distinct stored values on eligible rows: "
        f"{', '.join(results['vol_state']['distinct_values']) or 'none'}.",
        f"- Eligible rows without a stored value: "
        f"{results['vol_state']['missing_eligible_rows']}; test rows without "
        f"a stored value: {results['vol_state']['missing_test_rows']}.",
        "",
        "## Leakage checks",
        "",
        f"- Label permutation mean AUC: "
        f"{_format(results['leakage_checks']['permutation_auc_mean'])} "
        f"({_format(results['leakage_checks']['permutation_auc_minimum'])}–"
        f"{_format(results['leakage_checks']['permutation_auc_maximum'])}); "
        f"{'PASS' if results['leakage_checks']['permutation_pass'] else 'FAIL'}.",
        f"- Leaky canary AUC: {_format(results['leakage_checks']['canary_auc'])}; "
        f"{'PASS' if results['leakage_checks']['canary_pass'] else 'FAIL'}.",
        "",
        "## Pooled metrics",
        "",
    ]
    lines.extend(_metric_table("All test blocks", metrics["pooled"]))
    lines.extend(
        [
            "## Per-chain metrics and informative-chain macro-average",
            "",
            "| Chain / group | Series | Rows | Positives | Brier | Log loss | "
            "AUC | ECE | Slope | Intercept |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    chain_groups = list(metrics["per_chain"].items()) + [
        ("macro informative chains", metrics["macro_informative_chains"])
    ]
    for chain, group in chain_groups:
        for name in MODEL_AND_BASELINE_NAMES:
            summary = group[name]
            lines.append(
                f"| {chain} | {name} | {_format(summary['rows'], 0)} "
                f"| {_format(summary['positives'], 0)} "
                f"| {_format(summary['brier'])} "
                f"| {_format(summary['log_loss'])} "
                f"| {_format(summary['auc'])} "
                f"| {_format(summary['ece'])} "
                f"| {_format(summary['calibration_slope'])} "
                f"| {_format(summary['calibration_intercept'])} |"
            )
    lines.extend(["", "## Chronological halves", ""])
    for half, group in metrics["halves"].items():
        lines.extend(_metric_table(half, group))
    lines.extend(["## Calendar years (supplementary)", ""])
    for year, group in metrics["calendar_years"].items():
        lines.extend(_metric_table(str(year), group))
    lines.extend(["## Pooled reliability tables", ""])
    for name in MODEL_AND_BASELINE_NAMES:
        lines.extend(
            [
                f"### {name}",
                "",
                "| Bin | Rows | Mean p | Observed rate | Absolute gap |",
                "|---:|---:|---:|---:|---:|",
            ]
        )
        for reliability_bin in metrics["pooled"][name]["reliability"]:
            lines.append(
                f"| {_format(reliability_bin['bin'], 0)} "
                f"| {_format(reliability_bin['count'], 0)} "
                f"| {_format(reliability_bin['mean_probability'])} "
                f"| {_format(reliability_bin['observed_rate'])} "
                f"| {_format(reliability_bin['absolute_gap'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Paired moving-block bootstrap",
            "",
            "| Model | Comparator | Block days | Lower | Upper | Mean difference | "
            "Resamples |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for length, block_result in results["bootstrap"].items():
        for pair, interval in block_result["intervals"].items():
            model_name, comparator_name = pair.split("_vs_", maxsplit=1)
            lines.append(
                f"| {model_name} | {comparator_name} | {length} "
                f"| {_format(interval['lower'])} "
                f"| {_format(interval['upper'])} "
                f"| {_format(interval['mean_difference'])} "
                f"| {_format(interval['resamples'], 0)} |"
            )
    lines.extend(
        [
            "",
            "## Tier A criteria",
            "",
            "| Model | Comparator | CI both lengths | Relative improvement | "
            "Informative chains | Both halves | Tier A |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for model_name, comparisons in results["criteria"].items():
        for comparator_name, item in comparisons.items():
            lines.append(
                f"| {model_name} | {comparator_name} "
                f"| {_format(item['confidence_intervals_pass'])} "
                f"| {_format(item['relative_improvement'])} "
                f"| {item['improved_informative_chains']}/"
                f"{item['required_informative_chains']} "
                f"({_format(item['chain_criterion_pass'])}) "
                f"| {_format(item['halves_criterion_pass'])} "
                f"| {_format(item['tier_a'])} |"
            )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            f"**{results['verdict']['label']}**",
            "",
            f"Models meeting Tier A: "
            f"{', '.join(results['verdict']['tier_a_models']) or 'none'}.",
            f"M1 Tier B: {'MET' if results['verdict']['tier_b_m1'] else 'not met'}.",
            "",
            "## Fold and convergence diagnostics",
            "",
            "| Model | Single-class folds | Convergence warnings | Pooled "
            "calibration warnings |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, diagnostic in results["model_diagnostics"].items():
        lines.append(
            f"| {name} | {diagnostic['single_class_fold_count']} "
            f"| {diagnostic['convergence_warnings']} "
            f"| {diagnostic['pooled_calibration_convergence_warnings']} |"
        )
    lines.extend(["", "### Fold-level training class counts", ""])
    lines.extend(
        [
            "| Fold | Train rows | Train positives | Test rows | Test positives | "
            "Single class |",
            "|---:|---:|---:|---:|---:|---|",
        ]
    )
    for diagnostic in results["fold_diagnostics"]:
        lines.append(
            f"| {diagnostic['fold']} | {diagnostic['training_rows']} "
            f"| {diagnostic['training_positives']} "
            f"| {diagnostic['test_rows']} | {diagnostic['test_positives']} "
            f"| {_format(diagnostic['single_class_training'])} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "Overlapping labels reduce effective sample size to about `n/30`; "
            "chains are correlated; there is one historical path; "
            "hyperparameters are fixed; the HAR baseline is an adaptation; "
            "thresholds are a priori; and results use one data snapshot at "
            "course scale. An LLM review is not an expert review.",
            "",
            "The measured positive rate is 543/9,325 (5.82%) overall and "
            "138/7,216 (1.91%) over the test union, far below the nominal 20%. "
            "The expanding Q80 is anchored by the very high volatility of "
            "2017-2021; whether that explains the lower rates is a hypothesis "
            "and remains unverified.",
            "",
        ]
    )
    return "\n".join(lines)
