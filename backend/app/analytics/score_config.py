from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

VERSION = "v1"
CHAINS = ("btc", "eth", "sol", "bnb")
WEIGHT_DENOMINATOR = Decimal("100")
PERCENTILE_WINDOW_DAYS = 1095
MIN_PERCENTILE_OBSERVATIONS = 365
PERCENTILE_SCALE = Decimal("100")
MIDRANK_EQUAL_FACTOR = Decimal("0.5")
DECIMAL_PRECISION = 50
PERCENTILE_QUANTUM = Decimal("0.000000000001")
PILLAR_QUANTUM = Decimal("0.000000000001")
SCORE_QUANTUM = Decimal("0.01")
COVERAGE_QUANTUM = Decimal("0.0001")
VALUE_QUANTUM = Decimal("0.000000000001")
NO_SCORE_COVERAGE = Decimal("0.40")
HIGH_CONFIDENCE_COVERAGE = Decimal("0.80")
MEDIUM_CONFIDENCE_COVERAGE = Decimal("0.50")
CONFIDENCE_HIGH = "High"
CONFIDENCE_MEDIUM = "Medium"
CONFIDENCE_LOW = "Low"
UPDATE_DAYS = 14
INSERT_BATCH_SIZE = 1000
HYSTERESIS_DAYS = 5
SEVERITY_INFO = "info"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
VOL_STATE_HIGH = "high"
VOL_STATE_LOW = "low"
VOL_STATE_NORMAL = "normal"

REGIME_STRESS = "stress"
REGIME_UPTREND = "uptrend"
REGIME_DOWNTREND = "downtrend"
REGIME_RANGE = "range"
REGIME_LABELS = (
    REGIME_STRESS,
    REGIME_UPTREND,
    REGIME_DOWNTREND,
    REGIME_RANGE,
)
STRESS_DRAWDOWN_THRESHOLD = Decimal("-0.50")
HIGH_VOLATILITY_STATE_THRESHOLD = Decimal("80")
LOW_VOLATILITY_STATE_THRESHOLD = Decimal("20")

HIGH_VOLATILITY_RISK_THRESHOLD = Decimal("90")
DEEP_DRAWDOWN_THRESHOLD = Decimal("-0.40")
HIGH_DEEP_DRAWDOWN_THRESHOLD = Decimal("-0.60")
LIQUIDITY_DRYING_THRESHOLD = Decimal("0.50")
USAGE_DECLINE_THRESHOLD = Decimal("-0.20")
TVL_OUTFLOW_THRESHOLD = Decimal("-0.25")
STABLECOIN_CONTRACTION_THRESHOLD = Decimal("-0.10")
HASHRATE_DECLINE_THRESHOLD = Decimal("-0.15")
LOW_CONFIDENCE_THRESHOLD = Decimal("0.50")

Direction = Literal["higher_is_better", "lower_is_better"]
Comparison = Literal["lt", "lte", "gte"]
RiskValueKind = Literal["feature", "percentile", "coverage"]


@dataclass(frozen=True)
class PillarSpec:
    name: str
    weight: int


@dataclass(frozen=True)
class ComponentSpec:
    feature: str
    source_metric: str
    source: str
    pillar: str
    weight: int
    direction: Direction
    chains: tuple[str, ...]
    derived_label: str | None = None


@dataclass(frozen=True)
class RiskFlagSpec:
    flag: str
    feature: str | None
    source_metric: str | None
    source: str | None
    chains: tuple[str, ...]
    value_kind: RiskValueKind
    comparison: Comparison
    threshold: Decimal
    severity: str
    high_severity_threshold: Decimal | None = None


PILLARS = (
    PillarSpec("adoption", 30),
    PillarSpec("capital", 30),
    PillarSpec("security_economics", 10),
    PillarSpec("market_condition", 30),
)

COMPONENTS = (
    ComponentSpec(
        "active_addresses_chg90",
        "active_addresses",
        "coin_metrics",
        "adoption",
        15,
        "higher_is_better",
        ("btc", "eth"),
    ),
    ComponentSpec(
        "tx_count_chg90",
        "tx_count",
        "coin_metrics",
        "adoption",
        15,
        "higher_is_better",
        ("btc", "eth"),
    ),
    ComponentSpec(
        "tvl_usd_chg90",
        "tvl_usd",
        "defillama",
        "capital",
        12,
        "higher_is_better",
        ("eth", "sol", "bnb"),
    ),
    ComponentSpec(
        "stablecoin_supply_usd_chg90",
        "stablecoin_supply_usd",
        "defillama",
        "capital",
        12,
        "higher_is_better",
        ("eth", "sol", "bnb"),
    ),
    ComponentSpec(
        "dex_volume_usd_chg90",
        "dex_volume_usd",
        "defillama",
        "capital",
        6,
        "higher_is_better",
        ("eth", "sol", "bnb"),
    ),
    ComponentSpec(
        "hashrate_chg90",
        "hashrate",
        "blockchain_info",
        "security_economics",
        7,
        "higher_is_better",
        ("btc",),
    ),
    ComponentSpec(
        "fees_usd_chg90",
        "fees_usd",
        "blockchain_info",
        "security_economics",
        3,
        "higher_is_better",
        ("btc",),
        "Derived USD fees from Blockchain.info BTC fees and same-day Binance close",
    ),
    ComponentSpec(
        "drawdown_365d",
        "price_close_usd",
        "binance",
        "market_condition",
        10,
        "higher_is_better",
        CHAINS,
    ),
    ComponentSpec(
        "realized_vol_90d",
        "price_close_usd",
        "binance",
        "market_condition",
        7,
        "lower_is_better",
        CHAINS,
    ),
    ComponentSpec(
        "volume_ratio_30_365",
        "volume_usd",
        "binance",
        "market_condition",
        8,
        "higher_is_better",
        CHAINS,
    ),
    ComponentSpec(
        "price_vs_sma200",
        "price_close_usd",
        "binance",
        "market_condition",
        5,
        "higher_is_better",
        CHAINS,
    ),
)

REGIME_FEATURES = {
    "drawdown_365d": ("price_close_usd", "binance"),
    "price_vs_sma200": ("price_close_usd", "binance"),
    "ret_90d": ("price_close_usd", "binance"),
    "realized_vol_90d": ("price_close_usd", "binance"),
}

RISK_FLAGS = (
    RiskFlagSpec(
        "deep_drawdown",
        "drawdown_365d",
        "price_close_usd",
        "binance",
        CHAINS,
        "feature",
        "lte",
        DEEP_DRAWDOWN_THRESHOLD,
        SEVERITY_MEDIUM,
        HIGH_DEEP_DRAWDOWN_THRESHOLD,
    ),
    RiskFlagSpec(
        "high_volatility",
        "realized_vol_30d",
        "price_close_usd",
        "binance",
        CHAINS,
        "percentile",
        "gte",
        HIGH_VOLATILITY_RISK_THRESHOLD,
        SEVERITY_MEDIUM,
    ),
    RiskFlagSpec(
        "liquidity_drying",
        "volume_ratio_30_365",
        "volume_usd",
        "binance",
        CHAINS,
        "feature",
        "lt",
        LIQUIDITY_DRYING_THRESHOLD,
        SEVERITY_MEDIUM,
    ),
    RiskFlagSpec(
        "usage_decline",
        "active_addresses_chg90",
        "active_addresses",
        "coin_metrics",
        ("btc", "eth"),
        "feature",
        "lte",
        USAGE_DECLINE_THRESHOLD,
        SEVERITY_MEDIUM,
    ),
    RiskFlagSpec(
        "tvl_outflow",
        "tvl_usd_chg90",
        "tvl_usd",
        "defillama",
        ("eth", "sol", "bnb"),
        "feature",
        "lte",
        TVL_OUTFLOW_THRESHOLD,
        SEVERITY_MEDIUM,
    ),
    RiskFlagSpec(
        "stablecoin_contraction",
        "stablecoin_supply_usd_chg90",
        "stablecoin_supply_usd",
        "defillama",
        ("eth", "sol", "bnb"),
        "feature",
        "lte",
        STABLECOIN_CONTRACTION_THRESHOLD,
        SEVERITY_MEDIUM,
    ),
    RiskFlagSpec(
        "hashrate_decline",
        "hashrate_chg90",
        "hashrate",
        "blockchain_info",
        ("btc",),
        "feature",
        "lte",
        HASHRATE_DECLINE_THRESHOLD,
        SEVERITY_MEDIUM,
    ),
    RiskFlagSpec(
        "low_confidence",
        None,
        None,
        None,
        CHAINS,
        "coverage",
        "lt",
        LOW_CONFIDENCE_THRESHOLD,
        SEVERITY_INFO,
    ),
)

RISK_FEATURES: dict[str, tuple[str, str]] = {
    spec.feature: (spec.source_metric, spec.source)
    for spec in RISK_FLAGS
    if spec.feature is not None
    and spec.source_metric is not None
    and spec.source is not None
}


def maximum_coverage_by_chain() -> dict[str, Decimal]:
    return {
        chain: (
            sum(
                (Decimal(spec.weight) for spec in COMPONENTS if chain in spec.chains),
                Decimal(0),
            )
            / WEIGHT_DENOMINATOR
        ).quantize(COVERAGE_QUANTUM)
        for chain in CHAINS
    }
