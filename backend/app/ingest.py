from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion import (
    Chain,
    IngestionRun,
    Observation,
    SeriesCoverage,
)
from app.db.session import SessionFactory
from app.ingestion.binance import BinanceKlinesProvider
from app.ingestion.btcnet import BtcNetworkProvider, btc_fees_to_usd
from app.ingestion.coinmetrics import CoinMetricsProvider
from app.ingestion.defillama import DefiLlamaProvider
from app.ingestion.http import ProviderStopped
from app.ingestion.provider import ChainContext
from app.ingestion.seed import seed_reference_data
from app.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

type Provider = (
    BinanceKlinesProvider | CoinMetricsProvider | DefiLlamaProvider | BtcNetworkProvider
)

PROVIDER_TYPES: dict[str, type[Provider]] = {
    "binance": BinanceKlinesProvider,
    "coinmetrics": CoinMetricsProvider,
    "defillama": DefiLlamaProvider,
    "btcnet": BtcNetworkProvider,
}
PROVIDER_METRICS: dict[str, tuple[str, ...]] = {
    "binance": ("price_close_usd", "volume_usd"),
    "coinmetrics": ("market_cap_usd", "active_addresses", "tx_count"),
    "defillama": ("tvl_usd", "stablecoin_supply_usd"),
    "btcnet": ("hashrate", "fees_usd"),
}
PROVIDER_CHAINS: dict[str, tuple[str, ...]] = {
    "binance": ("btc", "eth", "sol", "bnb"),
    "coinmetrics": ("btc", "eth", "sol", "bnb"),
    "defillama": ("btc", "eth", "sol", "bnb"),
    "btcnet": ("btc",),
}
DEFAULT_BACKFILL_DATE = date(2017, 1, 1)


async def seed() -> int:
    async with SessionFactory() as session:
        await seed_reference_data(session)
    print("Seeded chains, data sources, and metric definitions.")
    return 0


async def ensure_coverage(
    session: AsyncSession,
    chain_code: str,
    metric_code: str,
    source_code: str,
) -> None:
    key = (chain_code, metric_code, source_code)
    if await session.get(SeriesCoverage, key) is None:
        session.add(
            SeriesCoverage(
                chain_code=chain_code,
                metric_code=metric_code,
                source_code=source_code,
            )
        )
        await session.commit()


async def run_provider(
    *,
    job: str,
    provider_name: str,
    chains: list[str] | None,
    since: date | None,
) -> int:
    provider_class = PROVIDER_TYPES[provider_name]
    provider: Provider = provider_class()
    async with SessionFactory() as session:
        result = await session.scalars(
            select(Chain).where(Chain.enabled.is_(True)).order_by(Chain.code)
        )
        selected = [
            chain
            for chain in result
            if chain.code in PROVIDER_CHAINS[provider_name]
            and (chains is None or chain.code in chains)
        ]
        run = IngestionRun(
            id=uuid4(),
            job=job,
            provider=provider_name,
            started_at=datetime.now(UTC),
            status="running",
        )
        session.add(run)
        await session.commit()
        total_upserted = 0
        total_rejected = 0
        failures: list[str] = []
        stop_provider = False

        try:
            for chain in selected:
                context = ChainContext(code=chain.code, symbol=chain.native_symbol)
                for metric in PROVIDER_METRICS[provider_name]:
                    service = IngestionService(
                        session,
                        provider=provider,
                        provider_code=provider_name,
                        source_code=provider.source_code,
                    )
                    await ensure_coverage(
                        session, chain.code, metric, provider.source_code
                    )
                    if provider_name == "defillama" and chain.code == "btc":
                        await service.record_unavailable(
                            chain.code,
                            metric,
                            "Prior audit verified HTTP 404 for the Bitcoin endpoint; "
                            "no new BTC request was made.",
                        )
                        continue

                    last = await service.last_stored_date(chain.code, metric)
                    start_date = since
                    if start_date is None:
                        start_date = (
                            service.incremental_start(
                                last,
                                getattr(provider, "overlap_days", 3),
                            )
                            or DEFAULT_BACKFILL_DATE
                        )
                    end_date = datetime.now(UTC).date() - timedelta(days=1)
                    try:
                        points = await provider.fetch(
                            context,
                            metric,
                            start_date,
                            end_date,
                        )
                        if provider_name == "btcnet" and metric == "fees_usd":
                            fee_dates = [point.date for point in points]
                            price_rows = (
                                await session.scalars(
                                    select(Observation).where(
                                        Observation.chain_code == "btc",
                                        Observation.metric_code == "price_close_usd",
                                        Observation.source_code == "binance",
                                        Observation.obs_date.in_(fee_dates),
                                    )
                                )
                            ).all()
                            prices = {row.obs_date: row.value for row in price_rows}
                            points, missing_prices = btc_fees_to_usd(points, prices)
                            total_rejected += missing_prices
                            if missing_prices:
                                logger.info(
                                    "Skipped %s BTC fee rows without Binance closes",
                                    missing_prices,
                                )
                        if (
                            provider_name == "btcnet"
                            and metric == "fees_usd"
                            and not points
                        ):
                            await service.record_unavailable(
                                chain.code,
                                metric,
                                "Blockchain.info transaction-fees chart returned "
                                "no daily points with matching Binance BTC closes.",
                            )
                            continue
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
                        message = f"{type(exc).__name__}: {exc}"[:300]
                        await service.record_error(chain.code, metric, message)
                        failures.append(f"{chain.code}/{metric}: {message}")
                        stop_provider = True
                        break
                    except httpx.HTTPStatusError as exc:
                        code = exc.response.status_code
                        message = str(exc)[:300]
                        if not message.startswith("HTTP "):
                            message = f"HTTP {code}: {message}"[:300]
                        if http_error_is_unavailable(code):
                            await service.record_unavailable(
                                chain.code, metric, message
                            )
                        else:
                            await service.record_error(chain.code, metric, message)
                            failures.append(f"{chain.code}/{metric}: {message}")
                    except InvalidOperation as exc:
                        message = f"{type(exc).__name__}: {str(exc)}"[:300]
                        await service.record_error(chain.code, metric, message)
                        failures.append(f"{chain.code}/{metric}: {message}")
                if stop_provider:
                    break
        finally:
            await provider.close()

        run.status = "ok" if not failures else "partial"
        run.finished_at = datetime.now(UTC)
        run.rows_upserted = total_upserted
        run.rows_rejected = total_rejected
        run.error = "; ".join(failures)[:300] or None
        await session.commit()

    print(
        f"{provider_name} {job}: upserted={total_upserted} "
        f"rejected={total_rejected} status={run.status}"
    )
    for failure in failures:
        print(f"  error: {failure}", file=sys.stderr)
    return 0 if not failures else 1


def format_status(rows: list[SeriesCoverage]) -> str:
    lines = [
        "chain | metric | source | first | last | points | missing | status | reason",
        "-" * 120,
    ]
    for row in rows:
        lines.append(
            f"{row.chain_code} | {row.metric_code} | {row.source_code} | "
            f"{row.first_date or '-'} | {row.last_date or '-'} | "
            f"{row.points} | {row.missing_days} | {row.status} | "
            f"{row.last_error or '-'}"
        )
    return "\n".join(lines)


async def status() -> int:
    async with SessionFactory() as session:
        rows = list(
            (
                await session.scalars(
                    select(SeriesCoverage).order_by(
                        SeriesCoverage.chain_code,
                        SeriesCoverage.metric_code,
                        SeriesCoverage.source_code,
                    )
                )
            ).all()
        )
    print(format_status(rows))
    return 0


def http_error_is_unavailable(status_code: int) -> bool:
    return status_code in {403, 404}


def gap_ranges(dates: list[date]) -> list[tuple[date, date]]:
    ordered = sorted(set(dates))
    gaps: list[tuple[date, date]] = []
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if (current - previous).days > 1:
            gaps.append((previous + timedelta(days=1), current - timedelta(days=1)))
    return gaps


def contiguous_ranges(dates: list[date]) -> list[tuple[date, date]]:
    ordered = sorted(set(dates))
    if not ordered:
        return []
    ranges: list[tuple[date, date]] = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        if (current - previous).days > 1:
            ranges.append((start, previous))
            start = current
        previous = current
    ranges.append((start, previous))
    return ranges


def analyze_series(
    series: list[Observation],
    jump_threshold: Decimal,
) -> tuple[
    list[tuple[date, date]],
    list[Observation],
    list[tuple[Observation, Observation, Decimal]],
]:
    gaps = gap_ranges([row.obs_date for row in series])
    zero_rows = [
        row
        for row in series
        if row.metric_code
        in {
            "price_close_usd",
            "volume_usd",
            "market_cap_usd",
            "active_addresses",
            "tx_count",
            "tvl_usd",
            "stablecoin_supply_usd",
            "hashrate",
            "validators",
        }
        and row.value == 0
    ]
    jumps: list[tuple[Observation, Observation, Decimal]] = []
    for previous, current in zip(series, series[1:], strict=False):
        if (current.obs_date - previous.obs_date).days != 1 or previous.value == 0:
            continue
        change = current.value / previous.value - Decimal(1)
        if abs(change) > jump_threshold:
            jumps.append((previous, current, change))
    return gaps, zero_rows, jumps


async def check_data(jump_threshold: Decimal) -> int:
    async with SessionFactory() as session:
        rows = (
            await session.scalars(
                select(Observation).order_by(
                    Observation.chain_code,
                    Observation.metric_code,
                    Observation.source_code,
                    Observation.obs_date,
                )
            )
        ).all()

    grouped: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
    for row in rows:
        grouped[(row.chain_code, row.metric_code, row.source_code)].append(row)

    gap_count = 0
    zero_count = 0
    jump_count = 0
    jump_series_count = 0
    for (chain, metric, source), series in sorted(grouped.items()):
        gaps, zero_rows, jumps = analyze_series(series, jump_threshold)
        for start, end in gaps:
            gap_count += 1
            length = (end - start).days + 1
            print(f"gap {chain}/{metric}/{source}: {start}..{end} ({length} days)")
        zero_count += len(zero_rows)
        if zero_rows:
            spans = ", ".join(
                f"{start}..{end}"
                for start, end in contiguous_ranges([row.obs_date for row in zero_rows])
            )
            print(f"zero {chain}/{metric}/{source}: {len(zero_rows)} dates={spans}")
        if jumps:
            jump_count += len(jumps)
            jump_series_count += 1
            largest_jumps = sorted(
                jumps,
                key=lambda item: abs(item[2]),
                reverse=True,
            )[:3]
            examples = "; ".join(
                f"{previous.obs_date}->{current.obs_date} ({change * 100:.2f}%)"
                for previous, current, change in largest_jumps
            )
            print(
                f"jumps {chain}/{metric}/{source}: {len(jumps)} "
                f"over {jump_threshold}; largest={examples}"
            )
    print(
        f"check summary: series={len(grouped)} gap_ranges={gap_count} "
        f"suspicious_zero_rows={zero_count} "
        f"jumps_over_{jump_threshold}={jump_count} "
        f"series_with_jumps={jump_series_count}"
    )
    return 0


async def run_updates_all() -> int:
    failed = False
    for provider_name in PROVIDER_TYPES:
        try:
            result = await run_provider(
                job="update",
                provider_name=provider_name,
                chains=None,
                since=None,
            )
        except Exception as exc:
            print(
                f"{provider_name} update failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            failed = True
            continue
        failed = failed or result != 0
    return int(failed)


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def parse_jump_threshold(value: str) -> Decimal:
    try:
        threshold = Decimal(value)
    except Exception as exc:
        raise argparse.ArgumentTypeError(
            "jump threshold must be a finite non-negative decimal"
        ) from exc
    if not threshold.is_finite() or threshold < 0:
        raise argparse.ArgumentTypeError(
            "jump threshold must be a finite non-negative decimal"
        )
    return threshold


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChainCompass data ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--provider", choices=PROVIDER_TYPES, required=True)
    backfill.add_argument("--chains")
    backfill.add_argument("--since", type=parse_date)
    update = sub.add_parser("update")
    update_selection = update.add_mutually_exclusive_group(required=True)
    update_selection.add_argument("--provider", choices=PROVIDER_TYPES)
    update_selection.add_argument("--all", action="store_true")
    sub.add_parser("status")
    check = sub.add_parser("check")
    check.add_argument(
        "--jump-threshold",
        type=parse_jump_threshold,
        default=Decimal("0.4"),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    if args.command == "seed":
        code = asyncio.run(seed())
    elif args.command == "status":
        code = asyncio.run(status())
    elif args.command == "check":
        if args.jump_threshold < 0:
            print("--jump-threshold must be non-negative", file=sys.stderr)
            code = 2
        else:
            code = asyncio.run(check_data(args.jump_threshold))
    elif args.command == "backfill":
        selected_chains = (
            [item.strip() for item in args.chains.split(",") if item.strip()]
            if args.chains
            else None
        )
        if selected_chains and not set(selected_chains).issubset(
            {"btc", "eth", "sol", "bnb"}
        ):
            print("Unknown chain in --chains", file=sys.stderr)
            code = 2
        else:
            code = asyncio.run(
                run_provider(
                    job="backfill",
                    provider_name=args.provider,
                    chains=selected_chains,
                    since=args.since,
                )
            )
    elif args.command == "update":
        if args.all:
            code = asyncio.run(run_updates_all())
        else:
            code = asyncio.run(
                run_provider(
                    job="update",
                    provider_name=args.provider,
                    chains=None,
                    since=None,
                )
            )
    else:
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
