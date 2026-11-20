from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.analytics.scenarios import (
    RETURN_QUANTUM,
    ScenarioAnalysis,
    calculate_scenarios,
    share_negative,
    type7_quantile,
    window_returns,
)
from app.analytics.scenarios_config import (
    HORIZONS_DAYS,
    LOW_SAMPLE_INDEPENDENT_WINDOWS,
    MIN_INDEPENDENT_WINDOWS,
    QUANTILES,
    VERSION,
)

START = date(2020, 1, 1)


def _daily_prices(window_count: int, horizon_days: int) -> list[tuple[date, Decimal]]:
    count = window_count + horizon_days
    return [
        (START + timedelta(days=index), Decimal(index + 1)) for index in range(count)
    ]


def _canonical_bytes(result: ScenarioAnalysis) -> bytes:
    return json.dumps(
        asdict(result),
        default=lambda value: (
            value.isoformat() if isinstance(value, date) else str(value)
        ),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_type7_quantiles_use_linear_interpolation() -> None:
    values = [
        Decimal("0"),
        Decimal("10"),
        Decimal("20"),
        Decimal("30"),
    ]

    assert type7_quantile(values, Decimal("0.10")) == Decimal("3.0")
    assert type7_quantile(values, Decimal("0.50")) == Decimal("15.0")
    assert type7_quantile(values, Decimal("0.90")) == Decimal("27.0")


def test_window_returns_use_exact_endpoints_and_round_to_six_places() -> None:
    prices = [
        (START, Decimal("3")),
        (START + timedelta(days=2), Decimal("4")),
        (START + timedelta(days=3), Decimal("8")),
    ]

    windows = window_returns(prices, START + timedelta(days=3), 2)

    assert windows == ((START, START + timedelta(days=2), Decimal("0.333333")),)


def test_window_returns_skip_missing_endpoints_without_filling_gaps() -> None:
    prices = [
        (START, Decimal("100")),
        (START + timedelta(days=1), Decimal("110")),
        (START + timedelta(days=3), Decimal("121")),
        (START + timedelta(days=4), Decimal("132")),
    ]

    windows = window_returns(prices, START + timedelta(days=4), 2)

    assert windows == (
        (
            START + timedelta(days=1),
            START + timedelta(days=3),
            Decimal("0.100000"),
        ),
    )


def test_share_negative_is_decimal_and_counts_only_negative_returns() -> None:
    assert share_negative(
        [
            Decimal("-0.100000"),
            Decimal("0"),
            Decimal("0.200000"),
            Decimal("-0.300000"),
        ]
    ) == Decimal("0.5000")


def test_scenario_results_are_point_in_time_under_future_append_and_mutation() -> None:
    as_of = START + timedelta(days=500)
    prices = _daily_prices(450, 30)
    original = _canonical_bytes(calculate_scenarios(prices, as_of))

    with_appended_future = prices + [
        (as_of + timedelta(days=1), Decimal("999999")),
        (as_of + timedelta(days=2), Decimal("1")),
    ]
    appended_result = _canonical_bytes(calculate_scenarios(with_appended_future, as_of))
    assert appended_result == original

    mutated_future = [
        (price_date, Decimal("0.000001") if price_date > as_of else close)
        for price_date, close in with_appended_future
    ]
    assert _canonical_bytes(calculate_scenarios(mutated_future, as_of)) == original


@pytest.mark.parametrize(
    ("independent_windows", "expected_available", "expected_low_sample"),
    [
        (MIN_INDEPENDENT_WINDOWS - 1, False, False),
        (MIN_INDEPENDENT_WINDOWS, True, True),
        (LOW_SAMPLE_INDEPENDENT_WINDOWS, True, False),
    ],
)
def test_independent_window_sample_gates(
    independent_windows: int,
    expected_available: bool,
    expected_low_sample: bool,
) -> None:
    horizon_days = HORIZONS_DAYS[0]
    prices = _daily_prices(independent_windows * horizon_days, horizon_days)

    result = calculate_scenarios(prices, prices[-1][0])
    horizon = result.horizons[0]

    assert horizon.n_windows == independent_windows * horizon_days
    assert horizon.n_independent == independent_windows
    assert horizon.available is expected_available
    assert horizon.low_sample is expected_low_sample
    if not expected_available:
        assert horizon.reason == "insufficient_history"
        assert horizon.share_negative is None
        assert horizon.scenarios == ()


def test_scenarios_are_decimal_ordered_and_have_exact_names() -> None:
    result = calculate_scenarios(
        _daily_prices(30 * 10, 30),
        START + timedelta(days=329),
    )
    horizon = result.horizons[0]

    assert result.version == VERSION == "scenarios-v1"
    assert result.not_a_forecast is True
    assert horizon.available is True
    assert [scenario.name for scenario in horizon.scenarios] == [
        "pessimistic",
        "base",
        "optimistic",
    ]
    assert [scenario.quantile for scenario in horizon.scenarios] == [
        "p10",
        "p50",
        "p90",
    ]
    returns = [scenario.return_value for scenario in horizon.scenarios]
    assert returns == sorted(returns)
    window_values = [
        window[2]
        for window in window_returns(
            _daily_prices(300, 30), START + timedelta(days=329), 30
        )
    ]
    assert returns == [
        type7_quantile(window_values, spec.probability).quantize(RETURN_QUANTUM)
        for spec in QUANTILES
    ]
    assert all(isinstance(value, Decimal) for value in returns)
    assert isinstance(result.base_price.close_usd, Decimal)
    assert all(
        isinstance(scenario.illustrative_price_usd, Decimal)
        for scenario in horizon.scenarios
    )
    assert horizon.scenarios[
        1
    ].illustrative_price_usd == result.base_price.close_usd * (
        Decimal("1") + horizon.scenarios[1].return_value
    )
    assert isinstance(horizon.share_negative, Decimal)


def test_all_generated_text_avoids_banned_words() -> None:
    result = calculate_scenarios(_daily_prices(30 * 5, 30), START + timedelta(days=179))
    text_fields = [
        result.version,
        result.method_note,
        *(horizon.reason or "" for horizon in result.horizons),
        *(
            text
            for horizon in result.horizons
            for scenario in horizon.scenarios
            for text in (scenario.name, scenario.quantile)
        ),
    ]
    banned = re.compile(r"\b(target|predict|will|buy|sell|guarantee)\b", re.I)

    assert all(banned.search(value) is None for value in text_fields)


def test_config_has_fixed_horizons_and_monotone_quantiles() -> None:
    assert HORIZONS_DAYS == (30, 90, 365)
    assert [item.name for item in QUANTILES] == [
        "pessimistic",
        "base",
        "optimistic",
    ]
    assert [item.probability for item in QUANTILES] == sorted(
        item.probability for item in QUANTILES
    )
