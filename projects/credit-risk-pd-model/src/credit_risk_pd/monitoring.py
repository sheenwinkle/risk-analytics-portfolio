from __future__ import annotations

import numpy as np
import pandas as pd


def population_stability_index(
    expected: pd.Series | np.ndarray,
    actual: pd.Series | np.ndarray,
    buckets: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """Calculate PSI using quantile buckets from the expected sample."""
    expected_series = pd.Series(expected).dropna()
    actual_series = pd.Series(actual).dropna()

    if expected_series.empty or actual_series.empty:
        return np.nan

    quantiles = np.linspace(0, 1, buckets + 1)
    breakpoints = np.unique(expected_series.quantile(quantiles).to_numpy())
    if len(breakpoints) < 3:
        return 0.0

    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf

    expected_counts = pd.cut(
        expected_series,
        bins=breakpoints,
        include_lowest=True,
    ).value_counts(sort=False)
    actual_counts = pd.cut(
        actual_series,
        bins=breakpoints,
        include_lowest=True,
    ).value_counts(sort=False)

    expected_pct = expected_counts / expected_counts.sum()
    actual_pct = actual_counts / actual_counts.sum()

    psi = (
        (actual_pct - expected_pct)
        * np.log((actual_pct + epsilon) / (expected_pct + epsilon))
    ).sum()
    return float(psi)


def psi_report(
    expected: pd.DataFrame,
    actual: pd.DataFrame,
    features: list[str],
    buckets: int = 10,
) -> pd.DataFrame:
    """Calculate feature-level PSI and apply common monitoring bands."""
    rows = []
    for feature in features:
        value = population_stability_index(expected[feature], actual[feature], buckets=buckets)
        if pd.isna(value):
            status = "not_available"
        elif value < 0.1:
            status = "stable"
        elif value < 0.25:
            status = "moderate_shift"
        else:
            status = "material_shift"
        rows.append({"feature": feature, "psi": value, "status": status})

    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)

