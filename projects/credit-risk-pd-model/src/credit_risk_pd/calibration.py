from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

DEFAULT_PROBABILITY_EPSILON = 1e-6


@dataclass
class LogisticPDRecalibrator:
    """Fit a logistic recalibration model on raw PD estimates."""

    epsilon: float = DEFAULT_PROBABILITY_EPSILON
    intercept_: float | None = None
    slope_: float | None = None

    def fit(self, raw_pd, y_true) -> LogisticPDRecalibrator:
        """Fit intercept and slope from raw model PDs and binary outcomes."""
        probabilities = _validate_probabilities(raw_pd, self.epsilon, "raw_pd")
        target = _validate_binary_target(y_true, len(probabilities))
        model = _fit_logistic_on_logit(probabilities, target)
        slope = float(model.coef_[0, 0])
        if slope <= 0:
            raise ValueError(
                "Recalibration requires a positive relationship between PD and default."
            )

        self.intercept_ = float(model.intercept_[0])
        self.slope_ = slope
        return self

    def transform(self, raw_pd) -> pd.Series:
        """Transform raw PDs into recalibrated PDs bounded to [0, 1]."""
        if self.intercept_ is None or self.slope_ is None:
            raise ValueError("Recalibrator must be fitted before transform.")

        probabilities = _validate_probabilities(raw_pd, self.epsilon, "raw_pd")
        logits = _logit(probabilities)
        recalibrated = _sigmoid(self.intercept_ + self.slope_ * logits)
        return pd.Series(recalibrated, index=_input_index(raw_pd), name="recalibrated_pd")


@dataclass
class RecalibratedPDModel:
    """Estimator wrapper that returns recalibrated PDs via predict_proba."""

    selected_model_name: str
    base_estimator: object
    recalibrator: LogisticPDRecalibrator

    @property
    def classes_(self) -> np.ndarray:
        """Expose fitted class labels for estimator compatibility."""
        return np.asarray(self.base_estimator.classes_)

    def predict_raw_proba(self, x) -> np.ndarray:
        """Return the selected base estimator's raw PD estimates."""
        probabilities = np.asarray(self.base_estimator.predict_proba(x), dtype=float)
        if probabilities.ndim != 2 or probabilities.shape[1] != 2:
            raise ValueError("Base estimator must return two-column binary probabilities.")
        return probabilities[:, 1]

    def predict_proba(self, x) -> np.ndarray:
        """Return two-column probabilities using recalibrated PD as the event probability."""
        recalibrated_pd = self.recalibrator.transform(self.predict_raw_proba(x)).to_numpy()
        return np.column_stack([1 - recalibrated_pd, recalibrated_pd])


def calibration_diagnostics(y_true, pd_scores) -> dict[str, float]:
    """Calculate calibration slope/intercept and proper scoring diagnostics."""
    probabilities = _validate_probabilities(pd_scores, DEFAULT_PROBABILITY_EPSILON, "pd_scores")
    target = _validate_binary_target(y_true, len(probabilities))
    model = _fit_logistic_on_logit(probabilities, target)

    return {
        "calibration_intercept": float(model.intercept_[0]),
        "calibration_slope": float(model.coef_[0, 0]),
        "brier_score": float(brier_score_loss(target, probabilities)),
        "log_loss": float(log_loss(target, probabilities)),
        "mean_pd": float(np.mean(probabilities)),
        "observed_default_rate": float(np.mean(target)),
    }


def _fit_logistic_on_logit(probabilities: np.ndarray, target: np.ndarray) -> LogisticRegression:
    model = LogisticRegression(C=1_000_000, max_iter=1_000)
    model.fit(_logit(probabilities).reshape(-1, 1), target)
    return model


def _validate_probabilities(values, epsilon: float, label: str) -> np.ndarray:
    if not np.isfinite(epsilon) or not 0 < epsilon < 0.5:
        raise ValueError("epsilon must be a finite value greater than 0 and less than 0.5.")
    probabilities = np.asarray(values, dtype=float)
    if probabilities.ndim != 1:
        raise ValueError(f"{label} must be one-dimensional.")
    if probabilities.size == 0:
        raise ValueError(f"{label} must contain at least one value.")
    if not np.isfinite(probabilities).all():
        raise ValueError(f"{label} must contain only finite values.")
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError(f"{label} values must be between 0 and 1.")
    return np.clip(probabilities, epsilon, 1 - epsilon)


def _validate_binary_target(values, expected_length: int) -> np.ndarray:
    target = np.asarray(values)
    if target.ndim != 1:
        raise ValueError("y_true must be one-dimensional.")
    if len(target) != expected_length:
        raise ValueError("raw_pd and y_true must have the same length.")
    if not np.isfinite(target.astype(float)).all():
        raise ValueError("y_true must contain only finite values.")

    unique_values = set(np.unique(target).tolist())
    if not unique_values.issubset({0, 1}):
        raise ValueError("y_true must contain binary 0/1 outcomes.")
    if len(unique_values) < 2:
        raise ValueError("y_true must contain both default and non-default observations.")
    return target.astype(int)


def _input_index(values) -> pd.Index | None:
    if isinstance(values, pd.Series):
        return values.index
    return None


def _logit(probabilities: np.ndarray) -> np.ndarray:
    return np.log(probabilities / (1 - probabilities))


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    result = np.empty_like(values)
    nonnegative = values >= 0
    result[nonnegative] = 1 / (1 + np.exp(-values[nonnegative]))
    exponentials = np.exp(values[~nonnegative])
    result[~nonnegative] = exponentials / (1 + exponentials)
    return result
