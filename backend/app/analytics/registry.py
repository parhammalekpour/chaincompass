from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FeatureRole = Literal["score", "context"]


@dataclass(frozen=True)
class FeatureInput:
    chain: str
    metric: str
    source: str
    role: FeatureRole
    derived: bool = False
    unit_note: str = "Provider-reported unit; verify before interpretation."
    availability_note: str | None = None


_UNIT_NOTES = {
    ("binance", "price_close_usd"): (
        "USD proxy; Binance spot prices are quoted in USDT."
    ),
    ("binance", "volume_usd"): (
        "USD quote-volume proxy; Binance spot volume is quoted in USDT."
    ),
    ("coin_metrics", "active_addresses"): "Address count from Coin Metrics Community.",
    ("coin_metrics", "tx_count"): "Transaction count from Coin Metrics Community.",
    ("coin_metrics", "market_cap_usd"): (
        "USD-denominated market-cap estimate from Coin Metrics Community."
    ),
    ("coingecko", "market_cap_usd"): (
        "USD-denominated market-cap estimate from CoinGecko snapshots."
    ),
    ("defillama", "tvl_usd"): (
        "DefiLlama-reported value; unit semantics are UNVERIFIED."
    ),
    ("defillama", "stablecoin_supply_usd"): (
        "DefiLlama-reported value; unit semantics are UNVERIFIED."
    ),
    ("defillama", "dex_volume_usd"): (
        "DefiLlama-reported value; unit semantics are UNVERIFIED."
    ),
    ("defillama", "protocol_fees_usd"): (
        "DefiLlama protocol fees, not network fees; unit semantics are UNVERIFIED."
    ),
    ("blockchain_info", "hashrate"): (
        "H/s; Blockchain.info TH/s values converted to H/s."
    ),
    ("blockchain_info", "fees_usd"): (
        "Derived USD estimate: BTC fees converted using same-day Binance close."
    ),
}


def _unit_note(metric: str, source: str) -> str:
    return _UNIT_NOTES.get(
        (source, metric),
        "Provider-reported unit; verify before interpretation.",
    )


FEATURE_INPUTS = (
    *(
        FeatureInput(
            chain,
            metric,
            "binance",
            "score",
            unit_note=_unit_note(metric, "binance"),
        )
        for chain in ("btc", "eth", "sol", "bnb")
        for metric in ("price_close_usd", "volume_usd")
    ),
    *(
        FeatureInput(
            chain,
            metric,
            "coin_metrics",
            "score",
            unit_note=_unit_note(metric, "coin_metrics"),
        )
        for chain in ("btc", "eth")
        for metric in ("active_addresses", "tx_count")
    ),
    *(
        FeatureInput(
            chain,
            "market_cap_usd",
            "coin_metrics",
            "context",
            unit_note=_unit_note("market_cap_usd", "coin_metrics"),
        )
        for chain in ("btc", "eth")
    ),
    *(
        FeatureInput(
            chain,
            metric,
            "defillama",
            "score",
            unit_note=_unit_note(metric, "defillama"),
        )
        for chain in ("eth", "sol", "bnb")
        for metric in ("tvl_usd", "stablecoin_supply_usd", "dex_volume_usd")
    ),
    FeatureInput(
        "btc",
        "hashrate",
        "blockchain_info",
        "score",
        unit_note=_unit_note("hashrate", "blockchain_info"),
    ),
    FeatureInput(
        "btc",
        "fees_usd",
        "blockchain_info",
        "score",
        derived=True,
        unit_note=_unit_note("fees_usd", "blockchain_info"),
    ),
    *(
        FeatureInput(
            chain,
            "protocol_fees_usd",
            "defillama",
            "context",
            unit_note=_unit_note("protocol_fees_usd", "defillama"),
        )
        for chain in ("btc", "eth", "sol", "bnb")
    ),
    FeatureInput(
        "btc",
        "dex_volume_usd",
        "defillama",
        "context",
        unit_note=_unit_note("dex_volume_usd", "defillama"),
    ),
    *(
        FeatureInput(
            chain,
            "market_cap_usd",
            "coingecko",
            "context",
            unit_note=_unit_note("market_cap_usd", "coingecko"),
        )
        for chain in ("btc", "eth", "sol", "bnb")
    ),
)

PUBLIC_UNAVAILABLE_INPUTS = (
    *(
        FeatureInput(
            "bnb",
            metric,
            "coin_metrics",
            "context",
            unit_note="Legacy Coin Metrics BNB asset data, not current BNB Chain.",
            availability_note=(
                "Legacy BNB asset series ended 2019-04-22; it is not BNB Chain."
            ),
        )
        for metric in ("market_cap_usd", "active_addresses", "tx_count")
    ),
    *(
        FeatureInput(
            "sol",
            metric,
            "coin_metrics",
            "context",
            unit_note="Coin Metrics Community unit; series is unavailable.",
            availability_note=(
                "This Coin Metrics Community series is unavailable for Solana."
            ),
        )
        for metric in ("market_cap_usd", "active_addresses", "tx_count")
    ),
    *(
        FeatureInput(
            "btc",
            metric,
            "defillama",
            "context",
            unit_note="DefiLlama unit semantics are UNVERIFIED.",
            availability_note=(
                "The audited Bitcoin DefiLlama endpoint returned no available "
                "series; no new request was made."
            ),
        )
        for metric in ("tvl_usd", "stablecoin_supply_usd")
    ),
)

PUBLIC_SERIES_INPUTS = (*FEATURE_INPUTS, *PUBLIC_UNAVAILABLE_INPUTS)

_INPUT_BY_KEY = {
    (item.chain, item.metric, item.source): item for item in FEATURE_INPUTS
}
_PUBLIC_INPUT_BY_KEY = {
    (item.chain, item.metric, item.source): item for item in PUBLIC_SERIES_INPUTS
}


def get_feature_input(chain: str, metric: str, source: str) -> FeatureInput | None:
    return _INPUT_BY_KEY.get((chain, metric, source))


def get_public_series_inputs(chain: str, metric: str) -> tuple[FeatureInput, ...]:
    return tuple(
        item
        for (item_chain, item_metric, _), item in _PUBLIC_INPUT_BY_KEY.items()
        if item_chain == chain and item_metric == metric
    )


def public_series_inputs(chain: str | None = None) -> tuple[FeatureInput, ...]:
    return tuple(
        item for item in PUBLIC_SERIES_INPUTS if chain is None or item.chain == chain
    )


def is_score_input(chain: str, metric: str, source: str) -> bool:
    item = get_feature_input(chain, metric, source)
    return item is not None and item.role == "score"


def score_inputs() -> tuple[FeatureInput, ...]:
    return tuple(item for item in FEATURE_INPUTS if item.role == "score")
