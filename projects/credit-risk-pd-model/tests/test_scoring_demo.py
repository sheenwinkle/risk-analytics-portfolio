from __future__ import annotations

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import joblib
import pandas as pd
import pytest

from credit_risk_pd.pipeline import run_pd_modelling_workflow
from credit_risk_pd.scoring_demo import run_scoring_service_demo
from credit_risk_pd.serving import write_deployment_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_scoring_demo_writes_privacy_safe_reconciliation_evidence(
    tmp_path: Path,
) -> None:
    pipeline = run_pd_modelling_workflow(
        output_dir=tmp_path / "model_reports",
        model_dir=tmp_path / "models",
    )
    write_deployment_manifest(
        pipeline["model"],
        joblib.load(pipeline["model"]),
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
        max_batch_size=100,
        output_path=pipeline["deployment_manifest"],
    )
    output = run_scoring_service_demo(
        model_path=pipeline["model"],
        manifest_path=pipeline["deployment_manifest"],
        prediction_path=pipeline["predictions"],
        output_dir=tmp_path / "scoring_reports",
        data_context="synthetic_demo",
    )

    assert set(output.report_paths) == {
        "data_quality_summary.csv",
        "score_band_summary.csv",
        "scoring_audit.csv",
        "scoring_reconciliation.csv",
        "scoring_service_report.md",
    }
    reconciliation = pd.read_csv(output.report_paths["scoring_reconciliation.csv"])
    assert reconciliation.loc[0, "records_replayed"] == 994
    assert reconciliation.loc[0, "batches_scored"] == 10
    assert reconciliation.loc[0, "data_context"] == "synthetic_demo"
    assert reconciliation.loc[0, "reporting_decimal_places"] == 12
    assert reconciliation.loc[0, "maximum_absolute_pd_delta"] == 0.0
    assert reconciliation.loc[0, "expected_mean_pd"] == reconciliation.loc[0, "service_mean_pd"]
    assert bool(reconciliation.loc[0, "replay_reconciled"])
    score_bands = pd.read_csv(
        output.report_paths["score_band_summary.csv"],
        dtype="string",
    )
    for column in (
        "mean_recalibrated_pd",
        "minimum_recalibrated_pd",
        "maximum_recalibrated_pd",
    ):
        values = score_bands[column].dropna().tolist()
        assert all(Decimal(value).as_tuple().exponent >= -12 for value in values)
    scoring_audit = pd.read_csv(
        output.report_paths["scoring_audit.csv"],
        dtype="string",
    )
    assert (
        Decimal(scoring_audit.loc[0, "mean_recalibrated_pd"]).as_tuple().exponent
        >= -12
    )

    for path in output.report_paths.values():
        if path.suffix == ".csv":
            assert "application_id" not in pd.read_csv(path, nrows=0).columns
    report = output.report_paths["scoring_service_report.md"].read_text(
        encoding="utf-8"
    )
    assert "Artifact integrity verified: **True**" in report
    assert "not local model attribution" in report
    assert "Data context: `synthetic_demo`" in report

    repeated = run_scoring_service_demo(
        model_path=pipeline["model"],
        manifest_path=pipeline["deployment_manifest"],
        prediction_path=pipeline["predictions"],
        output_dir=tmp_path / "repeated_scoring_reports",
        data_context="synthetic_demo",
    )
    for file_name, first_path in output.report_paths.items():
        assert first_path.read_bytes() == repeated.report_paths[file_name].read_bytes()

    cli_output_dir = tmp_path / "cli_scoring_reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_scoring_demo.py",
            "--manifest",
            str(pipeline["deployment_manifest"]),
            "--predictions",
            str(pipeline["predictions"]),
            "--output-dir",
            str(cli_output_dir),
            "--data-context",
            "synthetic_demo",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Scoring replay complete" in completed.stdout
    assert (cli_output_dir / "scoring_reconciliation.csv").is_file()

    duplicate_predictions = pd.read_csv(pipeline["predictions"]).iloc[:101].copy()
    duplicate_predictions.loc[
        duplicate_predictions.index[-1], "customer_id"
    ] = duplicate_predictions.loc[duplicate_predictions.index[0], "customer_id"]
    duplicate_path = tmp_path / "duplicate_predictions.csv"
    duplicate_predictions.to_csv(duplicate_path, index=False)
    with pytest.raises(ValueError, match="customer_id must be unique"):
        run_scoring_service_demo(
            model_path=pipeline["model"],
            manifest_path=pipeline["deployment_manifest"],
            prediction_path=duplicate_path,
            output_dir=tmp_path / "duplicate_reports",
        )
