from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

WOE_SIGN_CONVENTION = (
    "WOE is ln(% good / % bad), where good is non-default and bad is default. "
    "Positive WOE indicates lower observed default risk than the development sample mix."
)


def calculate_woe_iv(
    features: pd.DataFrame,
    target: pd.Series,
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    *,
    numeric_bins: int = 5,
    smoothing: float = 0.5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate scorecard-style Weight of Evidence bins and feature Information Value.

    The target must be binary with 1 representing default ("bad") and 0 representing
    non-default ("good"). Numeric features use quantile bins fitted on this sample;
    categorical features use one bin per observed category. Good and bad counts are
    additively smoothed per bin so zero-good or zero-bad bins produce finite WOE.
    """
    if numeric_bins < 2:
        raise ValueError("numeric_bins must be at least 2")
    if not np.isfinite(smoothing) or smoothing <= 0:
        raise ValueError("smoothing must be greater than 0")

    if len(features) != len(target):
        raise ValueError("features and target must contain the same number of rows")
    if not features.columns.is_unique:
        raise ValueError("features must have unique column names")

    selected_features = [*numeric_features, *categorical_features]
    if not selected_features:
        raise ValueError("at least one numeric or categorical feature is required")
    if len(selected_features) != len(set(selected_features)):
        raise ValueError("numeric and categorical feature lists must not contain duplicates")

    missing_features = [feature for feature in selected_features if feature not in features.columns]
    if missing_features:
        raise ValueError(f"features are missing required columns: {', '.join(missing_features)}")

    y_numeric = pd.to_numeric(target.reset_index(drop=True), errors="coerce")
    if y_numeric.isna().any() or not set(y_numeric.unique()).issubset({0, 1}):
        raise ValueError("target must contain only 0 and 1 values with no missing values")
    if set(y_numeric.unique()) != {0, 1}:
        raise ValueError("target must contain both 0 and 1 classes")
    y = y_numeric.astype(int)

    x = features.reset_index(drop=True)
    bin_frames: list[pd.DataFrame] = []

    for feature in numeric_features:
        assigned, bin_spec = _assign_numeric_bins(x[feature], numeric_bins)
        bin_frames.append(
            _summarise_feature_bins(feature, "numeric", assigned, y, bin_spec, smoothing)
        )

    for feature in categorical_features:
        assigned, bin_spec = _assign_categorical_bins(x[feature])
        bin_frames.append(
            _summarise_feature_bins(feature, "categorical", assigned, y, bin_spec, smoothing)
        )

    bins = pd.concat(bin_frames, ignore_index=True)
    summary = (
        bins.groupby(["feature", "feature_type"], as_index=False)
        .agg(bins=("bin", "count"), information_value=("iv", "sum"))
        .sort_values(["information_value", "feature"], ascending=[False, True])
        .reset_index(drop=True)
    )
    summary.insert(0, "rank", range(1, len(summary) + 1))
    summary["iv_band"] = summary["information_value"].map(_iv_band)
    return bins, summary


def _assign_numeric_bins(series: pd.Series, numeric_bins: int) -> tuple[pd.Series, pd.DataFrame]:
    numeric = pd.to_numeric(series, errors="coerce")
    assigned = pd.Series("Missing", index=series.index, dtype=object)
    non_missing = numeric.dropna()
    specs: list[dict[str, object]] = []

    if not non_missing.empty:
        if non_missing.nunique() == 1:
            value = float(non_missing.iloc[0])
            label = _format_closed_bin(value, value)
            assigned.loc[non_missing.index] = label
            specs.append(
                {
                    "bin": label,
                    "bin_order": 1,
                    "min_value": value,
                    "max_value": value,
                }
            )
        else:
            cut = pd.qcut(
                non_missing,
                q=min(numeric_bins, non_missing.nunique()),
                duplicates="drop",
            )
            intervals = list(cut.cat.categories)
            labels = {}
            for order, interval in enumerate(intervals, start=1):
                values_in_bin = non_missing.loc[cut == interval]
                lower = float(values_in_bin.min())
                upper = float(values_in_bin.max())
                label_lower = lower if order == 1 else float(interval.left)
                label_upper = float(interval.right)
                labels[interval] = _format_interval_bin(
                    label_lower,
                    label_upper,
                    include_lower=(order == 1),
                )
                specs.append(
                    {
                        "bin": labels[interval],
                        "bin_order": order,
                        "min_value": lower,
                        "max_value": upper,
                    }
                )
            assigned.loc[non_missing.index] = cut.map(labels).astype(object)

    if numeric.isna().any():
        specs.append(
            {
                "bin": "Missing",
                "bin_order": len(specs) + 1,
                "min_value": np.nan,
                "max_value": np.nan,
            }
        )

    return assigned, pd.DataFrame(specs)


def _assign_categorical_bins(series: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    assigned = series.astype("string").fillna("Missing").astype(object)
    categories = sorted(assigned.unique(), key=str)
    specs = pd.DataFrame(
        {
            "bin": category,
            "bin_order": order,
            "min_value": np.nan,
            "max_value": np.nan,
        }
        for order, category in enumerate(categories, start=1)
    )
    return assigned, specs


def _summarise_feature_bins(
    feature: str,
    feature_type: str,
    assigned_bins: pd.Series,
    target: pd.Series,
    bin_spec: pd.DataFrame,
    smoothing: float,
) -> pd.DataFrame:
    frame = pd.DataFrame({"bin": assigned_bins, "target": target})
    counts = (
        frame.groupby("bin", dropna=False)["target"]
        .agg(total="count", bads="sum")
        .reset_index()
    )
    counts["goods"] = counts["total"] - counts["bads"]

    result = bin_spec.merge(counts, on="bin", how="left").fillna(
        {"total": 0, "bads": 0, "goods": 0}
    )
    result[["total", "bads", "goods"]] = result[["total", "bads", "goods"]].astype(int)
    result["smoothed_goods"] = result["goods"] + smoothing
    result["smoothed_bads"] = result["bads"] + smoothing
    result["dist_good"] = result["smoothed_goods"] / result["smoothed_goods"].sum()
    result["dist_bad"] = result["smoothed_bads"] / result["smoothed_bads"].sum()
    result["woe"] = np.log(result["dist_good"] / result["dist_bad"])
    result["iv"] = (result["dist_good"] - result["dist_bad"]) * result["woe"]
    result["bad_rate"] = np.where(result["total"] > 0, result["bads"] / result["total"], 0.0)

    result.insert(0, "feature_type", feature_type)
    result.insert(0, "feature", feature)
    return result[
        [
            "feature",
            "feature_type",
            "bin_order",
            "bin",
            "min_value",
            "max_value",
            "total",
            "goods",
            "bads",
            "bad_rate",
            "dist_good",
            "dist_bad",
            "woe",
            "iv",
        ]
    ]


def _format_interval_bin(left_value: float, right_value: float, include_lower: bool) -> str:
    left = _format_number(left_value)
    right = _format_number(right_value)
    left_bracket = "[" if include_lower else "("
    return f"{left_bracket}{left}, {right}]"


def _format_closed_bin(left: float, right: float) -> str:
    return f"[{_format_number(left)}, {_format_number(right)}]"


def _format_number(value: float) -> str:
    if abs(value) >= 1_000:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _iv_band(value: float) -> str:
    if value < 0.02:
        return "not_predictive"
    if value < 0.10:
        return "weak"
    if value < 0.30:
        return "medium"
    if value < 0.50:
        return "strong"
    return "very_strong_review"
