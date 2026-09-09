from datetime import date
from pathlib import Path

import pytest

from model_validation import Project1OOTPredictionAdapter, run_validation
from model_validation.macro_remediation_demo import run_macro_remediation_validation
from model_validation.macro_satellite_demo import run_macro_satellite_validation
from model_validation.postgres import (
    MacroRemediationRunMetadata,
    MacroSatelliteRunMetadata,
    ValidationRunMetadata,
    build_macro_remediation_persistence_records,
    build_macro_satellite_persistence_records,
    build_persistence_records,
)


def test_build_persistence_records_maps_governance_tables_from_real_candidate_result():
    project_dir = Path(__file__).resolve().parents[1]
    prediction_path = (
        project_dir.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv"
    )
    result = run_validation(Project1OOTPredictionAdapter(prediction_path))

    records = build_persistence_records(
        result,
        ValidationRunMetadata(
            source_report_path="projects/credit-risk-pd-model/reports/oot_predictions.csv",
            source_commit_sha="abc123",
        ),
    )

    assert records.run["model_name"] == "logistic_regression"
    assert records.run["overall_status"] == "fail"
    assert records.run["source_commit_sha"] == "abc123"
    assert records.run["reference_start"].isoformat() == "2022-01-01"
    assert records.run["current_end"].isoformat() == "2022-12-01"
    assert len(records.metrics) == 6
    assert {record["check_name"] for record in records.metrics} == {
        "auc",
        "ks",
        "absolute_calibration_gap",
        "population_stability_index",
        "challenger_auc_margin",
        "maximum_characteristic_stability_index",
    }
    assert records.findings[0]["check_name"] == "absolute_calibration_gap"
    assert len(records.uncertainty) == 5
    assert {record["metric"] for record in records.uncertainty} == {
        "roc_auc",
        "observed_default_rate",
        "mean_predicted_pd",
        "calibration_gap",
        "brier_score",
    }
    assert all(record["confidence_level"] == 0.95 for record in records.uncertainty)
    assert len(records.group_performance) == (
        len(result.vintage_performance) + len(result.segment_performance)
    )
    assert {record["group_type"] for record in records.group_performance} == {
        "vintage",
        "segment",
    }
    assert len(records.characteristic_summaries) == len(
        result.characteristic_stability_summary
    )
    assert len(records.characteristic_bins) == len(result.characteristic_stability_bins)
    assert {record["feature_name"] for record in records.characteristic_summaries} == set(
        result.characteristic_stability_summary["feature_name"]
    )
    assert len(records.benchmarks) == 2
    assert len(records.limitations) == 4


def test_build_macro_satellite_persistence_records_maps_checks_and_findings(tmp_path):
    project_dir = Path(__file__).resolve().parents[1]
    developer_dir = (
        project_dir.parent / "ifrs9-ecl-engine" / "reports" / "macro_satellite"
    )
    validation = run_macro_satellite_validation(developer_dir, tmp_path)

    records = build_macro_satellite_persistence_records(
        validation.result,
        MacroSatelliteRunMetadata(
            source_report_path=(
                "projects/ifrs9-ecl-engine/reports/macro_satellite/"
                "backtest_predictions.csv"
            ),
            source_commit_sha="macro123",
        ),
    )

    assert records.run["overall_opinion"] == "restricted"
    assert records.run["intended_use"] == "sensitivity_only"
    assert records.run["oot_end"].isoformat() == "2021-12-31"
    assert records.run["source_commit_sha"] == "macro123"
    assert len(records.checks) == 9
    assert {record["status"] for record in records.checks} == {
        "pass",
        "warning",
        "fail",
    }
    assert {record["finding_id"] for record in records.findings} == {
        "MSV-001",
        "MSV-002",
        "MSV-003",
    }

    with pytest.raises(ValueError, match="does not match validated OOT evidence"):
        build_macro_satellite_persistence_records(
            validation.result,
            MacroSatelliteRunMetadata(
                source_report_path="backtest_predictions.csv",
                oot_end=date(2021, 9, 30),
            ),
        )


def test_build_macro_remediation_records_preserves_finding_lifecycle(tmp_path):
    project_dir = Path(__file__).resolve().parents[1]
    ifrs9_reports = project_dir.parent / "ifrs9-ecl-engine" / "reports"
    validation = run_macro_remediation_validation(
        ifrs9_reports / "macro_remediation",
        ifrs9_reports / "macro_satellite",
        project_dir / "reports" / "macro_satellite",
        tmp_path,
    )

    records = build_macro_remediation_persistence_records(
        validation.result,
        MacroRemediationRunMetadata(
            source_report_path=(
                "projects/model-validation-framework/reports/macro_remediation/"
                "macro_remediation_validation_report.md"
            ),
            source_commit_sha="remediation123",
        ),
    )

    assert records.run["selected_candidate_id"] == (
        "dynamic_ratio_change_lagged_macro"
    )
    assert records.run["selected_alpha"] == 1000.0
    assert records.run["overall_opinion"] == "restricted"
    assert records.run["evidence_freshness"] == "reused_oot"
    assert records.run["source_commit_sha"] == "remediation123"
    assert len(records.checks) == len(validation.result.validation_summary)
    assert len(records.events) == 6
    closure_events = [
        event for event in records.events if event["event_type"] == "closure_decision"
    ]
    assert {event["finding_id"] for event in closure_events} == {
        "MSV-001",
        "MSV-002",
        "MSV-003",
    }
    assert {event["event_status"] for event in closure_events} == {
        "open",
        "pending_fresh_oot",
    }
    assert all(event["event_status"] != "closed" for event in closure_events)
