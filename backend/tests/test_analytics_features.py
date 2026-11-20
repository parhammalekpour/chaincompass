from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.analytics.features import (
    _LOGGED_EXCLUSIONS,
    FeaturePoint,
    compute_series_features,
    find_effective_start,
)
from app.analytics.registry import FEATURE_INPUTS, is_score_input, score_inputs

START = date(2020, 1, 1)


def points(values: list[Decimal], *, start: date = START) -> list[FeaturePoint]:
    return [
        FeaturePoint(start + timedelta(days=index), value)
        for index, value in enumerate(values)
    ]


def at_date(features, feature: str, as_of: date) -> Decimal | None:
    return next(
        (
            item.value
            for item in features
            if item.feature == feature and item.as_of_date == as_of
        ),
        None,
    )


def test_price_return_uses_exact_calendar_offset_and_decimal_rounding() -> None:
    series = points([Decimal(3)] * 30 + [Decimal(10)] * 7)
    as_of = START + timedelta(days=36)
    result = compute_series_features("btc", "price_close_usd", "binance", series)
    assert at_date(result, "ret_7d", as_of) == Decimal("2.333333333333")
    assert all(isinstance(item.value, Decimal) for item in result)
    assert all(item.value.as_tuple().exponent == -12 for item in result)


def test_realized_volatility_matches_hand_computed_sample_standard_deviation() -> None:
    values = [Decimal(1)]
    for day in range(1, 31):
        values.append(values[-1] * (Decimal(2) if day % 2 else Decimal("0.5")))
    result = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        points(values),
    )
    expected = (
        (Decimal(30) / Decimal(29)).sqrt() * Decimal(2).ln() * Decimal(365).sqrt()
    ).quantize(Decimal("0.000000000001"))
    assert at_date(result, "realized_vol_30d", START + timedelta(days=30)) == expected


def test_drawdown_and_sma200_ratio_match_hand_computed_values() -> None:
    values = [Decimal(100)] * 366
    values[100] = Decimal(200)
    values[365] = Decimal(150)
    result = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        points(values),
    )
    as_of = START + timedelta(days=365)
    assert at_date(result, "drawdown_365d", as_of) == Decimal("-0.250000000000")

    sma_values = [Decimal(100)] * 200
    sma_values[-1] = Decimal(200)
    sma_result = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        points(sma_values),
    )
    assert at_date(
        sma_result,
        "price_vs_sma200",
        START + timedelta(days=199),
    ) == Decimal("0.990049751244")


def test_level_median_and_changes_use_distinct_calendar_windows() -> None:
    values = (
        [Decimal(5)] * 30 + [Decimal(7)] * 30 + [Decimal(10)] * 30 + [Decimal(20)] * 30
    )
    result = compute_series_features(
        "btc",
        "active_addresses",
        "coin_metrics",
        points(values),
    )
    as_of = START + timedelta(days=119)
    assert at_date(result, "active_addresses_med30", as_of) == Decimal(
        "20.000000000000"
    )
    assert at_date(result, "active_addresses_chg30", as_of) == Decimal("1.000000000000")
    assert at_date(result, "active_addresses_chg90", as_of) == Decimal("3.000000000000")


def test_future_append_and_mutation_cannot_change_past_features() -> None:
    initial = points(
        [Decimal(100 + index) for index in range(46)],
    )
    cutoff = START + timedelta(days=45)
    initial_features = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        initial,
    )
    future_dates = [
        FeaturePoint(cutoff + timedelta(days=index), Decimal(999999 + index))
        for index in range(1, 35)
    ]
    appended_features = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        initial + future_dates,
    )
    mutated_future = [
        FeaturePoint(item.obs_date, Decimal("1e20") / Decimal(index + 1))
        for index, item in enumerate(future_dates)
    ]
    mutated_features = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        initial + mutated_future,
    )

    def snapshot(features):
        return [
            (
                item.feature,
                item.as_of_date.isoformat(),
                str(item.value),
                item.n_obs,
                item.window_days,
                item.source_metric,
                item.source,
                item.role,
            )
            for item in features
            if item.as_of_date <= cutoff
        ]

    expected = snapshot(initial_features)
    assert snapshot(appended_features) == expected
    assert snapshot(mutated_features) == expected


def test_gaps_are_not_filled_and_insufficient_windows_have_no_value() -> None:
    price_points = points([Decimal(100 + index) for index in range(110)])
    removed_dates = {START + timedelta(days=index) for index in range(93, 99)}
    gapped_prices = [
        point for point in price_points if point.obs_date not in removed_dates
    ]
    price_result = compute_series_features(
        "btc",
        "price_close_usd",
        "binance",
        gapped_prices,
    )
    as_of = START + timedelta(days=100)
    assert at_date(price_result, "ret_7d", as_of) is None
    assert at_date(price_result, "realized_vol_30d", as_of) is None

    level_points = points([Decimal(10)] * 60)
    missing_days = {START + timedelta(days=index) for index in range(30, 37)}
    gapped_level = [
        point for point in level_points if point.obs_date not in missing_days
    ]
    level_result = compute_series_features(
        "btc",
        "active_addresses",
        "coin_metrics",
        gapped_level,
    )
    assert (
        at_date(
            level_result,
            "active_addresses_med30",
            START + timedelta(days=59),
        )
        is None
    )


def test_pre_effective_windows_are_excluded_and_exclusion_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    values = [Decimal(0)] * 20 + [Decimal(100)] * 410
    series = points(values)
    effective = START + timedelta(days=20)
    assert find_effective_start(series) == effective
    as_of = effective + timedelta(days=118)
    _LOGGED_EXCLUSIONS.discard(("btc", "active_addresses", "coin_metrics"))
    with caplog.at_level(logging.INFO, logger="app.analytics.features"):
        first = compute_series_features(
            "btc",
            "active_addresses",
            "coin_metrics",
            series,
            as_of_dates=[as_of],
        )
        compute_series_features(
            "btc",
            "active_addresses",
            "coin_metrics",
            series,
            as_of_dates=[as_of],
        )
    assert at_date(first, "active_addresses_med30", as_of) == Decimal(
        "100.000000000000"
    )
    assert at_date(first, "active_addresses_chg30", as_of) == Decimal("0.000000000000")
    assert at_date(first, "active_addresses_chg90", as_of) is None
    assert caplog.text.count("feature_leading_data_excluded") == 1

    price_series = points(values)
    price_as_of = effective + timedelta(days=364)
    price_features = compute_series_features(
        "eth",
        "price_close_usd",
        "binance",
        price_series,
        as_of_dates=[price_as_of],
    )
    assert at_date(price_features, "ret_365d", price_as_of) is None
    assert at_date(price_features, "drawdown_365d", price_as_of) == Decimal(
        "0.000000000000"
    )


def test_registry_separates_context_and_excludes_unavailable_sources() -> None:
    keys = {(item.chain, item.metric, item.source) for item in FEATURE_INPUTS}
    assert len(keys) == len(FEATURE_INPUTS) == 34
    assert all(item.role in {"score", "context"} for item in FEATURE_INPUTS)
    assert is_score_input("btc", "fees_usd", "blockchain_info")
    assert is_score_input("eth", "dex_volume_usd", "defillama")
    assert not is_score_input("btc", "dex_volume_usd", "defillama")
    assert not is_score_input("btc", "protocol_fees_usd", "defillama")
    assert not is_score_input("eth", "market_cap_usd", "coingecko")
    assert not is_score_input("bnb", "active_addresses", "coin_metrics")
    assert not is_score_input("sol", "tx_count", "coin_metrics")
    assert not is_score_input("btc", "tvl_usd", "defillama")
    assert all(item.role == "score" for item in score_inputs())
