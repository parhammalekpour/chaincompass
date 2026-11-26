from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db.session import SessionFactory, engine
from app.ml.dataset import (
    DATA_CUTOFF,
    PROTOCOL_COMMIT,
    Dataset,
    Fold,
    build_dataset,
    load_chain_inputs,
    make_folds,
    positive_counts,
)
from app.ml.label_audit import reference_labels
from app.ml.leakage import (
    passed_canary_check,
    passed_permutation_check,
    run_leakage_checks,
)
from app.ml.study import evaluate_study1, render_results_markdown
from app.ml.vol_state import load_vol_state_lookup

EXPECTED_DATASET_HASH = (
    "dc409eef38e6f425cc919bd9c52ad53cf5885bee42ce5a016f32eec64a7c8cbe"
)
AMENDMENT_HASHES = {
    "a1_commit_hash": "fc5cb5cba62c6b7e2eef7ff1bcec1ea0c8267a8f",
    "a2_commit_hash": "dbce7faaa8c97c5d258d6f89f30369d648f634a5",
    "a3_commit_hash": "675909da38fc6a60b322cc432348a6cf50d76655",
}


async def _load_dataset() -> Dataset:
    async with SessionFactory() as session:
        chain_inputs = await load_chain_inputs(session)
    await engine.dispose()
    return build_dataset(chain_inputs, DATA_CUTOFF)


def _print_dataset(dataset: Dataset, folds: tuple[Fold, ...]) -> None:
    print(f"cutoff={DATA_CUTOFF.isoformat()}")
    print(f"protocol_commit={PROTOCOL_COMMIT}")
    print(f"dataset_sha256={dataset.sha256}")
    counts = positive_counts(dataset.rows)
    for chain, (row_count, positives) in counts.items():
        print(f"chain={chain} eligible_rows={row_count} positives={positives}")
    print(f"fold_count={len(folds)}")
    for fold in folds:
        test_rows = [dataset.rows[index] for index in fold.test_indices]
        actual_end = fold.test_end_exclusive - timedelta(days=1)
        positives = sum(row.y for row in test_rows)
        print(
            f"fold={fold.index} test_dates={fold.test_start}..{actual_end} "
            f"rows={len(test_rows)} positives={positives} "
            f"train_rows={len(fold.train_indices)} "
            f"train_cutoff={fold.train_cutoff}"
        )
        for chain in counts:
            selected = [row for row in test_rows if row.chain == chain]
            print(
                f"  chain={chain} test_rows={len(selected)} "
                f"positives={sum(row.y for row in selected)}"
            )


async def _run_build_dataset() -> int:
    dataset = await _load_dataset()
    folds = make_folds(dataset.rows)
    _print_dataset(dataset, folds)
    return 0


async def _run_leakage_check() -> int:
    dataset = await _load_dataset()
    folds = make_folds(dataset.rows)
    results = run_leakage_checks(dataset, folds)
    permutation_pass = passed_permutation_check(results)
    canary_pass = passed_canary_check(results)
    print(
        "permutation_auc "
        f"mean={results.permutation_mean:.6f} "
        f"min={results.permutation_minimum:.6f} "
        f"max={results.permutation_maximum:.6f} "
        f"result={'PASS' if permutation_pass else 'FAIL'}"
    )
    print(
        f"leaky_canary_auc={results.canary_auc:.6f} "
        f"result={'PASS' if canary_pass else 'FAIL'}"
    )
    return 0 if permutation_pass and canary_pass else 1


async def _run_label_audit() -> int:
    async with SessionFactory() as session:
        chain_inputs = await load_chain_inputs(session)
    await engine.dispose()
    dataset = build_dataset(chain_inputs, DATA_CUTOFF)
    folds = make_folds(dataset.rows)

    reference_by_chain = {
        chain: reference_labels(inputs.dates, inputs.closes, DATA_CUTOFF)
        for chain, inputs in chain_inputs.items()
    }
    y_mismatches = 0
    numeric_mismatches = {
        "rv30": 0,
        "rv30_fwd": 0,
        "q80": 0,
    }
    max_absolute_differences = {
        "rv30": 0.0,
        "rv30_fwd": 0.0,
        "q80": 0.0,
    }
    mismatch_examples: list[str] = []
    numeric_fields = ("rv30", "rv30_fwd", "q80")

    for row in dataset.rows:
        reference = reference_by_chain[row.chain].get(row.obs_date)
        mismatches: list[str] = []
        if reference is None:
            y_mismatches += 1
            for field in numeric_fields:
                numeric_mismatches[field] += 1
            mismatches.append("reference row missing")
        else:
            if reference.y != row.y:
                y_mismatches += 1
                mismatches.append(f"y={reference.y}/{row.y}")
            for field in numeric_fields:
                expected = getattr(reference, field)
                actual = getattr(row, field)
                absolute_difference = abs(expected - actual)
                max_absolute_differences[field] = max(
                    max_absolute_differences[field],
                    absolute_difference,
                )
                scale = max(abs(expected), abs(actual))
                relative_difference = absolute_difference / scale if scale else 0.0
                if relative_difference > 1e-9:
                    numeric_mismatches[field] += 1
                    mismatches.append(
                        f"{field}_relative_difference={relative_difference:.3e}"
                    )
        if mismatches and len(mismatch_examples) < 5:
            mismatch_examples.append(
                f"chain={row.chain} date={row.obs_date} "
                f"reference_y={reference.y if reference else 'missing'} "
                f"dataset_y={row.y} details={'; '.join(mismatches)}"
            )

    print(f"cutoff={DATA_CUTOFF.isoformat()}")
    print(f"dataset_sha256={dataset.sha256}")
    print(f"rows_compared={len(dataset.rows)}")
    print(f"y_mismatches={y_mismatches}")
    for field in numeric_fields:
        print(
            f"{field}_mismatches={numeric_mismatches[field]} "
            f"{field}_max_absolute_difference="
            f"{max_absolute_differences[field]:.12e}"
        )

    annual_counts: defaultdict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    for row in dataset.rows:
        counts = annual_counts[(row.chain, row.obs_date.year)]
        counts[0] += 1
        counts[1] += row.y
    print("annual_counts chain year rows positives positive_rate")
    for chain in positive_counts(dataset.rows):
        years = sorted(
            year for current_chain, year in annual_counts if current_chain == chain
        )
        for year in years:
            rows, positives = annual_counts[(chain, year)]
            print(
                f"annual chain={chain} year={year} rows={rows} "
                f"positives={positives} positive_rate={positives / rows:.6f}"
            )

    test_indices = sorted({index for fold in folds for index in fold.test_indices})
    test_rows = [dataset.rows[index] for index in test_indices]
    test_positive_total = 0
    test_row_total = 0
    for chain in positive_counts(dataset.rows):
        chain_rows = [row for row in test_rows if row.chain == chain]
        positives = sum(row.y for row in chain_rows)
        test_row_total += len(chain_rows)
        test_positive_total += positives
        rate = positives / len(chain_rows) if chain_rows else 0.0
        print(
            f"test_union chain={chain} rows={len(chain_rows)} "
            f"positives={positives} positive_rate={rate:.6f}"
        )
    pooled_rate = test_positive_total / test_row_total if test_row_total else 0.0
    print(
        f"test_union pooled rows={test_row_total} "
        f"positives={test_positive_total} positive_rate={pooled_rate:.6f}"
    )

    if mismatch_examples:
        print("first_mismatch_examples:")
        for example in mismatch_examples:
            print(example)
    total_mismatches = y_mismatches + sum(numeric_mismatches.values())
    print(f"result={'PASS' if total_mismatches == 0 else 'FAIL'}")
    return 0 if total_mismatches == 0 else 1


async def _run_study1() -> int:
    repository_root = Path(__file__).resolve().parents[3]
    status_result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    worktree_status = status_result.stdout.strip()
    code_commit_hash = commit_result.stdout.strip()

    async with SessionFactory() as session:
        chain_inputs = await load_chain_inputs(session)
        dataset = build_dataset(chain_inputs, DATA_CUTOFF)
        folds = make_folds(dataset.rows)
        vol_states = await load_vol_state_lookup(session, dataset.rows)
    await engine.dispose()

    print(f"code_commit_hash={code_commit_hash}")
    print(f"worktree_status={'dirty' if worktree_status else 'clean'}")
    if worktree_status:
        print(f"worktree_changes={worktree_status}")
    print(f"dataset_hash={dataset.sha256}")
    print(f"expected_dataset_hash={EXPECTED_DATASET_HASH}")
    print(f"protocol_commit_hash={PROTOCOL_COMMIT}")
    print(f"a1_commit_hash={AMENDMENT_HASHES['a1_commit_hash']}")
    print(f"a2_commit_hash={AMENDMENT_HASHES['a2_commit_hash']}")
    print(f"a3_commit_hash={AMENDMENT_HASHES['a3_commit_hash']}")
    print(f"vol_state_distinct_values={','.join(vol_states.distinct_values)}")
    print(f"vol_state_missing_eligible_rows={vol_states.missing_eligible_rows}")
    if worktree_status or dataset.sha256 != EXPECTED_DATASET_HASH:
        print("study1=STOP (dirty worktree or dataset hash mismatch)")
        return 1

    results_path = repository_root / "docs" / "research" / "ml_study1_results.json"
    markdown_path = repository_root / "docs" / "ML_RESULTS.md"
    if results_path.exists() or markdown_path.exists():
        print("study1=STOP (result file already exists; refusing to overwrite)")
        return 1

    leakage_results = run_leakage_checks(dataset, folds)
    permutation_pass = passed_permutation_check(leakage_results)
    canary_pass = passed_canary_check(leakage_results)
    print(
        "study1_leakage_permutation_auc="
        f"{leakage_results.permutation_mean:.6f} "
        f"result={'PASS' if permutation_pass else 'FAIL'}"
    )
    print(
        f"study1_leaky_canary_auc={leakage_results.canary_auc:.6f} "
        f"result={'PASS' if canary_pass else 'FAIL'}"
    )
    if not permutation_pass or not canary_pass:
        print("study1=STOP (leakage checks failed)")
        return 1

    results = evaluate_study1(
        dataset,
        folds,
        vol_states,
        code_commit_hash=code_commit_hash,
        amendment_hashes=AMENDMENT_HASHES,
        leakage_results=leakage_results,
    )
    results["metadata"]["generated_at_utc"] = datetime.now(UTC).isoformat()
    json_output = json.dumps(
        results,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    markdown_output = render_results_markdown(results)

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json_output + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_output, encoding="utf-8")
    print(markdown_output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build-dataset")
    subparsers.add_parser("leakage-check")
    subparsers.add_parser("label-audit")
    subparsers.add_parser("study1")
    args = parser.parse_args()
    if args.command == "build-dataset":
        return asyncio.run(_run_build_dataset())
    if args.command == "leakage-check":
        return asyncio.run(_run_leakage_check())
    if args.command == "label-audit":
        return asyncio.run(_run_label_audit())
    if args.command == "study1":
        return asyncio.run(_run_study1())
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
