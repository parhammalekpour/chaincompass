from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta

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
from app.ml.leakage import (
    passed_canary_check,
    passed_permutation_check,
    run_leakage_checks,
)


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build-dataset")
    subparsers.add_parser("leakage-check")
    args = parser.parse_args()
    if args.command == "build-dataset":
        return asyncio.run(_run_build_dataset())
    if args.command == "leakage-check":
        return asyncio.run(_run_leakage_check())
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
