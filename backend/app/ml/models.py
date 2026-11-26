from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.baselines import laplace_probability

MODEL_NAMES = ("M1", "M2", "M3")
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int8]


@dataclass(frozen=True)
class ModelFoldPrediction:
    probabilities: FloatArray
    used_single_class_fallback: bool
    convergence_warnings: int


def _pipeline(model_name: str) -> Pipeline:
    if model_name == "M1":
        estimator = LogisticRegression(
            penalty="l2",
            C=1.0,
            max_iter=1000,
            random_state=12345,
        )
    elif model_name == "M2":
        estimator = HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.05,
            max_iter=200,
            early_stopping=False,
            random_state=12345,
        )
    elif model_name == "M3":
        estimator = MLPClassifier(
            hidden_layer_sizes=(16,),
            alpha=0.01,
            max_iter=500,
            early_stopping=False,
            random_state=12345,
        )
    else:
        raise ValueError(f"unknown model: {model_name}")
    return make_pipeline(StandardScaler(), estimator)


def fit_predict_fold(
    model_name: str,
    train_features: FloatArray,
    train_labels: IntArray,
    test_features: FloatArray,
) -> ModelFoldPrediction:
    unique_labels = np.unique(train_labels)
    if unique_labels.size == 0:
        raise ValueError("model training requires at least one label")
    if unique_labels.size == 1:
        rate = laplace_probability([int(value) for value in train_labels])
        return ModelFoldPrediction(
            probabilities=np.full(len(test_features), rate, dtype=np.float64),
            used_single_class_fallback=True,
            convergence_warnings=0,
        )

    model = _pipeline(model_name)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(train_features, train_labels)
    probabilities = model.predict_proba(test_features)[:, 1]
    warning_count = sum(
        issubclass(item.category, ConvergenceWarning) for item in caught
    )
    return ModelFoldPrediction(
        probabilities=np.asarray(probabilities, dtype=np.float64),
        used_single_class_fallback=False,
        convergence_warnings=warning_count,
    )
