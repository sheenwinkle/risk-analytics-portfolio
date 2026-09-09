from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.macro_remediation import run_macro_satellite_remediation
from ifrs9_ecl_engine.macro_remediation_demo import run_macro_remediation_pipeline
from ifrs9_ecl_engine.macro_satellite import run_macro_satellite


def _public_macro_data() -> pd.DataFrame:
    project_dir = Path(__file__).resolve().parents[1]
    return pd.read_csv(
        project_dir / "data" / "public" / "australia_macro_credit.csv",
        parse_dates=["quarter"],
    )


def test_remediation_selection_is_isolated_from_reused_oot() -> None:
    data = _public_macro_data()

    result = run_macro_satellite_remediation(data)
    changed_oot = data.copy()
    oot = changed_oot["quarter"] > "2018-12-31"
    changed_oot.loc[oot, "npl_proxy_ratio"] *= 1.20
    changed_oot.loc[oot, "unemployment_rate_pct"] += 2.0
    changed_oot.loc[oot, "real_gdp_yoy_pct"] -= 3.0
    rerun = run_macro_satellite_remediation(changed_oot)

    pd.testing.assert_frame_equal(result.candidate_register, rerun.candidate_register)
    pd.testing.assert_frame_equal(result.tuning, rerun.tuning)
    pd.testing.assert_frame_equal(result.selection, rerun.selection)
    pd.testing.assert_frame_equal(result.coefficients, rerun.coefficients)
    assert not result.predictions.loc[
        result.predictions["split"] == "oot", "model_prediction"
    ].equals(
        rerun.predictions.loc[
            rerun.predictions["split"] == "oot", "model_prediction"
        ]
    )
    assert not bool(result.selection.loc[0, "oot_used_for_selection"])
    assert result.selection.loc[0, "selection_window"] == "2016Q1-2018Q4"


def test_remediation_metadata_tracks_custom_validation_and_oot_windows() -> None:
    data = _public_macro_data()
    data = data.loc[data["quarter"] <= "2020-12-31"].copy()
    result = run_macro_satellite_remediation(
        data,
        development_end="2014-12-31",
        validation_end="2017-12-31",
        oot_end="2020-12-31",
    )

    selection = result.selection.iloc[0]
    assert selection["selection_window"] == "2015Q1-2017Q4"
    assert selection["oot_evidence_freshness"] == "reused_2018Q1_2020Q4"
    assert set(result.oot_comparison["evidence_window"]) == {"2018Q1-2020Q4"}


def test_remediation_search_grid_does_not_redefine_the_incumbent() -> None:
    data = _public_macro_data()
    incumbent = run_macro_satellite(data).performance.set_index("split").loc["oot"]

    result = run_macro_satellite_remediation(data, alpha_grid=(10000.0,))
    comparison = result.oot_comparison.set_index("variant").loc[
        "incumbent_satellite"
    ]

    assert comparison["model_mae"] == incumbent["model_mae"]
    assert comparison["model_rmse"] == incumbent["model_rmse"]


def test_remediation_quantifies_improvement_without_claiming_finding_closure() -> None:
    result = run_macro_satellite_remediation(_public_macro_data())

    comparison = result.oot_comparison.set_index("variant")
    challenger = comparison.loc["selected_remediation"]
    incumbent = comparison.loc["incumbent_satellite"]
    assert challenger["model_mae"] < incumbent["model_mae"]
    assert challenger["mae_reduction_vs_incumbent"] > 0.10
    assert challenger["rmse_reduction_vs_incumbent"] > 0.20
    assert challenger["mae_improvement_vs_persistence"] < 0.0
    assert challenger["rmse_improvement_vs_persistence"] > 0.0

    decision = result.governance_decision.iloc[0]
    assert decision["developer_recommendation"] == "retain_restricted_use"
    assert decision["use_restriction"] == "sensitivity_only"
    assert decision["evidence_freshness"] == "reused_oot"
    assert not bool(decision["finding_closure_claimed"])


def test_macro_remediation_pipeline_writes_deterministic_auditable_evidence(
    tmp_path: Path,
) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    data_path = project_dir / "data" / "public" / "australia_macro_credit.csv"
    expected_files = {
        "candidate_register.csv",
        "candidate_tuning.csv",
        "frozen_predictions.csv",
        "governance_decision.csv",
        "input_audit.csv",
        "oot_comparison.csv",
        "performance_summary.csv",
        "remediation_report.md",
        "selected_coefficients.csv",
        "selected_model.json",
    }

    first = run_macro_remediation_pipeline(data_path, tmp_path / "first")
    second = run_macro_remediation_pipeline(data_path, tmp_path / "second")

    assert set(first.report_paths) == expected_files
    assert set(second.report_paths) == expected_files
    for file_name in expected_files:
        assert first.report_paths[file_name].read_bytes() == second.report_paths[
            file_name
        ].read_bytes()
    report = first.report_paths["remediation_report.md"].read_text(encoding="utf-8")
    assert "OOT was not used for candidate or hyperparameter selection" in report
    assert "does not close MSV-001" in report
    assert "not a realised loss saving" in report


def test_remediation_candidates_are_pre_registered_and_release_compatible() -> None:
    result = run_macro_satellite_remediation(_public_macro_data())

    candidates = result.candidate_register
    assert len(candidates) == 4
    assert set(candidates["target_form"]) == {"ratio_change", "logit_change"}
    assert set(candidates["forecast_horizon_quarters"]) == {1, 2}
    assert candidates["release_compatible"].all()
    assert candidates["eligible_for_selection"].all()
    assert (
        candidates["macro_lag_quarters"]
        >= candidates["forecast_horizon_quarters"]
    ).all()
    assert (result.coefficients["standardized_coefficient"] >= 0.0).all()
    active_macro = result.coefficients.loc[
        result.coefficients["feature_role"] == "macro_stress",
        "standardized_coefficient",
    ]
    assert len(active_macro) == 2
    assert (active_macro > 1e-12).all()


def test_macro_remediation_cli_reproduces_the_evidence_bundle(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "cli"

    completed = subprocess.run(
        [
            sys.executable,
            str(project_dir / "scripts" / "run_macro_remediation.py"),
            "--data-path",
            str(project_dir / "data" / "public" / "australia_macro_credit.csv"),
            "--output-dir",
            str(output_dir),
        ],
        cwd=project_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Selected candidate: dynamic_ratio_change_lagged_macro" in completed.stdout
    assert "Developer recommendation: retain_restricted_use" in completed.stdout
    assert (output_dir / "remediation_report.md").is_file()
