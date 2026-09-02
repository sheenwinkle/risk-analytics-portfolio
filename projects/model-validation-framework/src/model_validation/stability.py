from __future__ import annotations

import numpy as np
import pandas as pd


def build_stability_tables(
    predictions: pd.DataFrame,
    *,
    selected_model: str,
    score_column: str,
    requested_bins: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reference_dates, current_dates = split_observation_dates(predictions["observation_date"])
    reference = predictions[predictions["observation_date"].isin(reference_dates)].copy()
    current = predictions[predictions["observation_date"].isin(current_dates)].copy()

    bin_edges = _derive_reference_bin_edges(
        reference[score_column],
        requested_bins=requested_bins,
    )
    reference_bin_numbers = _assign_to_reference_bins(reference[score_column], bin_edges)
    current_bin_numbers = _assign_to_reference_bins(current[score_column], bin_edges)

    bins = []
    for bin_number in range(1, len(bin_edges)):
        reference_observations = int((reference_bin_numbers == bin_number).sum())
        current_observations = int((current_bin_numbers == bin_number).sum())
        reference_share = reference_observations / len(reference)
        current_share = current_observations / len(current)
        bins.append(
            {
                "model_name": selected_model,
                "score_version": "recalibrated",
                "bin": bin_number,
                "lower_pd_bound": float(bin_edges[bin_number - 1]),
                "upper_pd_bound": float(bin_edges[bin_number]),
                "reference_observations": reference_observations,
                "current_observations": current_observations,
                "reference_share": reference_share,
                "current_share": current_share,
                "psi_component": _psi_component(reference_share, current_share),
            }
        )

    stability_bins = pd.DataFrame(bins)
    stability_summary = pd.DataFrame(
        [
            {
                "model_name": selected_model,
                "score_version": "recalibrated",
                "reference_start": reference_dates.min().strftime("%Y-%m-%d"),
                "reference_end": reference_dates.max().strftime("%Y-%m-%d"),
                "current_start": current_dates.min().strftime("%Y-%m-%d"),
                "current_end": current_dates.max().strftime("%Y-%m-%d"),
                "reference_observations": len(reference),
                "current_observations": len(current),
                "requested_bins": requested_bins,
                "effective_bins": len(bin_edges) - 1,
                "binning_method": "reference_quantile_midpoint",
                "population_stability_index": float(stability_bins["psi_component"].sum()),
            }
        ]
    )
    return stability_summary, stability_bins


def split_observation_dates(observation_dates: pd.Series) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    unique_dates = pd.DatetimeIndex(sorted(observation_dates.drop_duplicates()))
    midpoint = len(unique_dates) // 2
    return unique_dates[:midpoint], unique_dates[midpoint:]


def _derive_reference_bin_edges(
    scores: pd.Series,
    *,
    requested_bins: int,
) -> np.ndarray:
    if requested_bins < 1:
        raise ValueError("requested_bins must be at least 1")

    sorted_scores = np.sort(scores.to_numpy(dtype=float))
    distinct_boundaries = np.flatnonzero(sorted_scores[1:] > sorted_scores[:-1]) + 1
    if requested_bins == 1 or len(distinct_boundaries) == 0:
        return np.array([0.0, 1.0])

    targets = np.arange(1, requested_bins) * len(sorted_scores) / requested_bins
    chosen_boundaries = {
        int(distinct_boundaries[np.argmin(np.abs(distinct_boundaries - target))])
        for target in targets
    }
    cut_points = []
    for boundary in sorted(chosen_boundaries):
        lower = float(sorted_scores[boundary - 1])
        upper = float(sorted_scores[boundary])
        midpoint = lower + (upper - lower) / 2
        if midpoint <= lower:
            midpoint = float(np.nextafter(lower, upper))
        cut_points.append(midpoint)
    return np.array([0.0, *cut_points, 1.0])


def _assign_to_reference_bins(scores: pd.Series, bin_edges: np.ndarray) -> pd.Series:
    internal_edges = bin_edges[1:-1]
    assigned = np.searchsorted(internal_edges, scores.to_numpy(dtype=float), side="right") + 1
    return pd.Series(assigned, index=scores.index)


def _psi_component(reference_share: float, current_share: float) -> float:
    epsilon = 1e-6
    reference = max(reference_share, epsilon)
    current = max(current_share, epsilon)
    return float((current - reference) * np.log(current / reference))
