from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

DEFAULT_LGD = 0.45


def approval_strategy_table(
    pd_scores,
    y_true,
    exposures,
    thresholds: Iterable[float],
    lgd: float = DEFAULT_LGD,
) -> pd.DataFrame:
    """Summarise fixed max-PD approval cutoff scenarios without selecting a winner."""
    probabilities = _validate_probabilities(pd_scores)
    target = _validate_binary_target(y_true, len(probabilities))
    exposure_values = _validate_exposures(exposures, len(probabilities))
    threshold_values = _validate_thresholds(thresholds)
    lgd_value = _validate_lgd(lgd)
    total_accounts = len(probabilities)
    total_defaults = target.sum()

    rows = []
    for cutoff in threshold_values:
        approved = probabilities <= cutoff
        rejected = ~approved
        approved_accounts = int(approved.sum())
        approved_defaults = int(target[approved].sum())
        approved_exposure = float(exposure_values[approved].sum())
        expected_loss = float(
            (probabilities[approved] * lgd_value * exposure_values[approved]).sum()
        )

        rows.append(
            {
                "max_pd_cutoff": float(cutoff),
                "lgd": lgd_value,
                "approved_accounts": approved_accounts,
                "rejected_accounts": int(rejected.sum()),
                "approval_rate": float(approved_accounts / total_accounts),
                "approved_observed_defaults": approved_defaults,
                "approved_default_rate": _safe_rate(approved_defaults, approved_accounts),
                "approved_exposure": approved_exposure,
                "expected_loss": expected_loss,
                "expected_loss_rate": _safe_rate(expected_loss, approved_exposure),
                "rejected_default_capture_rate": _safe_rate(
                    int(target[rejected].sum()),
                    total_defaults,
                ),
            }
        )

    return pd.DataFrame(rows)


def _validate_probabilities(values) -> np.ndarray:
    probabilities = np.asarray(values, dtype=float)
    if probabilities.ndim != 1:
        raise ValueError("PD scores must be one-dimensional.")
    if probabilities.size == 0:
        raise ValueError("PD scores must contain at least one value.")
    if not np.isfinite(probabilities).all():
        raise ValueError("PD scores must contain only finite values.")
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("PD scores must be between 0 and 1.")
    return probabilities


def _validate_binary_target(values, expected_length: int) -> np.ndarray:
    target = np.asarray(values)
    if target.ndim != 1:
        raise ValueError("targets must be one-dimensional.")
    if len(target) != expected_length:
        raise ValueError("PD scores, targets, and exposures must have the same length.")
    if not np.isfinite(target.astype(float)).all():
        raise ValueError("targets must contain only finite values.")
    unique_values = set(np.unique(target).tolist())
    if not unique_values.issubset({0, 1}):
        raise ValueError("targets must be binary 0/1 outcomes.")
    return target.astype(int)


def _validate_exposures(values, expected_length: int) -> np.ndarray:
    exposures = np.asarray(values, dtype=float)
    if exposures.ndim != 1:
        raise ValueError("exposures must be one-dimensional.")
    if len(exposures) != expected_length:
        raise ValueError("PD scores, targets, and exposures must have the same length.")
    if not np.isfinite(exposures).all():
        raise ValueError("exposures must contain only finite values.")
    if (exposures < 0).any():
        raise ValueError("exposures must be nonnegative.")
    return exposures


def _validate_thresholds(thresholds: Iterable[float]) -> tuple[float, ...]:
    values = tuple(float(threshold) for threshold in thresholds)
    if not values:
        raise ValueError("thresholds must contain at least one value.")
    invalid_threshold = any(threshold <= 0 or threshold >= 1 for threshold in values)
    if not np.isfinite(values).all() or invalid_threshold:
        raise ValueError("thresholds must be finite values greater than 0 and less than 1.")
    if len(set(values)) != len(values):
        raise ValueError("thresholds must not contain duplicate values.")
    return values


def _validate_lgd(lgd: float) -> float:
    value = float(lgd)
    if not np.isfinite(value) or value < 0 or value > 1:
        raise ValueError("LGD must be a finite value between 0 and 1.")
    return value


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator / denominator)
