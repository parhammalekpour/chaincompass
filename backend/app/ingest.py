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
from sqlalchemy import delete, func, select
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
LEGACY_BNB_COINMETRICS_METRICS = {
    "market_cap_usd",
    "active_addresses",
    "tx_count",
}


def legacy_bnb_coinmetrics_reason(chain_code: str, metric_code: str) -> str | None:
    if chain_code == "bnb" and metric_code in LEGACY_BNB_COINMETRICS_METRICS:
        return "legacy BNB asset series ended 2019-04-22; not BNB Chain"
    return None


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
                    discontinued_reason = (
                        legacy_bnb_coinmetrics_reason(chain.code, metric)
                        if provider_name == "coinmetrics"
                        else None
                    )
                    if discontinued_reason is not None:
                        await service.record_discontinued(
                            chain.code,
                            metric,
                            discontinued_reason,
                        )
                        continue
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


async def purge_observations(
    session: AsyncSession,
    *,
    provider_name: str,
    chains: list[str],
    confirmed: bool,
) -> int:
    if provider_name != "coinmetrics" or chains != ["bnb"]:
        print("Purge is restricted to --provider coinmetrics --chains bnb")
        return 2

    source_code = CoinMetricsProvider.source_code
    result = await session.scalar(
        select(func.count())
        .select_from(Observation)
        .where(
            Observation.chain_code == "bnb",
            Observation.source_code == source_code,
        )
    )
    count = int(result or 0)
    print(
        f"Purge plan: {count} observations for chain=bnb "
        f"source={source_code}; coverage will be marked discontinued."
    )
    if not confirmed:
        print("No rows deleted. Re-run with --yes to confirm.")
        return 2

    started_at = datetime.now(UTC)
    run = IngestionRun(
        id=uuid4(),
        job="purge",
        provider=provider_name,
        started_at=started_at,
        status="running",
    )
    session.add(run)
    await session.flush()
    delete_result = await session.execute(
        delete(Observation)
        .where(
            Observation.chain_code == "bnb",
            Observation.source_code == source_code,
        )
        .returning(Observation.obs_date)
    )
    deleted = len(delete_result.all())
    reason = "legacy BNB asset series ended 2019-04-22; not BNB Chain"
    for metric in sorted(LEGACY_BNB_COINMETRICS_METRICS):
        coverage = await session.get(
            SeriesCoverage,
            ("bnb", metric, source_code),
        )
        if coverage is None:
            coverage = SeriesCoverage(
                chain_code="bnb",
                metric_code=metric,
                source_code=source_code,
            )
            session.add(coverage)
        coverage.first_date = None
        coverage.last_date = None
        coverage.points = 0
        coverage.missing_days = 0
        coverage.status = "discontinued"
        coverage.last_error = reason

    run.status = "ok"
    run.finished_at = datetime.now(UTC)
    run.error = (f"purged_observations={deleted}; chain=bnb; source={source_code}")[
        :300
    ]
    await session.commit()
    print(f"Deleted {deleted} observations.")
    return 0


async def run_purge(
    *,
    provider_name: str,
    chains: list[str],
    confirmed: bool,
) -> int:
    async with SessionFactory() as session:
        return await purge_observations(
            session,
            provider_name=provider_name,
            chains=chains,
            confirmed=confirmed,
        )


def format_status(rows: list[SeriesCoverage]) -> str:
    lines = [
        "chain | metric | source | kind | first | last | points | missing | "
        "status | reason",
        "-" * 120,
    ]
    for row in rows:
        kind = (
            "derived"
            if row.metric_code == "fees_usd" and row.source_code == "blockchain_info"
            else "observed"
        )
        lines.append(
            f"{row.chain_code} | {row.metric_code} | {row.source_code} | {kind} | "
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
    tuple[date, date] | None,
]:
    gaps = gap_ranges([row.obs_date for row in series])
    zero_metrics = {
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
    leading_zero_rows: list[Observation] = []
    for row in series:
        if row.value != 0:
            break
        leading_zero_rows.append(row)
    zero_rows = [
        row
        for row in series
        if row.metric_code in zero_metrics
        and row.value == 0
        and row not in leading_zero_rows
    ]
    relative_jump_metrics = {
        "price_close_usd",
        "market_cap_usd",
        "tvl_usd",
        "stablecoin_supply_usd",
    }
    median_metrics = {"volume_usd", "tx_count", "active_addresses"}
    jumps: list[tuple[Observation, Observation, Decimal]] = []
    for index, current in enumerate(series):
        if current.metric_code in relative_jump_metrics:
            if index == 0:
                continue
            previous = series[index - 1]
            if (current.obs_date - previous.obs_date).days != 1:
                continue
            if previous.value <= 0:
                continue
            change = current.value / previous.value - Decimal(1)
            if abs(change) > jump_threshold:
                jumps.append((previous, current, change))
        elif current.metric_code in median_metrics:
            trailing = [
                row
                for row in series[:index]
                if 0 < (current.obs_date - row.obs_date).days <= 30
            ]
            if not trailing:
                continue
            values = sorted(row.value for row in trailing)
            middle = len(values) // 2
            median = (
                values[middle]
                if len(values) % 2
                else (values[middle - 1] + values[middle]) / Decimal(2)
            )
            if median <= 0:
                continue
            if current.value > median * 10 or current.value < median / 10:
                change = current.value / median - Decimal(1)
                jumps.append((trailing[-1], current, change))
    prelaunch_zeros = (
        (leading_zero_rows[0].obs_date, leading_zero_rows[-1].obs_date)
        if leading_zero_rows
        else None
    )
    return gaps, zero_rows, jumps, prelaunch_zeros


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
    daily_move_count = 0
    median_outlier_count = 0
    jump_series_count = 0
    for (chain, metric, source), series in sorted(grouped.items()):
        gaps, zero_rows, jumps, prelaunch_zeros = analyze_series(series, jump_threshold)
        for start, end in gaps:
            gap_count += 1
            length = (end - start).days + 1
            print(f"gap {chain}/{metric}/{source}: {start}..{end} ({length} days)")
        zero_count += len(zero_rows)
        if prelaunch_zeros is not None:
            start, end = prelaunch_zeros
            print(
                f"pre-launch zeros {chain}/{metric}/{source}: "
                f"{start}..{end} (informational)"
            )
        if zero_rows:
            spans = ", ".join(
                f"{start}..{end}"
                for start, end in contiguous_ranges([row.obs_date for row in zero_rows])
            )
            print(
                f"suspicious zeros {chain}/{metric}/{source}: "
                f"{len(zero_rows)} dates={spans}"
            )
        if jumps:
            if metric in {
                "price_close_usd",
                "market_cap_usd",
                "tvl_usd",
                "stablecoin_supply_usd",
            }:
                daily_move_count += len(jumps)
            else:
                median_outlier_count += len(jumps)
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
            alert_rule = (
                f"daily moves over {jump_threshold}"
                if metric
                in {
                    "price_close_usd",
                    "market_cap_usd",
                    "tvl_usd",
                    "stablecoin_supply_usd",
                }
                else "trailing median outliers (>10x or <0.1x)"
            )
            print(
                f"alerts {chain}/{metric}/{source}: {len(jumps)} "
                f"{alert_rule}; largest={examples}"
            )
    print(
        f"check summary: series={len(grouped)} gap_ranges={gap_count} "
        f"suspicious_zero_rows={zero_count} "
        f"daily_moves_over_{jump_threshold}={daily_move_count} "
        f"trailing_median_outliers={median_outlier_count} "
        f"series_with_alerts={jump_series_count}"
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
    purge = sub.add_parser("purge")
    purge.add_argument("--provider", choices=("coinmetrics",), required=True)
    purge.add_argument("--chains", required=True)
    purge.add_argument("--yes", action="store_true")
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
    elif args.command == "purge":
        purge_chains = [item.strip() for item in args.chains.split(",") if item.strip()]
        code = asyncio.run(
            run_purge(
                provider_name=args.provider,
                chains=purge_chains,
                confirmed=args.yes,
            )
        )
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
