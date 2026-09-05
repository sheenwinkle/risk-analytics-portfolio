from pathlib import Path

from model_validation import Project1OOTPredictionAdapter, run_validation
from model_validation.postgres import ValidationRunMetadata, build_persistence_records


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
    assert len(records.metrics) == 5
    assert {record["check_name"] for record in records.metrics} == {
        "auc",
        "ks",
        "absolute_calibration_gap",
        "population_stability_index",
        "challenger_auc_margin",
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
    assert len(records.benchmarks) == 2
    assert len(records.limitations) == 4
