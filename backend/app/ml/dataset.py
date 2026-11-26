from __future__ import annotations

import hashlib
import math
from bisect import bisect_right, insort
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.score_config import CHAINS
from app.db.models.ingestion import Observation

DATA_CUTOFF = date(2026, 11, 19)
PROTOCOL_COMMIT = "08da59e507fedddf227f9e80dfd66b34d859ef70"
EXPANDING_MINIMUM = 365
Q80_MINIMUM = 365
FEATURE_NAMES = (
    "rv30",
    "rv90",
    "rv30_over_rv90",
    "ret_30d",
    "ret_90d",
    "drawdown_365d",
    "price_vs_sma200",
    "volume_ratio_30_365",
)
MODEL_FEATURE_NAMES = FEATURE_NAMES + tuple(
    f"{name}_expanding_rank" for name in FEATURE_NAMES
)
EXTRA_HASH_VALUES = ("rv7", "rv30", "q80", "rv30_fwd")

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int8]


@dataclass(frozen=True)
class ChainInputs:
    dates: tuple[date, ...]
    closes: tuple[float | None, ...]
    volumes: tuple[float | None, ...]


@dataclass(frozen=True)
class FeatureFrame:
    dates: tuple[date, ...]
    closes: FloatArray
    volumes: FloatArray
    base_features: FloatArray
    features: FloatArray
    rv7: FloatArray
    rv30: FloatArray
    rv90: FloatArray
    q80: FloatArray
    volume_mean_30: FloatArray
    volume_mean_365: FloatArray


@dataclass(frozen=True)
class LabelFrame:
    labels: IntArray
    rv30_fwd: FloatArray


@dataclass(frozen=True)
class DatasetRow:
    chain: str
    obs_date: date
    y: int
    features: tuple[float, ...]
    rv7: float
    rv30: float
    q80: float
    rv30_fwd: float


@dataclass(frozen=True)
class Dataset:
    rows: tuple[DatasetRow, ...]
    sha256: str


@dataclass(frozen=True)
class Fold:
    index: int
    test_start: date
    test_end_exclusive: date
    train_cutoff: date
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def dense_calendar(
    dates: Sequence[date],
    closes: Sequence[float | None],
    volumes: Sequence[float | None],
) -> tuple[tuple[date, ...], FloatArray, FloatArray]:
    if len(dates) != len(closes) or len(dates) != len(volumes):
        raise ValueError("dates, closes, and volumes must have equal lengths")
    if not dates:
        empty = np.empty(0, dtype=np.float64)
        return (), empty, empty.copy()

    observations: dict[date, tuple[float | None, float | None]] = {}
    for obs_date, close, volume in zip(dates, closes, volumes, strict=True):
        if obs_date in observations:
            raise ValueError(f"duplicate observation date: {obs_date.isoformat()}")
        observations[obs_date] = (close, volume)

    first_date = min(observations)
    last_date = max(observations)
    calendar: list[date] = []
    dense_closes: list[float] = []
    dense_volumes: list[float] = []
    cursor = first_date
    while cursor <= last_date:
        close, volume = observations.get(cursor, (None, None))
        calendar.append(cursor)
        dense_closes.append(float(close) if close is not None else math.nan)
        dense_volumes.append(float(volume) if volume is not None else math.nan)
        cursor += timedelta(days=1)
    return (
        tuple(calendar),
        np.asarray(dense_closes, dtype=np.float64),
        np.asarray(dense_volumes, dtype=np.float64),
    )


def _hf7_sorted(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("type-7 quantile requires at least one value")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between zero and one")
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return float(values[lower] * (1.0 - weight) + values[upper] * weight)


def hf7_quantile(values: Sequence[float], probability: float) -> float:
    numeric = np.asarray(values, dtype=np.float64)
    if numeric.size == 0:
        raise ValueError("type-7 quantile requires at least one value")
    if not np.all(np.isfinite(numeric)):
        raise ValueError("type-7 quantile values must be finite")
    return _hf7_sorted(sorted(float(value) for value in numeric), probability)


def _valid_window(values: FloatArray, start: int, end: int) -> bool:
    return start >= 0 and bool(np.all(np.isfinite(values[start : end + 1])))


def _valid_price_window(values: FloatArray, start: int, end: int) -> bool:
    return _valid_window(values, start, end) and bool(
        np.all(values[start : end + 1] > 0)
    )


def _realized_volatility(closes: FloatArray, start: int, end: int) -> float:
    prices = closes[start : end + 1]
    if len(prices) < 2 or not np.all(np.isfinite(prices)) or np.any(prices <= 0):
        return math.nan
    log_returns = np.diff(np.log(prices))
    return float(np.std(log_returns, ddof=1) * math.sqrt(365.0))


def build_feature_frame(
    dates: Sequence[date],
    closes: Sequence[float | None],
    volumes: Sequence[float | None],
) -> FeatureFrame:
    calendar, dense_closes, dense_volumes = dense_calendar(dates, closes, volumes)
    count = len(calendar)
    base_features = np.full((count, len(FEATURE_NAMES)), np.nan, dtype=np.float64)
    rv7 = np.full(count, np.nan, dtype=np.float64)
    rv30 = np.full(count, np.nan, dtype=np.float64)
    rv90 = np.full(count, np.nan, dtype=np.float64)
    volume_mean_30 = np.full(count, np.nan, dtype=np.float64)
    volume_mean_365 = np.full(count, np.nan, dtype=np.float64)

    for index in range(count):
        rv7[index] = _realized_volatility(dense_closes, index - 7, index)
        rv30[index] = _realized_volatility(dense_closes, index - 30, index)
        rv90[index] = _realized_volatility(dense_closes, index - 90, index)

        if math.isfinite(rv30[index]):
            base_features[index, 0] = rv30[index]
        if math.isfinite(rv90[index]):
            base_features[index, 1] = rv90[index]
        if (
            math.isfinite(rv30[index])
            and math.isfinite(rv90[index])
            and rv90[index] > 0
        ):
            base_features[index, 2] = rv30[index] / rv90[index]

        for days, feature_column in ((30, 3), (90, 4)):
            start = index - days
            if _valid_price_window(dense_closes, start, index):
                window = dense_closes[start : index + 1]
                base_features[index, feature_column] = float(
                    np.log(window[-1] / window[0])
                )

        drawdown_start = index - 364
        if _valid_price_window(dense_closes, drawdown_start, index):
            window = dense_closes[drawdown_start : index + 1]
            base_features[index, 5] = float(window[-1] / np.max(window) - 1.0)

        sma_start = index - 199
        if _valid_price_window(dense_closes, sma_start, index):
            window = dense_closes[sma_start : index + 1]
            mean_close = float(np.mean(window))
            if mean_close > 0:
                base_features[index, 6] = float(window[-1] / mean_close - 1.0)

        volume_start_30 = index - 29
        volume_start_365 = index - 364
        if _valid_window(dense_volumes, volume_start_30, index):
            volume_mean_30[index] = float(
                np.mean(dense_volumes[volume_start_30 : index + 1])
            )
        if _valid_window(dense_volumes, volume_start_365, index):
            volume_mean_365[index] = float(
                np.mean(dense_volumes[volume_start_365 : index + 1])
            )
        if (
            math.isfinite(volume_mean_30[index])
            and math.isfinite(volume_mean_365[index])
            and volume_mean_30[index] > 0
            and volume_mean_365[index] > 0
        ):
            base_features[index, 7] = volume_mean_30[index] / volume_mean_365[index]

    ranks = np.full_like(base_features, np.nan)
    ranked_history: list[list[float]] = [[] for _ in FEATURE_NAMES]
    q80 = np.full(count, np.nan, dtype=np.float64)
    sorted_rv30: list[float] = []
    for index in range(count):
        for column in range(len(FEATURE_NAMES)):
            value = float(base_features[index, column])
            if not math.isfinite(value):
                continue
            history = ranked_history[column]
            insort(history, value)
            if len(history) >= EXPANDING_MINIMUM:
                ranks[index, column] = bisect_right(history, value) / len(history)

        current_rv30 = float(rv30[index])
        if math.isfinite(current_rv30):
            insort(sorted_rv30, current_rv30)
        if len(sorted_rv30) >= Q80_MINIMUM:
            q80[index] = _hf7_sorted(sorted_rv30, 0.8)

    all_features = np.concatenate((base_features, ranks), axis=1)
    return FeatureFrame(
        dates=calendar,
        closes=dense_closes,
        volumes=dense_volumes,
        base_features=base_features,
        features=all_features,
        rv7=rv7,
        rv30=rv30,
        rv90=rv90,
        q80=q80,
        volume_mean_30=volume_mean_30,
        volume_mean_365=volume_mean_365,
    )


def q80_window_ends(frame: FeatureFrame, index: int) -> tuple[int, ...]:
    if index < 0 or index >= len(frame.dates):
        raise IndexError("Q80 index is outside the feature frame")
    return tuple(
        end for end in range(index + 1) if math.isfinite(float(frame.rv30[end]))
    )


def build_labels(frame: FeatureFrame, cutoff: date) -> LabelFrame:
    labels = np.full(len(frame.dates), -1, dtype=np.int8)
    rv30_fwd = np.full(len(frame.dates), np.nan, dtype=np.float64)
    for index, obs_date in enumerate(frame.dates):
        if obs_date + timedelta(days=30) > cutoff:
            continue
        end = index + 30
        if end >= len(frame.dates) or not math.isfinite(float(frame.q80[index])):
            continue
        if not _valid_window(frame.closes, index, end):
            continue
        forward_volatility = _realized_volatility(frame.closes, index, end)
        if not math.isfinite(forward_volatility):
            continue
        rv30_fwd[index] = forward_volatility
        labels[index] = int(forward_volatility > float(frame.q80[index]))
    return LabelFrame(labels=labels, rv30_fwd=rv30_fwd)


def _dataset_hash(rows: Sequence[DatasetRow], cutoff: date) -> str:
    digest = hashlib.sha256()
    digest.update(f"{cutoff.isoformat()}\n".encode())
    for row in sorted(rows, key=lambda item: (item.chain, item.obs_date)):
        fields = [row.chain, row.obs_date.isoformat(), str(row.y)]
        numeric_values = (
            *row.features,
            row.rv7,
            row.rv30,
            row.q80,
            row.rv30_fwd,
        )
        fields.extend(format(float(value), ".12e") for value in numeric_values)
        digest.update(("|".join(fields) + "\n").encode())
    return digest.hexdigest()


def build_dataset(
    per_chain_inputs: Mapping[str, ChainInputs],
    cutoff: date,
) -> Dataset:
    rows: list[DatasetRow] = []
    for chain in CHAINS:
        inputs = per_chain_inputs.get(chain)
        if inputs is None:
            continue
        selected = [
            (obs_date, close, volume)
            for obs_date, close, volume in zip(
                inputs.dates,
                inputs.closes,
                inputs.volumes,
                strict=True,
            )
            if obs_date <= cutoff
        ]
        if not selected:
            continue
        frame = build_feature_frame(
            [item[0] for item in selected],
            [item[1] for item in selected],
            [item[2] for item in selected],
        )
        labels = build_labels(frame, cutoff)
        for index, obs_date in enumerate(frame.dates):
            feature_values = frame.features[index]
            rv7_value = float(frame.rv7[index])
            rv30_value = float(frame.rv30[index])
            q80_value = float(frame.q80[index])
            forward_value = float(labels.rv30_fwd[index])
            if (
                int(labels.labels[index]) not in (0, 1)
                or not np.all(np.isfinite(feature_values))
                or not math.isfinite(rv7_value)
                or not math.isfinite(rv30_value)
                or not math.isfinite(q80_value)
                or not math.isfinite(forward_value)
                or rv7_value <= 0
                or rv30_value <= 0
                or float(frame.rv90[index]) <= 0
                or float(frame.volume_mean_30[index]) <= 0
                or float(frame.volume_mean_365[index]) <= 0
            ):
                continue
            rows.append(
                DatasetRow(
                    chain=chain,
                    obs_date=obs_date,
                    y=int(labels.labels[index]),
                    features=tuple(float(value) for value in feature_values),
                    rv7=rv7_value,
                    rv30=rv30_value,
                    q80=q80_value,
                    rv30_fwd=forward_value,
                )
            )
    rows.sort(key=lambda item: (item.chain, item.obs_date))
    return Dataset(rows=tuple(rows), sha256=_dataset_hash(rows, cutoff))


async def load_chain_inputs(session: AsyncSession) -> dict[str, ChainInputs]:
    result = await session.execute(
        select(
            Observation.chain_code,
            Observation.metric_code,
            Observation.obs_date,
            Observation.value,
        )
        .where(
            Observation.chain_code.in_(CHAINS),
            Observation.metric_code.in_(("price_close_usd", "volume_usd")),
            Observation.source_code == "binance",
        )
        .order_by(
            Observation.chain_code,
            Observation.metric_code,
            Observation.obs_date,
        )
    )
    values: dict[str, dict[str, dict[date, float]]] = {
        chain: {"price_close_usd": {}, "volume_usd": {}} for chain in CHAINS
    }
    for chain, metric, obs_date, decimal_value in result:
        if isinstance(decimal_value, Decimal):
            values[chain][metric][obs_date] = float(decimal_value)
        else:
            raise TypeError("database observation value must be Decimal")

    inputs: dict[str, ChainInputs] = {}
    for chain in CHAINS:
        prices = values[chain]["price_close_usd"]
        volumes = values[chain]["volume_usd"]
        all_dates = tuple(sorted(set(prices) | set(volumes)))
        inputs[chain] = ChainInputs(
            dates=all_dates,
            closes=tuple(prices.get(obs_date) for obs_date in all_dates),
            volumes=tuple(volumes.get(obs_date) for obs_date in all_dates),
        )
    return inputs


def make_folds(rows: Sequence[DatasetRow]) -> tuple[Fold, ...]:
    if not rows:
        return ()
    ordered = sorted(
        enumerate(rows),
        key=lambda item: (item[1].chain, item[1].obs_date),
    )
    first_eligible = min(row.obs_date for _, row in ordered)
    last_eligible = max(row.obs_date for _, row in ordered)
    first_test_start = first_eligible + timedelta(days=730)
    folds: list[Fold] = []
    fold_index = 0
    while first_test_start + timedelta(days=90 * fold_index) <= last_eligible:
        test_start = first_test_start + timedelta(days=90 * fold_index)
        test_end = min(
            test_start + timedelta(days=90),
            last_eligible + timedelta(days=1),
        )
        train_cutoff = test_start - timedelta(days=31)
        train_indices = tuple(
            original_index
            for original_index, row in ordered
            if row.obs_date <= train_cutoff
        )
        test_indices = tuple(
            original_index
            for original_index, row in ordered
            if test_start <= row.obs_date < test_end
        )
        if test_indices:
            folds.append(
                Fold(
                    index=len(folds),
                    test_start=test_start,
                    test_end_exclusive=test_end,
                    train_cutoff=train_cutoff,
                    train_indices=train_indices,
                    test_indices=test_indices,
                )
            )
        fold_index += 1
    return tuple(folds)


def positive_counts(rows: Sequence[DatasetRow]) -> dict[str, tuple[int, int]]:
    counts: dict[str, tuple[int, int]] = {}
    for chain in CHAINS:
        chain_rows = [row for row in rows if row.chain == chain]
        counts[chain] = (
            len(chain_rows),
            sum(row.y for row in chain_rows),
        )
    return counts
