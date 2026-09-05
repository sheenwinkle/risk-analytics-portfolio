from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from model_validation.metrics import ks_statistic, roc_auc_score

DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_MINIMUM_GROUP_OBSERVATIONS = 30
DEFAULT_MINIMUM_CLASS_COUNT = 5
SEGMENT_COLUMNS = ("home_ownership", "purpose")


def build_metric_uncertainty(
    predictions: pd.DataFrame,
    *,
    selected_model: str,
    score_column: str,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> pd.DataFrame:
    """Build deterministic confidence intervals for key portfolio validation metrics."""
    _validate_confidence_level(confidence_level)
    actual, scores = _validated_arrays(predictions, score_column)
    observations = len(actual)
    defaults = int(actual.sum())

    auc, auc_lower, auc_upper = _delong_auc_interval(
        actual,
        scores,
        confidence_level,
    )
    observed_rate, observed_lower, observed_upper = _wilson_interval(
        defaults,
        observations,
        confidence_level,
    )
    mean_pd, mean_pd_lower, mean_pd_upper = _normal_mean_interval(
        scores,
        confidence_level,
        lower_limit=0.0,
        upper_limit=1.0,
    )
    gap, gap_lower, gap_upper = _normal_mean_interval(
        scores - actual,
        confidence_level,
        lower_limit=-1.0,
        upper_limit=1.0,
    )
    brier, brier_lower, brier_upper = _normal_mean_interval(
        (scores - actual) ** 2,
        confidence_level,
        lower_limit=0.0,
        upper_limit=1.0,
    )

    rows = (
        ("roc_auc", auc, auc_lower, auc_upper, "delong"),
        (
            "observed_default_rate",
            observed_rate,
            observed_lower,
            observed_upper,
            "wilson_score",
        ),
        ("mean_predicted_pd", mean_pd, mean_pd_lower, mean_pd_upper, "normal_mean"),
        ("calibration_gap", gap, gap_lower, gap_upper, "paired_normal"),
        ("brier_score", brier, brier_lower, brier_upper, "normal_mean"),
    )
    return pd.DataFrame(
        [
            {
                "model_name": selected_model,
                "score_version": "recalibrated",
                "metric": metric,
                "estimate": estimate,
                "lower_bound": lower,
                "upper_bound": upper,
                "confidence_level": confidence_level,
                "method": method,
                "observations": observations,
                "defaults": defaults,
            }
            for metric, estimate, lower, upper, method in rows
        ]
    )


def build_vintage_performance(
    predictions: pd.DataFrame,
    *,
    selected_model: str,
    score_column: str,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    minimum_group_observations: int = DEFAULT_MINIMUM_GROUP_OBSERVATIONS,
    minimum_class_count: int = DEFAULT_MINIMUM_CLASS_COUNT,
) -> pd.DataFrame:
    """Backtest discrimination and calibration by origination quarter."""
    _validate_group_configuration(
        confidence_level,
        minimum_group_observations,
        minimum_class_count,
    )
    _require_columns(predictions, {"observation_date", "actual_default", score_column})
    working = predictions.copy()
    dates = pd.to_datetime(working["observation_date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("observation_date must contain parseable dates")
    working["vintage_quarter"] = dates.dt.to_period("Q").astype(str)
    rows = _build_group_rows(
        working,
        group_column="vintage_quarter",
        score_column=score_column,
        confidence_level=confidence_level,
        minimum_group_observations=minimum_group_observations,
        minimum_class_count=minimum_class_count,
    )
    return pd.DataFrame(
        [
            {
                "model_name": selected_model,
                "score_version": "recalibrated",
                "vintage_quarter": group_value,
                **metrics,
            }
            for group_value, metrics in rows
        ]
    )


def build_segment_performance(
    predictions: pd.DataFrame,
    *,
    selected_model: str,
    score_column: str,
    segment_columns: tuple[str, ...] = SEGMENT_COLUMNS,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    minimum_group_observations: int = DEFAULT_MINIMUM_GROUP_OBSERVATIONS,
    minimum_class_count: int = DEFAULT_MINIMUM_CLASS_COUNT,
) -> pd.DataFrame:
    """Backtest discrimination and calibration across non-sensitive business segments."""
    _validate_group_configuration(
        confidence_level,
        minimum_group_observations,
        minimum_class_count,
    )
    if not segment_columns:
        raise ValueError("segment_columns must contain at least one column")
    _require_columns(
        predictions,
        {"actual_default", score_column, *segment_columns},
    )

    rows = []
    for dimension in segment_columns:
        working = predictions.copy()
        working[dimension] = (
            working[dimension].astype("string").fillna("missing").str.strip().replace("", "missing")
        )
        for group_value, metrics in _build_group_rows(
            working,
            group_column=dimension,
            score_column=score_column,
            confidence_level=confidence_level,
            minimum_group_observations=minimum_group_observations,
            minimum_class_count=minimum_class_count,
        ):
            rows.append(
                {
                    "model_name": selected_model,
                    "score_version": "recalibrated",
                    "segment_dimension": dimension,
                    "segment_value": group_value,
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def _build_group_rows(
    predictions: pd.DataFrame,
    *,
    group_column: str,
    score_column: str,
    confidence_level: float,
    minimum_group_observations: int,
    minimum_class_count: int,
) -> list[tuple[str, dict[str, object]]]:
    total_observations = len(predictions)
    rows = []
    for group_value, group in predictions.groupby(group_column, sort=True, dropna=False):
        actual, scores = _validated_arrays(group, score_column)
        observations = len(group)
        defaults = int(actual.sum())
        non_defaults = observations - defaults
        expected_defaults = float(scores.sum())
        mean_pd = float(scores.mean())
        observed_rate, observed_lower, observed_upper = _wilson_interval(
            defaults,
            observations,
            confidence_level,
        )
        gap, gap_lower, gap_upper = _normal_mean_interval(
            scores - actual,
            confidence_level,
            lower_limit=-1.0,
            upper_limit=1.0,
        )
        has_both_classes = defaults > 0 and non_defaults > 0
        if has_both_classes:
            auc, auc_lower, auc_upper = _delong_auc_interval(
                actual,
                scores,
                confidence_level,
            )
            ks = ks_statistic(actual, scores)
            discrimination_status = "available"
        else:
            auc = auc_lower = auc_upper = ks = math.nan
            discrimination_status = "not_available_single_class"

        sufficient = (
            observations >= minimum_group_observations
            and defaults >= minimum_class_count
            and non_defaults >= minimum_class_count
        )
        rows.append(
            (
                str(group_value),
                {
                    "observations": observations,
                    "portfolio_share": observations / total_observations,
                    "defaults": defaults,
                    "non_defaults": non_defaults,
                    "expected_defaults": expected_defaults,
                    "mean_pd": mean_pd,
                    "observed_default_rate": observed_rate,
                    "observed_default_rate_lower": observed_lower,
                    "observed_default_rate_upper": observed_upper,
                    "calibration_gap": gap,
                    "calibration_gap_lower": gap_lower,
                    "calibration_gap_upper": gap_upper,
                    "expected_to_observed_ratio": (
                        expected_defaults / defaults if defaults else math.nan
                    ),
                    "roc_auc": auc,
                    "roc_auc_lower": auc_lower,
                    "roc_auc_upper": auc_upper,
                    "ks": ks,
                    "discrimination_status": discrimination_status,
                    "reliability_status": (
                        "sufficient" if sufficient else "limited_sample"
                    ),
                    "calibration_signal": _calibration_signal(gap_lower, gap_upper),
                },
            )
        )
    return rows


def _validated_arrays(
    predictions: pd.DataFrame,
    score_column: str,
) -> tuple[np.ndarray, np.ndarray]:
    _require_columns(predictions, {"actual_default", score_column})
    if predictions.empty:
        raise ValueError("predictions must contain at least one row")
    actual = pd.to_numeric(predictions["actual_default"], errors="coerce")
    scores = pd.to_numeric(predictions[score_column], errors="coerce")
    if actual.isna().any() or not actual.isin([0, 1]).all():
        raise ValueError("actual_default must contain only binary 0/1 values")
    if scores.isna().any() or not np.isfinite(scores.to_numpy(dtype=float)).all():
        raise ValueError(f"{score_column} must contain finite numeric values")
    if not scores.between(0, 1).all():
        raise ValueError(f"{score_column} must contain PD values between 0 and 1")
    return actual.to_numpy(dtype=int), scores.to_numpy(dtype=float)


def _delong_auc_interval(
    actual: np.ndarray,
    scores: np.ndarray,
    confidence_level: float,
) -> tuple[float, float, float]:
    positives = scores[actual == 1]
    negatives = scores[actual == 0]
    if len(positives) == 0 or len(negatives) == 0:
        raise ValueError("ROC-AUC confidence interval requires both default classes")

    auc = roc_auc_score(actual, scores)
    if len(positives) < 2 or len(negatives) < 2:
        return auc, math.nan, math.nan

    positive_ranks = _midranks(positives)
    negative_ranks = _midranks(negatives)
    combined_ranks = _midranks(np.concatenate([positives, negatives]))
    positive_components = (combined_ranks[: len(positives)] - positive_ranks) / len(
        negatives
    )
    negative_components = 1 - (
        combined_ranks[len(positives) :] - negative_ranks
    ) / len(positives)
    variance = float(
        np.var(positive_components, ddof=1) / len(positives)
        + np.var(negative_components, ddof=1) / len(negatives)
    )
    standard_error = math.sqrt(max(variance, 0.0))
    margin = _z_value(confidence_level) * standard_error
    return auc, max(0.0, auc - margin), min(1.0, auc + margin)


def _midranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ordered_values = values[order]
    ordered_ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and ordered_values[end] == ordered_values[start]:
            end += 1
        ordered_ranks[start:end] = 0.5 * (start + end - 1) + 1
        start = end
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = ordered_ranks
    return ranks


def _wilson_interval(
    successes: int,
    observations: int,
    confidence_level: float,
) -> tuple[float, float, float]:
    estimate = successes / observations
    z = _z_value(confidence_level)
    z_squared = z**2
    denominator = 1 + z_squared / observations
    centre = (estimate + z_squared / (2 * observations)) / denominator
    margin = (
        z
        * math.sqrt(
            estimate * (1 - estimate) / observations
            + z_squared / (4 * observations**2)
        )
        / denominator
    )
    return estimate, max(0.0, centre - margin), min(1.0, centre + margin)


def _normal_mean_interval(
    values: np.ndarray,
    confidence_level: float,
    *,
    lower_limit: float,
    upper_limit: float,
) -> tuple[float, float, float]:
    estimate = float(np.mean(values))
    if len(values) < 2:
        return estimate, math.nan, math.nan
    standard_error = float(np.std(values, ddof=1) / math.sqrt(len(values)))
    margin = _z_value(confidence_level) * standard_error
    return (
        estimate,
        max(lower_limit, estimate - margin),
        min(upper_limit, estimate + margin),
    )


def _calibration_signal(lower_bound: float, upper_bound: float) -> str:
    if not math.isfinite(lower_bound) or not math.isfinite(upper_bound):
        return "not_available"
    if lower_bound > 0:
        return "pd_overprediction"
    if upper_bound < 0:
        return "pd_underprediction"
    return "not_statistically_distinct"


def _validate_group_configuration(
    confidence_level: float,
    minimum_group_observations: int,
    minimum_class_count: int,
) -> None:
    _validate_confidence_level(confidence_level)
    if minimum_group_observations < 1:
        raise ValueError("minimum_group_observations must be at least 1")
    if minimum_class_count < 1:
        raise ValueError("minimum_class_count must be at least 1")


def _validate_confidence_level(confidence_level: float) -> None:
    if not isinstance(confidence_level, (int, float)) or not math.isfinite(
        confidence_level
    ):
        raise ValueError("confidence_level must be a finite number between 0 and 1")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")


def _z_value(confidence_level: float) -> float:
    return NormalDist().inv_cdf(0.5 + confidence_level / 2)


def _require_columns(predictions: pd.DataFrame, required: set[str]) -> None:
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError("Predictions missing diagnostic columns: " + ", ".join(missing))
