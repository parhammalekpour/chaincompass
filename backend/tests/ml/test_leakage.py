from __future__ import annotations

import importlib.util
import os
from datetime import date, timedelta
from typing import Any

import pytest


def _research_import(name: str) -> Any:
    if os.getenv("CI", "").lower() == "true" and importlib.util.find_spec(name) is None:
        pytest.fail(f"required research dependency is missing in CI: {name}")
    return pytest.importorskip(name)


np = _research_import("numpy")
_research_import("sklearn")

from app.ml.dataset import ChainInputs, build_dataset, make_folds  # noqa: E402
from app.ml.leakage import (  # noqa: E402
    passed_canary_check,
    passed_permutation_check,
    run_leakage_checks,
)


def _garch_inputs(length: int, seed: int) -> ChainInputs:
    rng = np.random.default_rng(seed)
    shocks = rng.normal(size=length)
    returns = np.zeros(length, dtype=np.float64)
    variance = np.full(length, 0.00002, dtype=np.float64)
    for index in range(1, length):
        variance[index] = (
            0.000002 + 0.12 * returns[index - 1] ** 2 + 0.85 * variance[index - 1]
        )
        returns[index] = np.sqrt(variance[index]) * shocks[index]
    closes = 100.0 * np.exp(np.cumsum(returns))
    volumes = np.exp(12.0 + rng.normal(0.0, 0.35, size=length))
    first = date(2012, 1, 1)
    dates = tuple(first + timedelta(days=index) for index in range(length))
    return ChainInputs(
        dates=dates,
        closes=tuple(float(value) for value in closes),
        volumes=tuple(float(value) for value in volumes),
    )


def test_synthetic_permutation_and_canary_checks_pass() -> None:
    inputs = {
        "btc": _garch_inputs(2250, 12345),
        "eth": _garch_inputs(1620, 67890),
    }
    dataset = build_dataset(inputs, date(2018, 2, 28))
    folds = make_folds(dataset.rows)
    results = run_leakage_checks(
        dataset,
        folds,
        permutation_seeds=tuple(range(12345, 12351)),
    )

    assert len(results.permutation_aucs) == 6
    assert passed_permutation_check(results)
    assert passed_canary_check(results)
