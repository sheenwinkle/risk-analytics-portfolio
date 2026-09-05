from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd

from model_validation.stability import split_observation_dates

NUMERIC_CHARACTERISTICS = (
    "age",
    "annual_income",
    "debt_to_income",
    "credit_utilisation",
    "delinquencies_2y",
    "loan_amount",
    "interest_rate",
    "employment_length",
    "loan_to_income",
)
CATEGORICAL_CHARACTERISTICS = ("home_ownership", "purpose")
MISSING_CATEGORY = "<MISSING>"


def build_characteristic_stability_tables(
    predictions: pd.DataFrame,
    *,
    numeric_features: tuple[str, ...] = NUMERIC_CHARACTERISTICS,
    categorical_features: tuple[str, ...] = CATEGORICAL_CHARACTERISTICS,
    requested_bins: int = 10,
    green_max: float = 0.10,
    warning_max: float = 0.25,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure numeric and categorical input drift across chronological OOT halves."""
    _validate_configuration(
        numeric_features,
        categorical_features,
        requested_bins,
        green_max,
        warning_max,
    )
    required = {"observation_date", *numeric_features, *categorical_features}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError("Predictions missing characteristic columns: " + ", ".join(missing))

    working = predictions.copy()
    dates = pd.to_datetime(working["observation_date"], errors="coerce", format="mixed")
    if dates.isna().any() or dates.nunique() < 2:
        raise ValueError("observation_date must contain at least two parseable dates")
    working["observation_date"] = dates.dt.normalize()
    reference_dates, current_dates = split_observation_dates(working["observation_date"])
    reference = working[working["observation_date"].isin(reference_dates)]
    current = working[working["observation_date"].isin(current_dates)]
    period = {
        "reference_start": reference_dates.min().strftime("%Y-%m-%d"),
        "reference_end": reference_dates.max().strftime("%Y-%m-%d"),
        "current_start": current_dates.min().strftime("%Y-%m-%d"),
        "current_end": current_dates.max().strftime("%Y-%m-%d"),
        "reference_observations": len(reference),
        "current_observations": len(current),
    }

    summary_rows: list[dict[str, object]] = []
    bin_rows: list[dict[str, object]] = []
    for feature in numeric_features:
        values = _validated_numeric(working[feature], feature)
        feature_rows, metadata = _numeric_bins(
            feature,
            values.loc[reference.index],
            values.loc[current.index],
            requested_bins=requested_bins,
        )
        summary_rows.append(
            _summary_row(
                feature,
                "numeric",
                values.loc[reference.index],
                values.loc[current.index],
                feature_rows,
                period,
                requested_bins=requested_bins,
                green_max=green_max,
                warning_max=warning_max,
                **metadata,
            )
        )
        bin_rows.extend(feature_rows)

    for feature in categorical_features:
        values = _normalised_categories(working[feature])
        feature_rows, metadata = _categorical_bins(
            feature,
            values.loc[reference.index],
            values.loc[current.index],
        )
        summary_rows.append(
            _summary_row(
                feature,
                "categorical",
                values.loc[reference.index],
                values.loc[current.index],
                feature_rows,
                period,
                requested_bins=None,
                green_max=green_max,
                warning_max=warning_max,
                **metadata,
            )
        )
        bin_rows.extend(feature_rows)

    return pd.DataFrame(summary_rows), pd.DataFrame(bin_rows)


def _numeric_bins(
    feature: str,
    reference: pd.Series,
    current: pd.Series,
    *,
    requested_bins: int,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    reference_non_missing = reference.dropna()
    current_non_missing = current.dropna()
    if reference_non_missing.empty and current_non_missing.empty:
        return [
            _bin_row(
                feature,
                "numeric",
                "MISSING",
                MISSING_CATEGORY,
                None,
                None,
                None,
                len(reference),
                len(current),
                len(reference),
                len(current),
            )
        ], {
            "binning_method": "all_missing",
            "availability_status": "all_missing",
        }

    if reference_non_missing.empty:
        rows = [
            _bin_row(
                feature,
                "numeric",
                "NON_MISSING",
                "non-missing",
                None,
                None,
                None,
                0,
                len(current_non_missing),
                len(reference),
                len(current),
            ),
            _bin_row(
                feature,
                "numeric",
                "MISSING",
                MISSING_CATEGORY,
                None,
                None,
                None,
                int(reference.isna().sum()),
                int(current.isna().sum()),
                len(reference),
                len(current),
            ),
        ]
        return rows, {
            "binning_method": "reference_missing_indicator",
            "availability_status": "reference_all_missing",
        }

    edges = _reference_midpoint_edges(reference_non_missing, requested_bins)
    reference_assignments = _assign_numeric_bins(reference_non_missing, edges)
    current_assignments = _assign_numeric_bins(current_non_missing, edges)
    rows = []
    for bin_number in range(1, len(edges)):
        lower = float(edges[bin_number - 1])
        upper = float(edges[bin_number])
        rows.append(
            _bin_row(
                feature,
                "numeric",
                f"B{bin_number:02d}",
                _range_label(lower, upper),
                None if math.isinf(lower) else lower,
                None if math.isinf(upper) else upper,
                None,
                int((reference_assignments == bin_number).sum()),
                int((current_assignments == bin_number).sum()),
                len(reference),
                len(current),
            )
        )
    if reference.isna().any() or current.isna().any():
        rows.append(
            _bin_row(
                feature,
                "numeric",
                "MISSING",
                MISSING_CATEGORY,
                None,
                None,
                None,
                int(reference.isna().sum()),
                int(current.isna().sum()),
                len(reference),
                len(current),
            )
        )
    return rows, {
        "binning_method": "reference_quantile_midpoint",
        "availability_status": "available",
    }


def _categorical_bins(
    feature: str,
    reference: pd.Series,
    current: pd.Series,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    categories = sorted(
        set(reference).union(current) - {MISSING_CATEGORY},
        key=str.casefold,
    )
    if MISSING_CATEGORY in set(reference).union(current):
        categories.append(MISSING_CATEGORY)
    rows = []
    for index, category in enumerate(categories, start=1):
        rows.append(
            _bin_row(
                feature,
                "categorical",
                "MISSING" if category == MISSING_CATEGORY else f"C{index:02d}",
                category,
                None,
                None,
                category,
                int(reference.eq(category).sum()),
                int(current.eq(category).sum()),
                len(reference),
                len(current),
            )
        )
    all_missing = categories == [MISSING_CATEGORY]
    reference_all_missing = reference.eq(MISSING_CATEGORY).all() and not all_missing
    return rows, {
        "binning_method": "category_union",
        "availability_status": (
            "all_missing"
            if all_missing
            else "reference_all_missing"
            if reference_all_missing
            else "available"
        ),
    }


def _bin_row(
    feature: str,
    feature_type: str,
    bin_name: str,
    bin_label: str,
    lower_bound: float | None,
    upper_bound: float | None,
    category_value: str | None,
    reference_observations: int,
    current_observations: int,
    reference_total: int,
    current_total: int,
) -> dict[str, object]:
    reference_share = reference_observations / reference_total
    current_share = current_observations / current_total
    return {
        "feature_name": feature,
        "feature_type": feature_type,
        "bin": bin_name,
        "bin_label": bin_label,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "category_value": category_value,
        "reference_observations": reference_observations,
        "current_observations": current_observations,
        "reference_share": reference_share,
        "current_share": current_share,
        "csi_component": _csi_component(reference_share, current_share),
    }


def _summary_row(
    feature: str,
    feature_type: str,
    reference: pd.Series,
    current: pd.Series,
    bins: list[dict[str, object]],
    period: dict[str, object],
    *,
    requested_bins: int | None,
    binning_method: str,
    availability_status: str,
    green_max: float,
    warning_max: float,
) -> dict[str, object]:
    csi = float(sum(float(row["csi_component"]) for row in bins))
    reference_missing = _missing_rate(reference, feature_type)
    current_missing = _missing_rate(current, feature_type)
    return {
        "feature_name": feature,
        "feature_type": feature_type,
        **period,
        "reference_missing_rate": reference_missing,
        "current_missing_rate": current_missing,
        "missing_rate_delta": current_missing - reference_missing,
        "requested_bins": requested_bins,
        "effective_bins": len(bins),
        "binning_method": binning_method,
        "availability_status": availability_status,
        "characteristic_stability_index": csi,
        "stability_status": _stability_status(
            csi,
            availability_status,
            green_max,
            warning_max,
        ),
    }


def _reference_midpoint_edges(values: pd.Series, requested_bins: int) -> np.ndarray:
    sorted_values = np.sort(values.to_numpy(dtype=float))
    distinct_boundaries = np.flatnonzero(sorted_values[1:] > sorted_values[:-1]) + 1
    if requested_bins == 1 or len(distinct_boundaries) == 0:
        return np.array([-np.inf, np.inf])
    targets = np.arange(1, requested_bins) * len(sorted_values) / requested_bins
    chosen = {
        int(distinct_boundaries[np.argmin(np.abs(distinct_boundaries - target))])
        for target in targets
    }
    cut_points = []
    for boundary in sorted(chosen):
        lower = float(sorted_values[boundary - 1])
        upper = float(sorted_values[boundary])
        midpoint = lower + (upper - lower) / 2
        if midpoint <= lower:
            midpoint = float(np.nextafter(lower, upper))
        cut_points.append(midpoint)
    return np.array([-np.inf, *cut_points, np.inf])


def _assign_numeric_bins(values: pd.Series, edges: np.ndarray) -> np.ndarray:
    return np.searchsorted(
        edges[1:-1],
        values.to_numpy(dtype=float),
        side="right",
    ) + 1


def _validated_numeric(values: pd.Series, feature: str) -> pd.Series:
    parsed = pd.to_numeric(values, errors="coerce")
    if (values.notna() & parsed.isna()).any():
        raise ValueError(f"{feature} must contain numeric values when present")
    non_missing = parsed.dropna().to_numpy(dtype=float)
    if not np.isfinite(non_missing).all():
        raise ValueError(f"{feature} must contain finite numeric values when present")
    return parsed.astype(float)


def _normalised_categories(values: pd.Series) -> pd.Series:
    missing = values.isna()
    normalized = values.astype("string").str.strip()
    missing |= normalized.eq("").fillna(True)
    return normalized.mask(missing, MISSING_CATEGORY).astype(str)


def _missing_rate(values: pd.Series, feature_type: str) -> float:
    if feature_type == "categorical":
        return float(values.eq(MISSING_CATEGORY).mean())
    return float(values.isna().mean())


def _range_label(lower: float, upper: float) -> str:
    lower_label = "-inf" if math.isinf(lower) else f"{lower:.6g}"
    upper_label = "+inf" if math.isinf(upper) else f"{upper:.6g}"
    return f"[{lower_label}, {upper_label})"


def _csi_component(reference_share: float, current_share: float) -> float:
    epsilon = 1e-6
    reference = max(reference_share, epsilon)
    current = max(current_share, epsilon)
    return float((current - reference) * np.log(current / reference))


def _stability_status(
    csi: float,
    availability_status: str,
    green_max: float,
    warning_max: float,
) -> str:
    if availability_status == "all_missing":
        return "not_available"
    if csi <= green_max:
        return "stable"
    if csi <= warning_max:
        return "moderate_shift"
    return "material_shift"


def _validate_configuration(
    numeric_features: tuple[str, ...],
    categorical_features: tuple[str, ...],
    requested_bins: int,
    green_max: float,
    warning_max: float,
) -> None:
    if not isinstance(requested_bins, int) or requested_bins < 1:
        raise ValueError("requested_bins must be a positive integer")
    all_features: Iterable[str] = (*numeric_features, *categorical_features)
    feature_list = list(all_features)
    if not feature_list:
        raise ValueError("At least one characteristic feature is required")
    if len(feature_list) != len(set(feature_list)):
        raise ValueError("Characteristic feature names must be unique")
    if not all(
        isinstance(value, (int, float)) and math.isfinite(value)
        for value in (green_max, warning_max)
    ):
        raise ValueError("CSI thresholds must be finite numbers")
    if green_max < 0 or green_max > warning_max:
        raise ValueError("CSI thresholds must order green before warning")
