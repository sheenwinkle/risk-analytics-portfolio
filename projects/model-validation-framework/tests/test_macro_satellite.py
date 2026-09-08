from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from model_validation.macro_satellite import validate_macro_satellite


def _validation_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictions = pd.DataFrame(
        {
            "quarter": pd.date_range("2019-03-31", periods=12, freq="QE"),
            "split": "oot",
            "actual_npl_ratio": [0.0100, 0.0102, 0.0101, 0.0103] * 3,
            "model_prediction": [0.0090, 0.0115, 0.0090, 0.0116] * 3,
            "persistence_prediction": [0.0099, 0.0100, 0.0102, 0.0101] * 3,
            "model_residual": [0.0010, -0.0013, 0.0011, -0.0013] * 3,
            "unemployment_rate_pct": [5.0] * 12,
            "real_gdp_yoy_pct": [2.0] * 12,
        }
    )
    coefficients = pd.DataFrame(
        {
            "feature": [
                "lag_logit_npl",
                "unemployment_rate_pct",
                "gdp_stress_pct",
            ],
            "feature_role": ["autoregressive", "macro_stress", "macro_stress"],
            "standardized_coefficient": [0.5, 0.0, 0.03],
            "raw_coefficient": [1.0, 0.0, 0.02],
            "constraint": ["nonnegative"] * 3,
        }
    )
    tuning = pd.DataFrame(
        {
            "alpha": [0.01, 0.1, 1.0],
            "validation_mae": [0.001, 0.0011, 0.0012],
            "validation_observations": [12] * 3,
        }
    )
    scenarios = pd.DataFrame(
        {
            "scenario": ["upside", "base", "downside"],
            "npl_multiplier": [0.9, 1.0, 1.2],
            "evidence_use": ["sensitivity_only"] * 3,
        }
    )
    return predictions, coefficients, tuning, scenarios


def test_independent_macro_validation_restricts_failed_point_forecast() -> None:
    result = validate_macro_satellite(*_validation_inputs())

    summary = result.validation_summary.set_index("check")
    assert result.overall_opinion == "restricted"
    assert summary.loc["oot_mae_vs_persistence", "status"] == "fail"
    assert summary.loc["scenario_directionality", "status"] == "pass"
    assert summary.loc["active_macro_drivers", "status"] == "warning"
    assert summary.loc["real_time_data_vintage", "status"] == "warning"
    assert set(result.findings["finding_id"]) == {"MSV-001", "MSV-002", "MSV-003"}
    assert result.replicated_performance.loc[0, "model_mae"] > result.replicated_performance.loc[
        0, "persistence_mae"
    ]


def test_macro_validation_clears_data_vintage_finding_only_with_explicit_evidence() -> None:
    result = validate_macro_satellite(
        *_validation_inputs(),
        real_time_vintage_evidenced=True,
    )

    summary = result.validation_summary.set_index("check")
    assert summary.loc["real_time_data_vintage", "status"] == "pass"
    assert "MSV-003" not in set(result.findings["finding_id"])

    with pytest.raises(TypeError, match="must be boolean"):
        validate_macro_satellite(
            *_validation_inputs(),
            real_time_vintage_evidenced="yes",
        )


def test_macro_validation_rejects_changed_oot_window_and_duplicate_scenarios() -> None:
    predictions, coefficients, tuning, scenarios = _validation_inputs()
    shifted = predictions.copy()
    shifted["quarter"] = pd.date_range("2018-12-31", periods=12, freq="QE")
    with pytest.raises(ValueError, match="frozen 2019-2021 OOT window"):
        validate_macro_satellite(shifted, coefficients, tuning, scenarios)

    duplicated = pd.concat([scenarios, scenarios.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="exactly once"):
        validate_macro_satellite(predictions, coefficients, tuning, duplicated)


def test_macro_validation_cli_reproduces_restricted_opinion(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    repo_root = project_dir.parents[1]
    developer_dir = repo_root / "projects" / "ifrs9-ecl-engine" / "reports" / "macro_satellite"
    expected_files = [
        "input_audit.csv",
        "macro_validation_report.md",
        "replicated_performance.csv",
        "validation_findings.csv",
        "validation_summary.csv",
    ]
    output_dirs = [tmp_path / "first", tmp_path / "second"]

    for output_dir in output_dirs:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_macro_satellite_validation.py"),
                "--developer-report-dir",
                str(developer_dir),
                "--output-dir",
                str(output_dir),
            ],
            cwd=project_dir,
            check=True,
        )
        assert sorted(path.name for path in output_dir.iterdir()) == expected_files

    for report_name in expected_files:
        assert (output_dirs[0] / report_name).read_bytes() == (
            output_dirs[1] / report_name
        ).read_bytes()
    summary = pd.read_csv(output_dirs[0] / "validation_summary.csv")
    assert "fail" in set(summary["status"])
    report = (output_dirs[0] / "macro_validation_report.md").read_text(encoding="utf-8")
    assert "RESTRICTED" in report


def test_sql_contract_covers_macro_checks_and_findings() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    schema = (project_dir / "sql" / "schema.sql").read_text(encoding="utf-8")
    queries = (project_dir / "sql" / "example_queries.sql").read_text(encoding="utf-8")

    assert "model_validation_macro_check" in schema
    assert "model_validation_macro_finding" in schema
    assert "oot_mae_vs_persistence" in queries
    assert "sensitivity_only" in queries
