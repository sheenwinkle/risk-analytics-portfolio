import pandas as pd
import pytest

from credit_risk_pd.reporting import generate_model_report


def test_generate_model_report_summarises_report_csvs(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    pd.DataFrame(
        [
            {
                "model": "logistic_regression",
                "score_type": "raw",
                "classification_threshold": 0.15,
                "roc_auc": 0.71,
                "gini": 0.42,
                "ks": 0.31,
                "brier_score": 0.19,
                "precision": 0.40,
                "recall": 0.55,
            },
            {
                "model": "random_forest",
                "score_type": "raw",
                "classification_threshold": 0.15,
                "roc_auc": 0.68,
                "gini": 0.36,
                "ks": 0.27,
                "brier_score": 0.21,
                "precision": 0.35,
                "recall": 0.50,
            },
            {
                "model": "logistic_regression",
                "score_type": "recalibrated",
                "classification_threshold": 0.15,
                "roc_auc": 0.71,
                "gini": 0.42,
                "ks": 0.31,
                "brier_score": 0.16,
                "precision": 0.44,
                "recall": 0.57,
            },
        ]
    ).to_csv(reports_dir / "model_metrics.csv", index=False)
    pd.DataFrame(
        [
            {
                "model": "logistic_regression",
                "model_development_accounts": 600,
                "calibration_holdout_accounts": 200,
                "model_development_start": "2019-01-01",
                "model_development_end": "2020-06-01",
                "calibration_holdout_start": "2020-07-01",
                "calibration_holdout_end": "2020-12-01",
                "calibration_holdout_roc_auc": 0.73,
                "selected_model": True,
            },
            {
                "model": "random_forest",
                "model_development_accounts": 600,
                "calibration_holdout_accounts": 200,
                "model_development_start": "2019-01-01",
                "model_development_end": "2020-06-01",
                "calibration_holdout_start": "2020-07-01",
                "calibration_holdout_end": "2020-12-01",
                "calibration_holdout_roc_auc": 0.70,
                "selected_model": False,
            },
        ]
    ).to_csv(reports_dir / "model_selection_audit.csv", index=False)
    pd.DataFrame(
        [
            {
                "model": "logistic_regression",
                "score_type": "raw",
                "evaluation_sample": "out_of_time",
                "recalibration_fit_sample": "pre_oot_calibration_holdout",
                "recalibration_fit_intercept": -0.35,
                "recalibration_fit_slope": 1.20,
                "calibration_intercept": -0.21,
                "calibration_slope": 0.82,
                "brier_score": 0.19,
                "log_loss": 0.58,
                "mean_pd": 0.24,
                "observed_default_rate": 0.20,
            },
            {
                "model": "logistic_regression",
                "score_type": "recalibrated",
                "evaluation_sample": "out_of_time",
                "recalibration_fit_sample": "pre_oot_calibration_holdout",
                "recalibration_fit_intercept": -0.35,
                "recalibration_fit_slope": 1.20,
                "calibration_intercept": 0.03,
                "calibration_slope": 1.04,
                "brier_score": 0.16,
                "log_loss": 0.51,
                "mean_pd": 0.21,
                "observed_default_rate": 0.20,
            },
        ]
    ).to_csv(reports_dir / "recalibration_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "max_pd_cutoff": 0.10,
                "lgd": 0.45,
                "approved_accounts": 120,
                "rejected_accounts": 880,
                "approval_rate": 0.12,
                "approved_observed_defaults": 6,
                "approved_default_rate": 0.05,
                "approved_exposure": 1_800_000,
                "expected_loss": 81_000,
                "expected_loss_rate": 0.045,
                "rejected_default_capture_rate": 0.97,
            },
            {
                "max_pd_cutoff": 0.20,
                "lgd": 0.45,
                "approved_accounts": 420,
                "rejected_accounts": 580,
                "approval_rate": 0.42,
                "approved_observed_defaults": 42,
                "approved_default_rate": 0.10,
                "approved_exposure": 6_300_000,
                "expected_loss": 567_000,
                "expected_loss_rate": 0.09,
                "rejected_default_capture_rate": 0.79,
            },
        ]
    ).to_csv(reports_dir / "approval_strategy.csv", index=False)
    pd.DataFrame(
        [
            {
                "bucket": "(0.10, 0.20]",
                "accounts": 100,
                "predicted_pd": 0.15,
                "observed_default_rate": 0.10,
                "defaults": 10,
                "calibration_gap": 0.05,
            },
            {
                "bucket": "(0.20, 0.30]",
                "accounts": 100,
                "predicted_pd": 0.25,
                "observed_default_rate": 0.18,
                "defaults": 18,
                "calibration_gap": 0.07,
            },
        ]
    ).to_csv(reports_dir / "calibration_table.csv", index=False)
    pd.DataFrame(
        [
            {"feature": "interest_rate", "psi": 0.31, "status": "material_shift"},
            {"feature": "annual_income", "psi": 0.04, "status": "stable"},
            {"feature": "age", "psi": float("nan"), "status": "not_available"},
        ]
    ).to_csv(reports_dir / "psi_report.csv", index=False)
    pd.DataFrame(
        [
            {
                "feature": "debt_to_income",
                "importance_mean": 0.085,
                "importance_std": 0.012,
            },
            {
                "feature": "annual_income",
                "importance_mean": 0.010,
                "importance_std": 0.004,
            },
        ]
    ).to_csv(reports_dir / "feature_importance.csv", index=False)
    pd.DataFrame(
        [
            {
                "rank": 1,
                "feature": "credit_utilisation",
                "feature_type": "numeric",
                "bins": 5,
                "information_value": 0.42,
                "iv_band": "strong",
            },
            {
                "rank": 2,
                "feature": "home_ownership",
                "feature_type": "categorical",
                "bins": 4,
                "information_value": 0.08,
                "iv_band": "weak",
            },
        ]
    ).to_csv(reports_dir / "woe_summary.csv", index=False)

    report_path = generate_model_report(reports_dir)

    assert report_path == reports_dir / "model_report.md"
    report = report_path.read_text(encoding="utf-8")
    assert "# Credit Risk PD Model Report" in report
    assert "Selected model by pre-OOT calibration holdout ROC-AUC: `logistic_regression`" in report
    assert (
        "| logistic_regression | raw | 15.0% | 0.710 | 0.420 | 0.310 | "
        "0.190 | 40.0% | 55.0% |"
    ) in report
    assert "Model selection occurred before OOT evaluation" in report
    assert "## PD Recalibration" in report
    assert "logit(PD_recalibrated) = -0.350 + 1.200 x logit(PD_raw)" in report
    assert "| recalibrated | 0.030 | 1.040 | 0.160 | 0.510 | 21.0% | 20.0% |" in report
    assert "## Lending Strategy" in report
    assert "scenario rows, not recommendations" in report
    assert (
        "| 20.0% | 45.0% | 420 | 42.0% | 10.0% | 6300000 | 567000 | "
        "9.0% | 79.0% |"
    ) in report
    assert "largest absolute decile gap 7.0%" in report
    assert "top out-of-time permutation importance feature `debt_to_income`" in report
    assert "top development-sample Information Value feature `credit_utilisation`" in report
    assert "## Information Value" in report
    assert "WOE is ln(% good / % bad)" in report
    assert "| 1 | credit_utilisation | numeric | 5 | 0.420 | strong |" in report
    assert "| debt_to_income | 0.085 | 0.012 |" in report
    assert "| interest_rate | 0.310 | material_shift |" in report
    assert "| age | N/A | not_available |" in report


def test_generate_model_report_requires_expected_inputs(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="model_metrics.csv"):
        generate_model_report(reports_dir)
