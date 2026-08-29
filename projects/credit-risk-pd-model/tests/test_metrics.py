import numpy as np

from credit_risk_pd.metrics import calibration_table, classification_metrics, gini_from_auc, ks_statistic


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

    assert set(["accounts", "predicted_pd", "observed_default_rate"]).issubset(table.columns)
    assert table["accounts"].sum() == 10

