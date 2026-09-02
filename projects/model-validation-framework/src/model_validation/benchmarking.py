from __future__ import annotations

import pandas as pd

from model_validation.metrics import RAW_SCORE_COLUMNS


def build_benchmark_comparison(
    model_metrics: pd.DataFrame,
    *,
    selected_model: str,
) -> pd.DataFrame:
    challenger_model = _challenger_model(selected_model)
    selected_raw = _metric_row(model_metrics, selected_model, "raw")
    selected_recalibrated = _metric_row(model_metrics, selected_model, "recalibrated")
    challenger_raw = _metric_row(model_metrics, challenger_model, "raw")

    rows = [
        _comparison_row(
            comparison="selected_recalibrated_vs_unselected_raw_challenger",
            baseline=selected_recalibrated,
            benchmark=challenger_raw,
        ),
        _comparison_row(
            comparison="selected_raw_vs_selected_recalibrated",
            baseline=selected_raw,
            benchmark=selected_recalibrated,
        ),
    ]
    return pd.DataFrame(rows)


def _comparison_row(
    *,
    comparison: str,
    baseline: pd.Series,
    benchmark: pd.Series,
) -> dict[str, float | str]:
    return {
        "comparison": comparison,
        "baseline_model": baseline["model_name"],
        "baseline_score_version": baseline["score_version"],
        "baseline_score_column": baseline["score_column"],
        "benchmark_model": benchmark["model_name"],
        "benchmark_score_version": benchmark["score_version"],
        "benchmark_score_column": benchmark["score_column"],
        "baseline_auc": float(baseline["roc_auc"]),
        "benchmark_auc": float(benchmark["roc_auc"]),
        "auc_delta": float(benchmark["roc_auc"] - baseline["roc_auc"]),
        "baseline_ks": float(baseline["ks"]),
        "benchmark_ks": float(benchmark["ks"]),
        "ks_delta": float(benchmark["ks"] - baseline["ks"]),
        "baseline_absolute_calibration_gap": float(baseline["absolute_calibration_gap"]),
        "benchmark_absolute_calibration_gap": float(benchmark["absolute_calibration_gap"]),
        "absolute_calibration_gap_delta": float(
            benchmark["absolute_calibration_gap"] - baseline["absolute_calibration_gap"]
        ),
        "baseline_brier_score": float(baseline["brier_score"]),
        "benchmark_brier_score": float(benchmark["brier_score"]),
        "brier_score_delta": float(benchmark["brier_score"] - baseline["brier_score"]),
    }


def _metric_row(model_metrics: pd.DataFrame, model_name: str, score_version: str) -> pd.Series:
    matched = model_metrics[
        model_metrics["model_name"].eq(model_name)
        & model_metrics["score_version"].eq(score_version)
    ]
    return matched.iloc[0]


def _challenger_model(selected_model: str) -> str:
    return next(model for model in RAW_SCORE_COLUMNS if model != selected_model)
