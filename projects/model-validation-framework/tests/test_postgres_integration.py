import os
from pathlib import Path

import psycopg
import pytest

from model_validation import Project1OOTPredictionAdapter, run_validation
from model_validation.policy import ValidationPolicy
from model_validation.postgres import (
    ValidationRunMetadata,
    persist_remediation_result,
    persist_validation_result,
)
from model_validation.remediation import run_calibration_remediation


@pytest.mark.skipif(
    not os.getenv("MODEL_VALIDATION_TEST_DSN"),
    reason="MODEL_VALIDATION_TEST_DSN is not configured",
)
def test_validation_result_persists_to_real_postgresql_tables():
    project_dir = Path(__file__).resolve().parents[1]
    prediction_path = (
        project_dir.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv"
    )
    result = run_validation(Project1OOTPredictionAdapter(prediction_path))
    dsn = os.environ["MODEL_VALIDATION_TEST_DSN"]

    with psycopg.connect(dsn) as connection:
        connection.execute((project_dir / "sql" / "schema.sql").read_text(encoding="utf-8"))
        validation_run_id = persist_validation_result(
            connection,
            result,
            ValidationRunMetadata(
                source_report_path="projects/credit-risk-pd-model/reports/oot_predictions.csv",
                source_commit_sha="ci-integration-test",
            ),
        )
        persist_remediation_result(
            connection,
            validation_run_id,
            run_calibration_remediation(Project1OOTPredictionAdapter(prediction_path)),
        )
        metric_count = connection.execute(
            "SELECT COUNT(*) FROM model_validation_metric WHERE validation_run_id = %s",
            (validation_run_id,),
        ).fetchone()[0]
        uncertainty_count = connection.execute(
            "SELECT COUNT(*) FROM model_validation_uncertainty WHERE validation_run_id = %s",
            (validation_run_id,),
        ).fetchone()[0]
        group_count = connection.execute(
            "SELECT COUNT(*) FROM model_validation_group_performance WHERE validation_run_id = %s",
            (validation_run_id,),
        ).fetchone()[0]
        characteristic_summary_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM model_validation_characteristic_summary
            WHERE validation_run_id = %s
            """,
            (validation_run_id,),
        ).fetchone()[0]
        characteristic_bin_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM model_validation_characteristic_bin
            WHERE validation_run_id = %s
            """,
            (validation_run_id,),
        ).fetchone()[0]
        finding = connection.execute(
            """
            SELECT check_name, status
            FROM model_validation_finding
            WHERE validation_run_id = %s
            """,
            (validation_run_id,),
        ).fetchone()
        benchmark_count = connection.execute(
            "SELECT COUNT(*) FROM model_validation_benchmark WHERE validation_run_id = %s",
            (validation_run_id,),
        ).fetchone()[0]
        finding_lifecycle = connection.execute(
            """
            SELECT lifecycle_status
            FROM model_validation_finding
            WHERE validation_run_id = %s
            """,
            (validation_run_id,),
        ).fetchone()[0]
        finding_event_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM model_validation_finding_event AS event
            JOIN model_validation_finding AS finding USING (finding_id)
            WHERE finding.validation_run_id = %s
            """,
            (validation_run_id,),
        ).fetchone()[0]

        open_run_id = persist_validation_result(
            connection,
            result,
            ValidationRunMetadata(
                source_report_path="projects/credit-risk-pd-model/reports/oot_predictions.csv",
                source_commit_sha="ci-open-lifecycle-test",
            ),
        )
        open_remediation = run_calibration_remediation(
            Project1OOTPredictionAdapter(prediction_path),
            validation_policy=ValidationPolicy(
                absolute_calibration_gap_green_max=0.001,
                absolute_calibration_gap_warning_max=0.002,
            ),
        )
        persist_remediation_result(
            connection,
            open_run_id,
            open_remediation,
        )
        open_event_status = connection.execute(
            """
            SELECT event.event_status
            FROM model_validation_finding_event AS event
            JOIN model_validation_finding AS finding USING (finding_id)
            WHERE finding.validation_run_id = %s
              AND event.event_type = 'closure_decision'
            """,
            (open_run_id,),
        ).fetchone()[0]

    assert metric_count == 6
    assert uncertainty_count == 5
    assert group_count == len(result.vintage_performance) + len(result.segment_performance)
    assert characteristic_summary_count == len(result.characteristic_stability_summary)
    assert characteristic_bin_count == len(result.characteristic_stability_bins)
    assert finding == ("absolute_calibration_gap", "fail")
    assert benchmark_count == 2
    assert finding_lifecycle == "pending_fresh_oot"
    assert finding_event_count == 3
    assert open_event_status == "open"
