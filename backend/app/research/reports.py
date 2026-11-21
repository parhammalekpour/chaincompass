from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def json_report(data: dict[str, object]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )


def _number(value: object, digits: int = 4) -> str:
    if value is None:
        return "—"
    if not isinstance(value, (int, float)):
        return str(value)
    return f"{value:.{digits}f}"


def _metric_text(metric: dict[str, Any], include_interval: bool) -> str:
    share = _number(metric.get("share"), 3)
    if not include_interval or metric.get("wilson_95") is None:
        return share
    lower, upper = metric["wilson_95"]
    return f"{share} [{_number(lower, 3)}, {_number(upper, 3)}]"


def scenario_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Study S — historical scenario calibration",
        "",
        "Origins use the pre-registered point-in-time protocol. All-origin",
        "outcomes overlap and are descriptive; Wilson intervals are shown only",
        "for the non-overlapping calendar-grid sample. B1 is comparison-only.",
        "",
        "| Chain | H | Era | Method | All n | "
        "All: <p10 / <p50 / >p90 / hit | Non-overlap n | "
        "Non-overlap: <p10 / <p50 / >p90 / hit (Wilson 95%) | v1 label |",
        "|---|---:|---|---|---:|---|---:|---|---|",
    ]
    for cell in data["cells"]:
        for method in ("scenarios-v1", "B1"):
            for era in ("pooled", "E1", "E2"):
                period = cell["methods"][method][era]
                all_sample = period["all_origins"]
                inferential = period["non_overlapping"]
                keys = ("below_p10", "below_p50", "above_p90", "p10_p90_hit")
                all_values = " / ".join(
                    _metric_text(all_sample["metrics"][key], False) for key in keys
                )
                inferential_values = " / ".join(
                    _metric_text(inferential["metrics"][key], True) for key in keys
                )
                label = (
                    cell["scenarios_v1_labels"][era]
                    if method == "scenarios-v1"
                    else "comparison only"
                )
                lines.append(
                    f"| {cell['chain']} | {cell['horizon_days']} | {era} | {method} "
                    f"| {all_sample['n']} | {all_values} | "
                    f"{inferential['n_independent_origins']} | {inferential_values} "
                    f"| {label} |"
                )
    lines.extend(
        [
            "",
            "## Scenarios-v1 sample groups",
            "",
            "Groups are classified by the engine's independent-window count.",
            "",
            "| Chain | H | Era | Sample group | All n | "
            "All: <p10 / <p50 / >p90 / hit | Non-overlap n | "
            "Non-overlap: <p10 / <p50 / >p90 / hit (Wilson 95%) |",
            "|---|---:|---|---|---:|---|---:|---|",
        ]
    )
    for cell in data["cells"]:
        for era in ("pooled", "E1", "E2"):
            groups = cell["methods"]["scenarios-v1"][era]["sample_groups"]
            for group_name in ("low_sample", "normal_sample"):
                samples = groups[group_name]
                all_sample = samples["all_origins"]
                inferential = samples["non_overlapping"]
                keys = ("below_p10", "below_p50", "above_p90", "p10_p90_hit")
                all_values = " / ".join(
                    _metric_text(all_sample["metrics"][key], False) for key in keys
                )
                inferential_values = " / ".join(
                    _metric_text(inferential["metrics"][key], True) for key in keys
                )
                lines.append(
                    f"| {cell['chain']} | {cell['horizon_days']} | {era} "
                    f"| {group_name} | {all_sample['n']} | {all_values} | "
                    f"{inferential['n_independent_origins']} | "
                    f"{inferential_values} |"
                )
    lines.extend(
        [
            "",
            "## Paired non-overlapping pinball loss",
            "",
            "The same-origin sample is used for both methods; smaller values are",
            "descriptive only. Each entry is mean loss (paired n).",
            "",
            "| Chain | H | Era | Method | p10 | p50 | p90 |",
            "|---|---:|---|---|---:|---:|---:|",
        ]
    )
    for cell in data["cells"]:
        for era in ("pooled", "E1", "E2"):
            for method in ("scenarios-v1", "B1"):
                loss = cell["paired_non_overlapping_pinball"][era][method]
                losses = " | ".join(
                    (
                        f"{_number(loss[q], 6)} (n={loss['n']})"
                        if loss[q] is not None
                        else f"— (n={loss['n']})"
                    )
                    for q in ("p10", "p50", "p90")
                )
                lines.append(
                    f"| {cell['chain']} | {cell['horizon_days']} | {era} "
                    f"| {method} | {losses} |"
                )
    lines.append("")
    return "\n".join(lines)


def health_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Study H — Health Score and forward-return association",
        "",
        "The samples are spaced by their forward-return horizon. Correlation",
        "intervals use the pre-registered approximate Fisher-z calculation;",
        "terciles use expanding past-only score cutoffs.",
        "",
        "| Chain | H | n / n independent | Spearman rho | Approx. 95% CI | Reading | "
        "Low tercile n / mean / median | Middle n / mean / median | "
        "High n / mean / median | Tercile exclusions |",
        "|---|---:|---:|---:|---|---|---|---|---|---:|",
    ]
    for chain in data["chains"]:
        for horizon in chain["horizons"]:
            interval = horizon["fisher_z_approx_95"]
            interval_text = (
                f"[{_number(interval[0], 3)}, {_number(interval[1], 3)}]"
                if interval
                else "unavailable"
            )
            reading = horizon["association_not_distinguishable_from_zero"]
            reading_text = (
                "association not distinguishable from zero"
                if reading is True
                else "not distinguishable"
                if reading is None
                else "interval excludes zero"
            )
            tercile_cells = []
            for name in ("low", "middle", "high"):
                group = horizon["terciles"][name]
                tercile_cells.append(
                    f"{group['n']} / {_number(group['mean_forward_return'], 4)} / "
                    f"{_number(group['median_forward_return'], 4)}"
                )
            lines.append(
                f"| {chain['chain']} | {horizon['horizon_days']} | "
                f"{horizon['n']} / {horizon['n_independent']} | "
                f"{_number(horizon['spearman_rho'], 4)} "
                f"| {interval_text} | {reading_text} | "
                f"{' | '.join(tercile_cells)} | "
                f"{horizon['tercile_excluded_insufficient_past_scores']} |"
            )
    lines.extend(
        [
            "",
            "Association is descriptive, not predictive. Score inputs include",
            "price-derived market-condition components, so any association may",
            "reflect momentum or mean-reversion rather than on-chain information.",
            "",
        ]
    )
    return "\n".join(lines)


def regime_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Study R — regime v1 versus comparison state machine v2",
        "",
        "V2 is comparison-only and is not adopted. Durations include the final",
        "right-censored run; switches do not count initial state assignment.",
        "",
        "| Chain | Version | Switches | Regime episodes | Mean duration days | "
        "Median duration days | Episodes <10 days | Stored v1 matches | Mismatches |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for chain in data["chains"]:
        stored = chain["stored_v1_comparison"]
        for version in ("v1", "v2"):
            metrics = chain["versions"][version]
            match = str(stored["matches"]) if version == "v1" else "—"
            mismatch_count = stored["mismatch_count"] if version == "v1" else "—"
            lines.append(
                f"| {chain['chain']} | {version} | {metrics['regime_switches']} | "
                f"{metrics['regime_episode_count']} | "
                f"{_number(metrics['mean_regime_duration_days'], 2)} | "
                f"{_number(metrics['median_regime_duration_days'], 2)} | "
                f"{metrics['episodes_under_10_days']} | {match} | {mismatch_count} |"
            )
    lines.extend(
        [
            "",
            "## Raw-stress episode lags",
            "",
            "Lags are calendar days. A missing detection is reported as not",
            "observed; a missing exit after detected stress is right-censored.",
            "",
            "| Chain | Version | Raw stress episode | Detection lag days | "
            "Exit lag days | Detection | Exit censoring |",
            "|---|---|---|---:|---:|---|---|",
        ]
    )
    for chain in data["chains"]:
        for version in ("v1", "v2"):
            for episode in chain["versions"][version]["raw_stress_episodes"]:
                detection = (
                    "not observed" if episode["detection_not_observed"] else "observed"
                )
                lines.append(
                    f"| {chain['chain']} | {version} | "
                    f"{episode['raw_stress_start']}–{episode['raw_stress_end']} | "
                    f"{_number(episode['detection_lag_days'], 0)} | "
                    f"{_number(episode['exit_lag_days'], 0)} | {detection} | "
                    f"{episode['exit_right_censored']} |"
                )
    lines.append("")
    return "\n".join(lines)


RENDERERS = {
    "S": scenario_markdown,
    "H": health_markdown,
    "R": regime_markdown,
}


def write_study_report(
    docs_directory: Path,
    study: str,
    data: dict[str, object],
) -> tuple[Path, Path]:
    research_directory = docs_directory / "research"
    research_directory.mkdir(parents=True, exist_ok=True)
    json_path = research_directory / f"{study}.json"
    markdown_path = research_directory / f"{study}.md"
    json_path.write_text(json_report(data), encoding="utf-8", newline="\n")
    markdown_path.write_text(RENDERERS[study](data), encoding="utf-8", newline="\n")
    return json_path, markdown_path
