from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
LabelArray = NDArray[np.int8]


@dataclass(frozen=True)
class BlockSamples:
    block_length: int
    starts: IntArray
    date_indices: IntArray


@dataclass(frozen=True)
class BootstrapInterval:
    lower: float
    upper: float
    mean_difference: float
    resamples: int


def moving_block_samples(
    n_dates: int,
    block_length: int,
    *,
    resamples: int = 2000,
    seed: int = 12345,
) -> BlockSamples:
    if n_dates <= 0 or block_length <= 0 or block_length > n_dates:
        raise ValueError("block length must be between 1 and the number of dates")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    blocks_per_sample = math.ceil(n_dates / block_length)
    rng = np.random.default_rng(seed)
    starts = rng.integers(
        0,
        n_dates - block_length + 1,
        size=(resamples, blocks_per_sample),
        dtype=np.int64,
    )
    offsets = np.arange(block_length, dtype=np.int64)
    full_samples = (starts[:, :, None] + offsets).reshape(resamples, -1)
    date_indices = full_samples[:, :n_dates]
    return BlockSamples(
        block_length=block_length,
        starts=starts,
        date_indices=date_indices,
    )


def paired_brier_intervals(
    labels: LabelArray,
    date_ids: IntArray,
    probabilities: Mapping[str, FloatArray],
    pairs: Sequence[tuple[str, str]],
    samples: BlockSamples,
    *,
    total_alpha: float = 0.05 / 3.0,
) -> dict[tuple[str, str], BootstrapInterval]:
    y = np.asarray(labels, dtype=np.int8)
    date_indices = np.asarray(date_ids, dtype=np.int64)
    if y.ndim != 1 or date_indices.ndim != 1 or len(y) != len(date_indices):
        raise ValueError("labels and date ids must be aligned one-dimensional arrays")
    n_dates = samples.date_indices.shape[1]
    if len(y) == 0 or np.any(date_indices < 0) or np.any(date_indices >= n_dates):
        raise ValueError("row date ids must reference the sampled date range")
    if not 0 < total_alpha < 1:
        raise ValueError("total alpha must be between zero and one")

    multiplicities = np.stack(
        [np.bincount(sample, minlength=n_dates) for sample in samples.date_indices],
        axis=0,
    ).astype(np.float64)
    row_counts = np.bincount(date_indices, minlength=n_dates).astype(np.float64)
    denominators = multiplicities @ row_counts
    if np.any(denominators == 0):
        raise ValueError("a bootstrap sample contains no evaluation rows")

    result: dict[tuple[str, str], BootstrapInterval] = {}
    for model_name, comparator_name in pairs:
        model_probabilities = np.asarray(
            probabilities[model_name],
            dtype=np.float64,
        )
        comparator_probabilities = np.asarray(
            probabilities[comparator_name],
            dtype=np.float64,
        )
        if (
            model_probabilities.shape != y.shape
            or comparator_probabilities.shape != y.shape
        ):
            raise ValueError("all probability arrays must align with labels")
        model_daily_errors = np.bincount(
            date_indices,
            weights=(model_probabilities - y) ** 2,
            minlength=n_dates,
        )
        comparator_daily_errors = np.bincount(
            date_indices,
            weights=(comparator_probabilities - y) ** 2,
            minlength=n_dates,
        )
        model_brier = (multiplicities @ model_daily_errors) / denominators
        comparator_brier = (multiplicities @ comparator_daily_errors) / denominators
        differences = model_brier - comparator_brier
        lower, upper = np.quantile(
            differences,
            [total_alpha / 2.0, 1.0 - total_alpha / 2.0],
        )
        result[(model_name, comparator_name)] = BootstrapInterval(
            lower=float(lower),
            upper=float(upper),
            mean_difference=float(np.mean(differences)),
            resamples=len(differences),
        )
    return result
