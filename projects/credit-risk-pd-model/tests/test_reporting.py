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
                "roc_auc": 0.71,
                "gini": 0.42,
                "ks": 0.31,
                "brier_score": 0.19,
                "precision": 0.40,
                "recall": 0.55,
            },
            {
                "model": "random_forest",
                "roc_auc": 0.68,
                "gini": 0.36,
                "ks": 0.27,
                "brier_score": 0.21,
                "precision": 0.35,
                "recall": 0.50,
            },
        ]
    ).to_csv(reports_dir / "model_metrics.csv", index=False)
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
        ]
    ).to_csv(reports_dir / "psi_report.csv", index=False)

    report_path = generate_model_report(reports_dir)

    assert report_path == reports_dir / "model_report.md"
    report = report_path.read_text(encoding="utf-8")
    assert "# Credit Risk PD Model Report" in report
    assert "Best model by out-of-time ROC-AUC: `logistic_regression`" in report
    assert "| logistic_regression | 0.710 | 0.420 | 0.310 | 0.190 | 40.0% | 55.0% |" in report
    assert "largest absolute decile gap 7.0%" in report
    assert "| interest_rate | 0.310 | material_shift |" in report


def test_generate_model_report_requires_expected_inputs(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="model_metrics.csv"):
        generate_model_report(reports_dir)
