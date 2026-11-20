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


FEATURE_INPUTS = (
    *(
        FeatureInput(chain, metric, "binance", "score")
        for chain in ("btc", "eth", "sol", "bnb")
        for metric in ("price_close_usd", "volume_usd")
    ),
    *(
        FeatureInput(chain, metric, "coin_metrics", "score")
        for chain in ("btc", "eth")
        for metric in ("active_addresses", "tx_count")
    ),
    *(
        FeatureInput(chain, "market_cap_usd", "coin_metrics", "context")
        for chain in ("btc", "eth")
    ),
    *(
        FeatureInput(chain, metric, "defillama", "score")
        for chain in ("eth", "sol", "bnb")
        for metric in ("tvl_usd", "stablecoin_supply_usd", "dex_volume_usd")
    ),
    FeatureInput("btc", "hashrate", "blockchain_info", "score"),
    FeatureInput("btc", "fees_usd", "blockchain_info", "score", derived=True),
    *(
        FeatureInput(chain, "protocol_fees_usd", "defillama", "context")
        for chain in ("btc", "eth", "sol", "bnb")
    ),
    FeatureInput("btc", "dex_volume_usd", "defillama", "context"),
    *(
        FeatureInput(chain, "market_cap_usd", "coingecko", "context")
        for chain in ("btc", "eth", "sol", "bnb")
    ),
)

_INPUT_BY_KEY = {
    (item.chain, item.metric, item.source): item for item in FEATURE_INPUTS
}


def get_feature_input(chain: str, metric: str, source: str) -> FeatureInput | None:
    return _INPUT_BY_KEY.get((chain, metric, source))


def is_score_input(chain: str, metric: str, source: str) -> bool:
    item = get_feature_input(chain, metric, source)
    return item is not None and item.role == "score"


def score_inputs() -> tuple[FeatureInput, ...]:
    return tuple(item for item in FEATURE_INPUTS if item.role == "score")
