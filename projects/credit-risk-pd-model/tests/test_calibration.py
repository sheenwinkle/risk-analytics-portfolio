import numpy as np
import pandas as pd
import pytest

from credit_risk_pd.calibration import (
    LogisticPDRecalibrator,
    calibration_diagnostics,
)


def test_logistic_recalibrator_fits_and_transforms_probabilities_monotonically():
    raw_pd = pd.Series([0.03, 0.07, 0.12, 0.19, 0.31, 0.44, 0.58, 0.72])
    y_true = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])

    recalibrator = LogisticPDRecalibrator().fit(raw_pd, y_true)
    recalibrated_pd = recalibrator.transform(raw_pd)

    assert np.isfinite(recalibrator.intercept_)
    assert recalibrator.slope_ > 0
    assert recalibrated_pd.between(0, 1).all()
    assert recalibrated_pd.is_monotonic_increasing


def test_calibration_diagnostics_reports_oot_intercept_slope_and_losses():
    y_true = pd.Series([0, 0, 0, 1, 1, 1])
    pd_scores = pd.Series([0.05, 0.12, 0.25, 0.40, 0.67, 0.81])

    diagnostics = calibration_diagnostics(y_true, pd_scores)

    assert np.isfinite(diagnostics["calibration_intercept"])
    assert np.isfinite(diagnostics["calibration_slope"])
    assert diagnostics["brier_score"] == pytest.approx(np.mean((pd_scores - y_true) ** 2))
    assert diagnostics["log_loss"] > 0
    assert diagnostics["mean_pd"] == pytest.approx(pd_scores.mean())
    assert diagnostics["observed_default_rate"] == pytest.approx(y_true.mean())


@pytest.mark.parametrize(
    ("raw_pd", "y_true", "match"),
    [
        ([0.1, 1.2], [0, 1], "between 0 and 1"),
        ([0.1, np.nan], [0, 1], "finite"),
        ([0.1, 0.2], [0, 0], "both default and non-default"),
        ([0.1, 0.2, 0.3], [0, 1], "same length"),
        ([[0.1, 0.2]], [0, 1], "one-dimensional"),
    ],
)
def test_calibration_rejects_malformed_inputs(raw_pd, y_true, match):
    with pytest.raises(ValueError, match=match):
        LogisticPDRecalibrator().fit(raw_pd, y_true)


@pytest.mark.parametrize("epsilon", [0.0, 0.5, np.nan])
def test_logistic_recalibrator_rejects_invalid_epsilon(epsilon):
    with pytest.raises(ValueError, match="epsilon"):
        LogisticPDRecalibrator(epsilon=epsilon).fit([0.1, 0.9], [0, 1])


def test_logistic_recalibrator_handles_extreme_logits_without_overflow():
    recalibrator = LogisticPDRecalibrator(intercept_=1_000.0, slope_=1_000.0)

    recalibrated = recalibrator.transform(pd.Series([0.0, 1.0]))

    assert np.isfinite(recalibrated).all()
    assert recalibrated.between(0, 1).all()
