from pathlib import Path

import pandas as pd
import pytest

from model_validation import Project1OOTPredictionAdapter
from model_validation.remediation import (
    RemediationPolicy,
    run_calibration_remediation,
    run_calibration_remediation_pipeline,
)


def _candidate_adapter() -> Project1OOTPredictionAdapter:
    project_dir = Path(__file__).resolve().parents[1]
    return Project1OOTPredictionAdapter(
        project_dir.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv"
    )


def test_rolling_remediation_uses_only_prior_periods_and_defers_final_closure():
    result = run_calibration_remediation(_candidate_adapter())
    summary = result.remediation_summary.iloc[0]

    assert (result.monthly_recalibration["calibration_end"] < result.monthly_recalibration["validation_period"]).all()
    assert result.monthly_recalibration["lookback_months"].eq(3).all()
    assert summary["incumbent_calibration_status"] == "fail"
    assert summary["remediation_retest_status"] == "pass"
    assert summary["remediated_absolute_calibration_gap"] == pytest.approx(
        0.0092178139,
        abs=1e-10,
    )
    assert summary["closure_status"] == "pending_fresh_oot"
    assert result.finding_lifecycle.loc[0, "initial_status"] == "fail"


def test_remediation_pipeline_outputs_are_deterministic_and_privacy_safe(tmp_path):
    output_a = tmp_path / "a"
    output_b = tmp_path / "b"
    run_calibration_remediation_pipeline(_candidate_adapter(), output_a)
    run_calibration_remediation_pipeline(_candidate_adapter(), output_b)

    assert {path.name for path in output_a.iterdir()} == {
        "remediation_summary.csv",
        "monthly_recalibration.csv",
        "finding_lifecycle.csv",
        "remediation_report.md",
    }
    for path_a in output_a.iterdir():
        path_b = output_b / path_a.name
        assert path_a.read_bytes() == path_b.read_bytes()
        assert b"\r\n" not in path_a.read_bytes()
    for csv_path in output_a.glob("*.csv"):
        assert "customer_id" not in pd.read_csv(csv_path, nrows=0).columns


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"lookback_months": 1}, "lookback_months"),
        (
            {"lookback_months": 4, "initial_calibration_months": 3},
            "initial_calibration_months",
        ),
        ({"tolerance": 0}, "tolerance"),
    ],
)
def test_remediation_policy_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        RemediationPolicy(**kwargs)
