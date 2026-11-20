from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

VERSION = "scenarios-v1"
HORIZONS_DAYS = (30, 90, 365)
ScenarioName = Literal["pessimistic", "base", "optimistic"]
QuantileName = Literal["p10", "p50", "p90"]


@dataclass(frozen=True)
class QuantileSpec:
    name: ScenarioName
    label: QuantileName
    probability: Decimal


QUANTILES = (
    QuantileSpec("pessimistic", "p10", Decimal("0.10")),
    QuantileSpec("base", "p50", Decimal("0.50")),
    QuantileSpec("optimistic", "p90", Decimal("0.90")),
)
MIN_INDEPENDENT_WINDOWS = 5
LOW_SAMPLE_INDEPENDENT_WINDOWS = 10
RETURN_QUANTUM = Decimal("0.000001")
SHARE_QUANTUM = Decimal("0.0001")
METHOD_NOTE = (
    "Historical realised calendar-day return quantiles applied to the latest "
    "close; descriptive statistics only, not a forecast."
)
SCENARIO_DISCLAIMER = (
    "Scenarios summarise historical returns only; not a forecast and not "
    "financial advice."
)
SCENARIO_LIMITATION = (
    "Scenarios are historical return quantiles, not forecasts; overlapping "
    "windows reduce the effective sample size."
)
