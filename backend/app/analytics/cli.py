from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.analytics.repository import (
    ComputeMode,
    compute_and_store,
    feature_status,
)

logger = logging.getLogger("app.analytics")
CHAINS = ("btc", "eth", "sol", "bnb")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChainCompass feature analytics")
    commands = parser.add_subparsers(dest="command", required=True)
    compute = commands.add_parser("compute-features")
    mode = compute.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backfill", action="store_true")
    mode.add_argument("--update", action="store_true")
    compute.add_argument("--chain", choices=CHAINS)
    status = commands.add_parser("feature-status")
    status.add_argument("--chain", choices=CHAINS)
    return parser.parse_args(argv)


async def execute_command(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.command == "compute-features":
        mode: ComputeMode = "backfill" if args.backfill else "update"
        summary = await compute_and_store(mode=mode, chain=args.chain)
        print(
            f"features: mode={mode} rows_upserted={summary.rows_upserted} "
            f"rows_deleted={summary.rows_deleted}"
        )
        for chain, count in summary.rows_by_chain.items():
            print(f"{chain}: {count} feature rows")
        return 0

    rows = await feature_status(chain=args.chain)
    print("chain | feature | first_date | last_date | rows")
    print("-" * 72)
    for chain, feature, first, last, count in rows:
        print(f"{chain} | {feature} | {first or '-'} | {last or '-'} | {count}")
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        code = asyncio.run(execute_command(sys.argv[1:]))
    except Exception as exc:
        logger.error(
            "analytics_command_failed error_type=%s",
            type(exc).__name__,
        )
        print(
            f"Analytics command failed ({type(exc).__name__}).",
            file=sys.stderr,
        )
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
