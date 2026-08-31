from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)


def gini_from_auc(auc: float) -> float:
    """Convert ROC-AUC to Gini coefficient."""
    return 2 * auc - 1


def ks_statistic(y_true: pd.Series | np.ndarray, y_score: pd.Series | np.ndarray) -> float:
    """Calculate the Kolmogorov-Smirnov statistic for binary default predictions."""
    frame = pd.DataFrame({"y_true": y_true, "y_score": y_score}).sort_values("y_score")
    goods = frame["y_true"].eq(0).sum()
    bads = frame["y_true"].eq(1).sum()
    if goods == 0 or bads == 0:
        raise ValueError("KS statistic requires both default and non-default observations.")

    frame["cum_good"] = frame["y_true"].eq(0).cumsum() / goods
    frame["cum_bad"] = frame["y_true"].eq(1).cumsum() / bads
    return float((frame["cum_bad"] - frame["cum_good"]).abs().max())


def classification_metrics(
    y_true: pd.Series | np.ndarray,
    y_score: pd.Series | np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Calculate discrimination, calibration, and threshold-based metrics."""
    y_pred = (np.asarray(y_score) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    auc = roc_auc_score(y_true, y_score)

    return {
        "roc_auc": float(auc),
        "gini": float(gini_from_auc(auc)),
        "ks": ks_statistic(y_true, y_score),
        "brier_score": float(brier_score_loss(y_true, y_score)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "true_negative": float(tn),
        "false_positive": float(fp),
        "false_negative": float(fn),
        "true_positive": float(tp),
    }


def calibration_table(
    y_true: pd.Series | np.ndarray,
    y_score: pd.Series | np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Create a decile calibration table comparing predicted PD to observed default rate."""
    frame = pd.DataFrame({"default": y_true, "pd": y_score})
    frame["bucket"] = pd.qcut(frame["pd"], q=n_bins, duplicates="drop")

    table = (
        frame.groupby("bucket", observed=True)
        .agg(
            accounts=("default", "size"),
            predicted_pd=("pd", "mean"),
            observed_default_rate=("default", "mean"),
            defaults=("default", "sum"),
        )
        .reset_index()
    )
    table["bucket"] = table["bucket"].astype(str)
    table["calibration_gap"] = table["predicted_pd"] - table["observed_default_rate"]
    return table


def permutation_feature_importance(
    estimator,
    x_oot: pd.DataFrame,
    y_oot: pd.Series | np.ndarray,
    scoring: str = "roc_auc",
    n_repeats: int = 10,
    random_state: int = 42,
) -> pd.DataFrame:
    """Calculate model-agnostic permutation importance on the out-of-time sample."""
    result = permutation_importance(
        estimator,
        x_oot,
        y_oot,
        scoring=scoring,
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=1,
    )

    return (
        pd.DataFrame(
            {
                "feature": x_oot.columns,
                "importance_mean": result.importances_mean,
                "importance_std": result.importances_std,
            }
        )
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )

