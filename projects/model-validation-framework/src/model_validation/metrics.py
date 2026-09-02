from __future__ import annotations

import numpy as np
import pandas as pd

RAW_SCORE_COLUMNS = {
    "logistic_regression": "logistic_regression_pd",
    "random_forest": "random_forest_pd",
}
PD_SCORE_COLUMNS = (*RAW_SCORE_COLUMNS.values(), "recalibrated_pd")


def build_model_metrics(predictions: pd.DataFrame, *, selected_model: str) -> pd.DataFrame:
    actual = predictions["actual_default"].to_numpy(dtype=int)
    rows = []
    score_definitions = (
        ("logistic_regression", "raw", "logistic_regression_pd"),
        (selected_model, "recalibrated", "recalibrated_pd"),
        ("random_forest", "raw", "random_forest_pd"),
    )
    for model_name, score_version, score_column in score_definitions:
        scores = predictions[score_column].to_numpy(dtype=float)
        observed_default_rate = float(actual.mean())
        mean_predicted_pd = float(scores.mean())
        roc_auc = roc_auc_score(actual, scores)
        rows.append(
            {
                "model_name": model_name,
                "score_version": score_version,
                "score_column": score_column,
                "observations": len(actual),
                "defaults": int(actual.sum()),
                "observed_default_rate": observed_default_rate,
                "mean_predicted_pd": mean_predicted_pd,
                "calibration_gap": mean_predicted_pd - observed_default_rate,
                "absolute_calibration_gap": abs(mean_predicted_pd - observed_default_rate),
                "roc_auc": roc_auc,
                "gini": 2 * roc_auc - 1,
                "ks": ks_statistic(actual, scores),
                "brier_score": float(np.mean((scores - actual) ** 2)),
            }
        )
    return pd.DataFrame(rows)


def roc_auc_score(actual: np.ndarray, scores: np.ndarray) -> float:
    positives = actual == 1
    negatives = actual == 0
    positive_count = int(positives.sum())
    negative_count = int(negatives.sum())

    ranks = pd.Series(scores).rank(method="average").to_numpy(dtype=float)
    positive_rank_sum = float(ranks[positives].sum())
    return (positive_rank_sum - positive_count * (positive_count + 1) / 2) / (
        positive_count * negative_count
    )


def ks_statistic(actual: np.ndarray, scores: np.ndarray) -> float:
    positives = actual == 1
    negatives = actual == 0
    positive_count = int(positives.sum())
    negative_count = int(negatives.sum())

    grouped = (
        pd.DataFrame({"actual": actual, "score": scores})
        .groupby("score", as_index=False)
        .agg(defaults=("actual", "sum"), observations=("actual", "size"))
        .sort_values("score", ascending=False, kind="mergesort")
    )
    non_defaults = grouped["observations"] - grouped["defaults"]
    cumulative_defaults = grouped["defaults"].cumsum() / positive_count
    cumulative_non_defaults = non_defaults.cumsum() / negative_count
    return float(np.max(np.abs(cumulative_defaults - cumulative_non_defaults)))
