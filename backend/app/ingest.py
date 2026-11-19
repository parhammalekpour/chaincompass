from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db.models.ingestion import (
    Chain,
    IngestionRun,
    SeriesCoverage,
)
from app.db.session import SessionFactory
from app.ingestion.binance import BinanceKlinesProvider
from app.ingestion.http import ProviderStopped
from app.ingestion.provider import ChainContext
from app.ingestion.seed import seed_reference_data
from app.ingestion.service import IngestionService


async def seed() -> int:
    async with SessionFactory() as session:
        await seed_reference_data(session)
    print("Seeded chains, data sources, and metric definitions.")
    return 0


async def run_binance(
    *,
    job: str,
    chains: list[str] | None,
    since: date | None,
) -> int:
    async with SessionFactory() as session:
        chain_rows = await session.scalars(
            select(Chain).where(
                Chain.enabled.is_(True),
            )
        )
        selected = [
            chain for chain in chain_rows if chains is None or chain.code in chains
        ]
        provider = BinanceKlinesProvider()
        run = IngestionRun(
            id=uuid4(),
            job=job,
            provider="binance",
            started_at=datetime.now(UTC),
            status="running",
        )
        session.add(run)
        await session.commit()
        total_upserted = 0
        total_rejected = 0
        failure: str | None = None
        for chain in selected:
            context = ChainContext(code=chain.code, symbol=chain.native_symbol)
            service = IngestionService(
                session,
                provider,
                provider_code="binance",
                source_code="binance",
            )
            for metric in ("price_close_usd", "volume_usd"):
                try:
                    last = await service.last_stored_date(chain.code, metric)
                    if since is not None:
                        start = since
                    elif last is not None:
                        start = last - timedelta(days=3)
                    else:
                        earliest = {
                            "btc": date(2017, 8, 17),
                            "eth": date(2017, 8, 17),
                            "sol": date(2020, 8, 11),
                            "bnb": date(2017, 11, 6),
                        }
                        start = earliest[chain.code]
                    end = datetime.now(UTC).date() - timedelta(days=1)
                    points = await provider.fetch(context, metric, start, end)
                    upserted, rejected = await service.upsert_points(
                        context,
                        metric,
                        points,
                        today=datetime.now(UTC).date(),
                    )
                    total_upserted += upserted
                    total_rejected += rejected
                    await service.recompute_coverage(chain.code, metric)
                except ProviderStopped as exc:
                    failure = str(exc)[:300]
                    break
                except Exception as exc:
                    failure = f"{type(exc).__name__}: {str(exc)[:200]}"[:300]
                    break
            if failure:
                break
        await provider.close()
        run.status = "ok" if failure is None else "partial"
        run.finished_at = datetime.now(UTC)
        run.rows_upserted = total_upserted
        run.rows_rejected = total_rejected
        run.error = failure
        await session.commit()
    print(
        f"Binance {job}: upserted={total_upserted} "
        f"rejected={total_rejected} status={run.status}"
    )
    return 0 if failure is None else 1


async def status() -> int:
    async with SessionFactory() as session:
        rows = (
            (
                await session.execute(
                    select(SeriesCoverage).order_by(
                        SeriesCoverage.chain_code,
                        SeriesCoverage.metric_code,
                        SeriesCoverage.source_code,
                    )
                )
            )
            .scalars()
            .all()
        )
    print("chain | metric | source | first | last | points | missing | status")
    print("-" * 90)
    for row in rows:
        print(
            f"{row.chain_code} | {row.metric_code} | {row.source_code} | "
            f"{row.first_date or '-'} | {row.last_date or '-'} | "
            f"{row.points} | {row.missing_days} | {row.status}"
        )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChainCompass data ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--provider", required=True)
    backfill.add_argument("--chains")
    backfill.add_argument("--since")
    update = sub.add_parser("update")
    update.add_argument("--provider", required=True)
    sub.add_parser("status")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    if args.command == "seed":
        code = asyncio.run(seed())
    elif args.command == "status":
        code = asyncio.run(status())
    elif args.command in {"backfill", "update"}:
        if args.provider != "binance":
            print(f"Unsupported provider: {args.provider}", file=sys.stderr)
            code = 1
        else:
            chain_filter = (
                [item.strip() for item in args.chains.split(",") if item.strip()]
                if getattr(args, "chains", None)
                else None
            )
            since = None
            if getattr(args, "since", None):
                try:
                    since = date.fromisoformat(args.since)
                except ValueError:
                    print("Invalid --since date", file=sys.stderr)
                    code = 1
                    return
            code = asyncio.run(
                run_binance(
                    job=args.command,
                    chains=chain_filter,
                    since=since,
                )
            )
    else:
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
