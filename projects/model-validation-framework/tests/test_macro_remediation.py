from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from model_validation.macro_remediation import validate_macro_remediation
from model_validation.macro_remediation_demo import run_macro_remediation_validation


def _developer_evidence() -> tuple[object, ...]:
    project_dir = Path(__file__).resolve().parents[1]
    ifrs9_reports = project_dir.parent / "ifrs9-ecl-engine" / "reports"
    remediation_dir = ifrs9_reports / "macro_remediation"
    incumbent_dir = ifrs9_reports / "macro_satellite"
    initial_validation_dir = project_dir / "reports" / "macro_satellite"
    selected_model = json.loads(
        (remediation_dir / "selected_model.json").read_text(encoding="utf-8")
    )
    return (
        pd.read_csv(remediation_dir / "candidate_register.csv"),
        pd.read_csv(remediation_dir / "candidate_tuning.csv"),
        selected_model,
        pd.read_csv(remediation_dir / "selected_coefficients.csv"),
        pd.read_csv(remediation_dir / "frozen_predictions.csv"),
        pd.read_csv(remediation_dir / "oot_comparison.csv"),
        pd.read_csv(remediation_dir / "governance_decision.csv"),
        pd.read_csv(incumbent_dir / "backtest_predictions.csv"),
        pd.read_csv(initial_validation_dir / "validation_findings.csv"),
    )


def test_independent_remediation_review_reperforms_evidence_and_defers_closure() -> None:
    result = validate_macro_remediation(*_developer_evidence())

    assert result.overall_opinion == "restricted"
    checks = result.validation_summary.set_index("check")
    assert checks.loc["selection_reperformance", "status"] == "pass"
    assert checks.loc["oot_selection_exclusion", "status"] == "pass"
    assert checks.loc["release_lag_compatibility", "status"] == "pass"
    assert checks.loc["oot_mae_vs_persistence", "status"] == "fail"
    assert checks.loc["oot_rmse_vs_persistence", "status"] == "pass"
    assert checks.loc["developer_metric_reconciliation", "status"] == "pass"
    assert checks.loc["fresh_oot_closure_evidence", "status"] == "fail"

    selection = result.selection_reperformance.iloc[0]
    assert selection["reperformed_candidate_id"] == selection[
        "developer_candidate_id"
    ]
    assert selection["reperformed_alpha"] == selection["developer_alpha"]
    assert selection["selection_reconciled"]

    lifecycle = result.finding_lifecycle.set_index("finding_id")
    assert lifecycle.loc["MSV-001", "closure_status"] == "open"
    assert lifecycle.loc["MSV-002", "closure_status"] == "pending_fresh_oot"
    assert lifecycle.loc["MSV-003", "closure_status"] == "open"
    assert "closed" not in set(lifecycle["closure_status"])
    assert set(lifecycle["evidence_freshness"]) == {"reused_oot"}


def test_macro_remediation_validation_pipeline_is_deterministic(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    ifrs9_reports = project_dir.parent / "ifrs9-ecl-engine" / "reports"
    kwargs = {
        "developer_remediation_dir": ifrs9_reports / "macro_remediation",
        "incumbent_report_dir": ifrs9_reports / "macro_satellite",
        "initial_validation_dir": project_dir / "reports" / "macro_satellite",
    }
    expected_files = {
        "finding_lifecycle.csv",
        "input_audit.csv",
        "macro_remediation_validation_report.md",
        "replicated_performance.csv",
        "selection_reperformance.csv",
        "validation_summary.csv",
    }

    first = run_macro_remediation_validation(
        **kwargs,
        output_dir=tmp_path / "first",
    )
    second = run_macro_remediation_validation(
        **kwargs,
        output_dir=tmp_path / "second",
    )

    assert set(first.report_paths) == expected_files
    assert set(second.report_paths) == expected_files
    for file_name in expected_files:
        assert first.report_paths[file_name].read_bytes() == second.report_paths[
            file_name
        ].read_bytes()
    report = first.report_paths[
        "macro_remediation_validation_report.md"
    ].read_text(encoding="utf-8")
    assert "Opinion: RESTRICTED" in report
    assert "MSV-001 remains open" in report
    assert "No finding is closed" in report


def test_macro_remediation_validation_cli_reproduces_opinion(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    ifrs9_reports = project_dir.parent / "ifrs9-ecl-engine" / "reports"
    output_dir = tmp_path / "cli"

    completed = subprocess.run(
        [
            sys.executable,
            str(project_dir / "scripts" / "run_macro_remediation_validation.py"),
            "--developer-remediation-dir",
            str(ifrs9_reports / "macro_remediation"),
            "--incumbent-report-dir",
            str(ifrs9_reports / "macro_satellite"),
            "--initial-validation-dir",
            str(project_dir / "reports" / "macro_satellite"),
            "--output-dir",
            str(output_dir),
        ],
        cwd=project_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Opinion: RESTRICTED" in completed.stdout
    assert "Closed findings: 0" in completed.stdout
    assert (output_dir / "macro_remediation_validation_report.md").is_file()


def test_independent_review_detects_oot_selection_and_false_closure_claims() -> None:
    oot_tampered = list(_developer_evidence())
    selected_model = dict(oot_tampered[2])
    selected_model["oot_used_for_selection"] = True
    oot_tampered[2] = selected_model

    oot_result = validate_macro_remediation(*oot_tampered)
    oot_checks = oot_result.validation_summary.set_index("check")
    assert oot_checks.loc["oot_selection_exclusion", "status"] == "fail"

    closure_tampered = list(_developer_evidence())
    governance = closure_tampered[6].copy()
    governance.loc[0, "finding_closure_claimed"] = True
    closure_tampered[6] = governance

    closure_result = validate_macro_remediation(*closure_tampered)
    closure_checks = closure_result.validation_summary.set_index("check")
    assert closure_checks.loc["developer_closure_control", "status"] == "fail"
    assert closure_result.overall_opinion == "restricted"

    metric_tampered = list(_developer_evidence())
    comparison = metric_tampered[5].copy()
    challenger = comparison["variant"].eq("selected_remediation")
    comparison.loc[challenger, "model_mae"] += 0.001
    metric_tampered[5] = comparison

    metric_result = validate_macro_remediation(*metric_tampered)
    metric_checks = metric_result.validation_summary.set_index("check")
    assert metric_checks.loc["developer_metric_reconciliation", "status"] == "fail"


def test_sql_contract_covers_macro_remediation_checks_and_events() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    schema = (project_dir / "sql" / "schema.sql").read_text(encoding="utf-8")

    assert "model_validation_macro_remediation_run" in schema
    assert "model_validation_macro_remediation_check" in schema
    assert "model_validation_macro_finding_event" in schema
    assert "pending_fresh_oot" in schema
    assert "evidence_freshness" in schema
