import numpy as np
import pandas as pd
import pytest

from model_validation.diagnostics import (
    build_metric_uncertainty,
    build_segment_performance,
    build_vintage_performance,
)


def _diagnostic_predictions() -> pd.DataFrame:
    rows = []
    for index in range(120):
        overprediction = index < 60
        within_group = index % 60
        default = int(
            within_group < (12 if overprediction else 42)
        )
        rows.append(
            {
                "customer_id": f"D{index:03d}",
                "observation_date": "2022-02-01" if overprediction else "2022-05-01",
                "actual_default": default,
                "recalibrated_pd": 0.55 if overprediction else 0.20,
                "home_ownership": "rent" if overprediction else "mortgage",
                "purpose": "overpredicted" if overprediction else "underpredicted",
            }
        )
    return pd.DataFrame(rows).assign(
        observation_date=lambda frame: pd.to_datetime(frame["observation_date"])
    )


def test_metric_uncertainty_uses_named_methods_and_contains_point_estimates():
    uncertainty = build_metric_uncertainty(
        _diagnostic_predictions(),
        selected_model="logistic_regression",
        score_column="recalibrated_pd",
    )

    assert uncertainty["metric"].tolist() == [
        "roc_auc",
        "observed_default_rate",
        "mean_predicted_pd",
        "calibration_gap",
        "brier_score",
    ]
    assert uncertainty.set_index("metric")["method"].to_dict() == {
        "roc_auc": "delong",
        "observed_default_rate": "wilson_score",
        "mean_predicted_pd": "normal_mean",
        "calibration_gap": "paired_normal",
        "brier_score": "normal_mean",
    }
    assert (
        (uncertainty["lower_bound"] <= uncertainty["estimate"])
        & (uncertainty["estimate"] <= uncertainty["upper_bound"])
    ).all()
    assert uncertainty["confidence_level"].eq(0.95).all()


def test_vintage_and_segment_diagnostics_surface_material_calibration_direction():
    predictions = _diagnostic_predictions()

    vintage = build_vintage_performance(
        predictions,
        selected_model="logistic_regression",
        score_column="recalibrated_pd",
    )
    segments = build_segment_performance(
        predictions,
        selected_model="logistic_regression",
        score_column="recalibrated_pd",
    )

    assert vintage["vintage_quarter"].tolist() == ["2022Q1", "2022Q2"]
    assert vintage["observations"].tolist() == [60, 60]
    assert vintage["portfolio_share"].tolist() == pytest.approx([0.5, 0.5])
    assert vintage["calibration_signal"].tolist() == [
        "pd_overprediction",
        "pd_underprediction",
    ]
    assert set(segments["segment_dimension"]) == {"home_ownership", "purpose"}
    purpose = segments.loc[segments["segment_dimension"].eq("purpose")].set_index(
        "segment_value"
    )
    assert purpose.loc["overpredicted", "calibration_signal"] == "pd_overprediction"
    assert purpose.loc["underpredicted", "calibration_signal"] == "pd_underprediction"
    assert segments["reliability_status"].eq("sufficient").all()


def test_small_or_single_class_group_is_flagged_without_invalid_auc_interval():
    predictions = _diagnostic_predictions().iloc[:4].copy()
    predictions["actual_default"] = 0

    segments = build_segment_performance(
        predictions,
        selected_model="logistic_regression",
        score_column="recalibrated_pd",
    )

    assert segments["reliability_status"].eq("limited_sample").all()
    assert segments["discrimination_status"].eq("not_available_single_class").all()
    assert segments["roc_auc"].isna().all()
    assert segments["roc_auc_lower"].isna().all()
    assert segments["roc_auc_upper"].isna().all()


@pytest.mark.parametrize("confidence_level", [0, 1, np.nan])
def test_metric_uncertainty_rejects_invalid_confidence_level(confidence_level):
    with pytest.raises(ValueError, match="confidence_level"):
        build_metric_uncertainty(
            _diagnostic_predictions(),
            selected_model="logistic_regression",
            score_column="recalibrated_pd",
            confidence_level=confidence_level,
        )
