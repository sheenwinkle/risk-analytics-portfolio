import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from credit_risk_pd.metrics import (
    calibration_table,
    classification_metrics,
    gini_from_auc,
    ks_statistic,
    permutation_feature_importance,
)


def test_gini_from_auc():
    assert gini_from_auc(0.75) == 0.5


def test_ks_statistic_is_positive_for_ranked_scores():
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_score = np.array([0.05, 0.10, 0.20, 0.70, 0.80, 0.90])

    assert ks_statistic(y_true, y_score) == 1.0


def test_classification_metrics_contains_risk_model_metrics():
    y_true = np.array([0, 0, 1, 1])
    y_score = np.array([0.1, 0.2, 0.8, 0.9])

    metrics = classification_metrics(y_true, y_score)

    assert metrics["roc_auc"] == 1.0
    assert metrics["gini"] == 1.0
    assert metrics["ks"] == 1.0
    assert "brier_score" in metrics


def test_calibration_table_returns_bins():
    y_true = np.array([0, 0, 0, 1, 1, 1, 0, 1, 0, 1])
    y_score = np.linspace(0.05, 0.95, 10)

    table = calibration_table(y_true, y_score, n_bins=5)

    assert {"accounts", "predicted_pd", "observed_default_rate"}.issubset(table.columns)
    assert table["accounts"].sum() == 10
    assert table["bucket"].tolist() == ["D01", "D02", "D03", "D04", "D05"]


def test_permutation_feature_importance_ranks_predictive_feature_first():
    x = pd.DataFrame(
        {
            "predictive": [0, 0, 0, 0, 1, 1, 1, 1],
            "noise": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    estimator = LogisticRegression().fit(x, y)

    importance = permutation_feature_importance(
        estimator,
        x,
        y,
        n_repeats=5,
        random_state=7,
    )

    assert list(importance.columns) == ["feature", "importance_mean", "importance_std"]
    assert importance.iloc[0]["feature"] == "predictive"
    assert importance.iloc[0]["importance_mean"] > importance.iloc[1]["importance_mean"]

