from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion import (
    Chain,
    DataSource,
    MetricDefinition,
)

CHAINS = (
    ("btc", "Bitcoin", "BTC", "pow", True),
    ("eth", "Ethereum", "ETH", "pos", True),
    ("sol", "Solana", "SOL", "pos", True),
    ("bnb", "BNB Chain", "BNB", "pos", True),
)

DATA_SOURCES = (
    (
        "binance",
        "Binance data-api",
        "https://data-api.binance.vision/",
        "Public market data; USDT is used as a USD proxy. "
        "Redistribute under Binance terms.",
        False,
    ),
    (
        "coingecko",
        "CoinGecko",
        "https://www.coingecko.com/en/api",
        "Free API attribution required; terms apply.",
        True,
    ),
    (
        "coin_metrics",
        "Coin Metrics Community",
        "https://community-api.coinmetrics.io/",
        "Community API terms; measured availability can differ by asset and metric.",
        True,
    ),
    (
        "defillama",
        "DefiLlama",
        "https://defillama.com/",
        "Public API; source attribution terms should be reviewed.",
        True,
    ),
    (
        "mempool",
        "mempool.space",
        "https://mempool.space/docs/api/rest",
        "Public API; attribution/rate-limit terms should be reviewed.",
        True,
    ),
    (
        "blockchain_info",
        "Blockchain.info",
        "https://www.blockchain.com/explorer/api",
        "API/chart terms apply; attribution requirements require review.",
        True,
    ),
    (
        "public_rpc",
        "Public RPC endpoints",
        "https://ethereum.org/en/developers/docs/nodes-and-clients/",
        "Public infrastructure endpoint terms vary by provider.",
        True,
    ),
)

METRICS = (
    ("price_close_usd", "USD", "1d", "Daily USD close price."),
    ("volume_usd", "USD", "1d", "Daily quote-volume proxy in USD."),
    ("market_cap_usd", "USD", "1d", "Daily market capitalization estimate."),
    ("active_addresses", "addresses", "1d", "Daily active-address count."),
    ("tx_count", "transactions", "1d", "Daily transaction count."),
    ("fees_usd", "USD", "1d", "Daily network fees in USD."),
    ("tvl_usd", "USD", "1d", "Daily total value locked."),
    ("stablecoin_supply_usd", "USD", "1d", "Daily stablecoin supply."),
    ("hashrate", "H/s", "1d", "Daily network hash rate."),
    ("validators", "validators", "1d", "Active-validator count."),
)


async def seed_reference_data(session: AsyncSession) -> None:
    for code, name, symbol, consensus, enabled in CHAINS:
        existing = await session.get(Chain, code)
        if existing is None:
            session.add(
                Chain(
                    code=code,
                    name=name,
                    native_symbol=symbol,
                    consensus=consensus,
                    enabled=enabled,
                )
            )
    for code, name, url, license_note, attribution in DATA_SOURCES:
        existing = await session.scalar(
            select(DataSource).where(DataSource.code == code)
        )
        if existing is None:
            session.add(
                DataSource(
                    code=code,
                    name=name,
                    url=url,
                    license_note=license_note,
                    attribution_required=attribution,
                )
            )
        else:
            existing.name = name
            existing.url = url
            existing.license_note = license_note
            existing.attribution_required = attribution
    for code, unit, frequency, description in METRICS:
        existing = await session.scalar(
            select(MetricDefinition).where(MetricDefinition.code == code)
        )
        if existing is None:
            session.add(
                MetricDefinition(
                    code=code,
                    unit=unit,
                    frequency=frequency,
                    description=description,
                )
            )
    await session.commit()
