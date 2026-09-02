from __future__ import annotations

import numpy as np
import pandas as pd

from model_validation.metrics import ks_statistic, roc_auc_score


def build_calibration_by_decile(
    predictions: pd.DataFrame,
    *,
    selected_model: str,
    score_column: str,
) -> pd.DataFrame:
    scored = predictions.loc[
        :, ["customer_id", "actual_default", score_column]
    ].copy()
    scored["decile"] = assign_rank_deciles(
        scored[score_column],
        tie_breaker=scored["customer_id"],
    )

    rows = []
    for decile, group in scored.groupby("decile", sort=True):
        rows.append(_performance_row(group, selected_model, "recalibrated", score_column, decile))
    return pd.DataFrame(rows)


def build_monthly_performance(
    predictions: pd.DataFrame,
    *,
    selected_model: str,
    score_column: str,
) -> pd.DataFrame:
    scored = predictions.loc[:, ["observation_date", "actual_default", score_column]].copy()
    scored["period"] = scored["observation_date"].dt.strftime("%Y-%m")

    rows = []
    for period, group in scored.groupby("period", sort=True):
        actual = group["actual_default"].to_numpy(dtype=int)
        scores = group[score_column].to_numpy(dtype=float)
        has_both_classes = len(set(actual.tolist())) == 2
        row = _performance_row(group, selected_model, "recalibrated", score_column, period)
        row["period"] = row.pop("decile")
        row["roc_auc"] = roc_auc_score(actual, scores) if has_both_classes else np.nan
        row["ks"] = ks_statistic(actual, scores) if has_both_classes else np.nan
        row["discrimination_status"] = (
            "available" if has_both_classes else "not_available_single_class"
        )
        rows.append(row)

    columns = [
        "model_name",
        "score_version",
        "period",
        "observations",
        "defaults",
        "expected_defaults",
        "mean_pd",
        "observed_default_rate",
        "calibration_gap",
        "expected_to_observed_ratio",
        "roc_auc",
        "ks",
        "discrimination_status",
    ]
    return pd.DataFrame(rows, columns=columns)


def assign_rank_deciles(
    scores: pd.Series,
    *,
    requested_bins: int = 10,
    tie_breaker: pd.Series | None = None,
) -> pd.Series:
    observations = len(scores)
    bins = min(requested_bins, observations)
    stable_tie_breaker = (
        np.arange(observations)
        if tie_breaker is None
        else tie_breaker.astype(str).to_numpy()
    )
    ordered = (
        pd.DataFrame(
            {
                "score": scores.to_numpy(dtype=float),
                "tie_breaker": stable_tie_breaker,
                "_index": np.arange(observations),
            }
        )
        .sort_values(["score", "tie_breaker", "_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    ordered["decile"] = np.floor(np.arange(observations) * bins / observations).astype(int) + 1
    deciles = pd.Series(index=ordered["_index"], data=ordered["decile"].to_numpy(dtype=int))
    return deciles.sort_index().reset_index(drop=True)


def _performance_row(
    group: pd.DataFrame,
    model_name: str,
    score_version: str,
    score_column: str,
    bucket: int | str,
) -> dict[str, float | int | str]:
    observations = len(group)
    defaults = int(group["actual_default"].sum())
    expected_defaults = float(group[score_column].sum())
    mean_pd = float(group[score_column].mean())
    observed_default_rate = defaults / observations
    return {
        "model_name": model_name,
        "score_version": score_version,
        "decile": bucket,
        "observations": observations,
        "defaults": defaults,
        "expected_defaults": expected_defaults,
        "mean_pd": mean_pd,
        "observed_default_rate": observed_default_rate,
        "calibration_gap": mean_pd - observed_default_rate,
        "expected_to_observed_ratio": expected_defaults / defaults if defaults else np.nan,
    }
