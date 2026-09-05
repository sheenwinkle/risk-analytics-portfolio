from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from ifrs9_ecl_engine import (
    MacroSensitivityCase,
    ManagementOverlay,
    analyse_macro_sensitivity,
    evaluate_management_overlays,
    run_ecl_engine,
    run_macro_overlay_analysis,
)
from ifrs9_ecl_engine.demo import build_demo_inputs
from ifrs9_ecl_engine.governance_demo import build_demo_governance_inputs


def _scenario_ecl() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "scenario": "base",
                "scenario_weight": 0.7,
                "scenario_ecl": 100.0,
                "weighted_scenario_ecl": 70.0,
            },
            {
                "account_id": "SYN-ECL-001",
                "scenario": "downside",
                "scenario_weight": 0.3,
                "scenario_ecl": 200.0,
                "weighted_scenario_ecl": 60.0,
            },
        ]
    )


def _cases() -> tuple[MacroSensitivityCase, ...]:
    return (
        MacroSensitivityCase(
            case_id="baseline",
            description="Modelled scenario weights",
            scenario_weights={"base": 0.7, "downside": 0.3},
            is_baseline=True,
        ),
        MacroSensitivityCase(
            case_id="downside_weight_plus_20pp",
            description="Shift 20 percentage points from base to downside",
            scenario_weights={"base": 0.5, "downside": 0.5},
        ),
        MacroSensitivityCase(
            case_id="downside_severity_plus_20pct",
            description="Increase downside ECL severity by 20 percent",
            scenario_weights={"base": 0.7, "downside": 0.3},
            scenario_ecl_multipliers={"downside": 1.2},
        ),
    )


def _overlay(
    overlay_id: str,
    *,
    risk_driver: str,
    requested_amount: float = 200.0,
    cap_ratio: float = 0.1,
    overlap_assessment: str = "distinct",
    approval_status: str = "approved",
    approved_by: str | None = "ECL Committee",
    observed_value: float = 0.2,
) -> ManagementOverlay:
    return ManagementOverlay(
        overlay_id=overlay_id,
        risk_driver=risk_driver,
        scope="portfolio",
        trigger_metric="synthetic_risk_indicator",
        trigger_operator="greater_than_or_equal",
        observed_value=observed_value,
        trigger_threshold=0.15,
        requested_amount=requested_amount,
        cap_ratio_of_modelled_ecl=cap_ratio,
        overlap_assessment=overlap_assessment,
        modelled_risk_reference="Documented comparison with modelled scenario risks",
        approval_status=approval_status,
        approved_by=approved_by,
        rationale="Synthetic governance test request",
    )


def test_macro_sensitivity_separates_weight_and_severity_effects() -> None:
    result = analyse_macro_sensitivity(
        _scenario_ecl(),
        gross_exposure=10_000.0,
        cases=_cases(),
    )

    summary = result.summary.set_index("case_id")
    assert summary.loc["baseline", "modelled_ecl"] == pytest.approx(130.0)
    assert summary.loc["downside_weight_plus_20pp", "modelled_ecl"] == pytest.approx(150.0)
    assert summary.loc["downside_weight_plus_20pp", "change_vs_baseline"] == pytest.approx(20.0)
    assert summary.loc["downside_severity_plus_20pct", "modelled_ecl"] == pytest.approx(142.0)
    assert summary.loc["downside_severity_plus_20pct", "change_vs_baseline"] == pytest.approx(12.0)

    detail = result.detail.set_index(["case_id", "scenario"])
    downside = detail.loc[("downside_severity_plus_20pct", "downside")]
    assert downside["scenario_weight"] == pytest.approx(0.3)
    assert downside["scenario_ecl_multiplier"] == pytest.approx(1.2)
    assert downside["stressed_scenario_ecl"] == pytest.approx(240.0)
    assert downside["weighted_scenario_ecl"] == pytest.approx(72.0)


def test_macro_sensitivity_rejects_uncontrolled_case_definitions() -> None:
    invalid_cases = [
        (
            (
                MacroSensitivityCase(
                    case_id="baseline",
                    description="Bad weights",
                    scenario_weights={"base": 0.6, "downside": 0.3},
                    is_baseline=True,
                ),
            ),
            "Scenario weights must sum to 1",
        ),
        (
            (
                MacroSensitivityCase(
                    case_id="baseline",
                    description="Missing scenario",
                    scenario_weights={"base": 1.0},
                    is_baseline=True,
                ),
            ),
            "must cover exactly the modelled scenarios",
        ),
        (
            (
                MacroSensitivityCase(
                    case_id="baseline",
                    description="Changed baseline",
                    scenario_weights={"base": 0.5, "downside": 0.5},
                    is_baseline=True,
                ),
            ),
            "Baseline case weights must match",
        ),
    ]

    for cases, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            analyse_macro_sensitivity(
                _scenario_ecl(),
                gross_exposure=10_000.0,
                cases=cases,
            )


def test_macro_sensitivity_accepts_six_decimal_report_rounding() -> None:
    scenario_ecl = _scenario_ecl()
    scenario_ecl.loc[0, "scenario_ecl"] = 100.123456
    scenario_ecl.loc[0, "weighted_scenario_ecl"] = round(100.123456 * 0.7, 6)

    result = analyse_macro_sensitivity(scenario_ecl, 10_000.0, _cases())

    assert result.summary.loc[0, "modelled_ecl"] == pytest.approx(130.0864192)


def test_overlay_controls_cap_and_separately_disclose_every_request() -> None:
    requests = (
        _overlay("OVL-001", risk_driver="unmodelled_cost_pressure"),
        _overlay(
            "OVL-002",
            risk_driver="broad_macro_deterioration",
            overlap_assessment="captured_by_model",
        ),
        _overlay(
            "OVL-003",
            risk_driver="industry_concentration",
            approval_status="pending",
            approved_by=None,
        ),
        _overlay(
            "OVL-004",
            risk_driver="inactive_trigger",
            observed_value=0.1,
        ),
    )

    result = evaluate_management_overlays(
        modelled_ecl=1_000.0,
        gross_exposure=10_000.0,
        overlays=requests,
    )

    register = result.overlay_register.set_index("overlay_id")
    assert len(register) == 4
    assert register.loc["OVL-001", "cap_amount"] == pytest.approx(100.0)
    assert register.loc["OVL-001", "cap_binding"]
    assert register.loc["OVL-001", "recognized_amount"] == pytest.approx(100.0)
    assert register.loc["OVL-001", "recognition_status"] == "recognized_capped"
    assert register.loc["OVL-002", "double_counting_check"] == "fail"
    assert register.loc["OVL-002", "recognition_status"] == "blocked_model_overlap"
    assert register.loc["OVL-002", "recognized_amount"] == 0
    assert register.loc["OVL-003", "recognition_status"] == "pending_approval"
    assert register.loc["OVL-004", "recognition_status"] == "blocked_trigger_not_met"

    reconciliation = result.reconciliation.iloc[0]
    assert reconciliation["baseline_modelled_ecl"] == pytest.approx(1_000.0)
    assert reconciliation["recognized_management_overlay"] == pytest.approx(100.0)
    assert reconciliation["illustrative_reported_ecl"] == pytest.approx(1_100.0)
    assert reconciliation["modelled_coverage_ratio"] == pytest.approx(0.1)
    assert reconciliation["illustrative_reported_coverage_ratio"] == pytest.approx(0.11)


def test_overlay_controls_reject_invalid_governance_records() -> None:
    with pytest.raises(ValueError, match="Overlay IDs must be unique"):
        evaluate_management_overlays(
            1_000.0,
            10_000.0,
            (
                _overlay("OVL-001", risk_driver="driver_a"),
                _overlay("OVL-001", risk_driver="driver_b"),
            ),
        )

    with pytest.raises(ValueError, match="risk driver and scope must be unique"):
        evaluate_management_overlays(
            1_000.0,
            10_000.0,
            (
                _overlay("OVL-001", risk_driver="driver_a"),
                _overlay("OVL-002", risk_driver="driver_a"),
            ),
        )

    with pytest.raises(ValueError, match="approved_by is required"):
        evaluate_management_overlays(
            1_000.0,
            10_000.0,
            (_overlay("OVL-001", risk_driver="driver_a", approved_by=None),),
        )


def test_overlay_supports_lower_bound_trigger_and_uncapped_recognition() -> None:
    overlay = replace(
        _overlay(
            "OVL-001",
            risk_driver="lower_bound_driver",
            requested_amount=40.0,
        ),
        trigger_operator="less_than_or_equal",
        observed_value=0.1,
        trigger_threshold=0.15,
    )

    result = evaluate_management_overlays(1_000.0, 10_000.0, (overlay,))

    row = result.overlay_register.iloc[0]
    assert row["trigger_met"]
    assert not row["cap_binding"]
    assert row["recognition_status"] == "recognized"
    assert row["recognized_amount"] == pytest.approx(40.0)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"requested_amount": -1.0}, "requested_amount must be nonnegative"),
        (
            {"cap_ratio_of_modelled_ecl": 1.01},
            "cap_ratio_of_modelled_ecl must be between 0 and 1",
        ),
        ({"trigger_operator": "equals"}, "trigger_operator must be one of"),
        ({"overlap_assessment": "unknown"}, "overlap_assessment must be one of"),
        ({"approval_status": "unknown"}, "approval_status must be one of"),
        ({"approved_by": 123}, "approved_by is required"),
    ],
)
def test_overlay_rejects_invalid_control_values(
    changes: dict[str, object],
    message: str,
) -> None:
    overlay = replace(_overlay("OVL-001", risk_driver="driver_a"), **changes)

    with pytest.raises(ValueError, match=message):
        evaluate_management_overlays(1_000.0, 10_000.0, (overlay,))


def test_full_analysis_keeps_unbooked_sensitivity_out_of_reported_ecl() -> None:
    accounts, term_structures, scenario_weights = build_demo_inputs()
    ecl_result = run_ecl_engine(accounts, term_structures, scenario_weights)
    cases, overlays = build_demo_governance_inputs()

    analysis = run_macro_overlay_analysis(ecl_result, cases, overlays)

    reconciliation = analysis.reconciliation.iloc[0]
    expected_reported = (
        reconciliation["baseline_modelled_ecl"]
        + reconciliation["recognized_management_overlay"]
    )
    assert reconciliation["illustrative_reported_ecl"] == pytest.approx(expected_reported)
    assert reconciliation["highest_sensitivity_delta_not_booked"] > 0
    assert reconciliation["illustrative_reported_ecl"] != pytest.approx(
        reconciliation["highest_sensitivity_ecl"]
        + reconciliation["recognized_management_overlay"]
    )


def test_macro_sensitivity_rejects_duplicate_cases_and_invalid_multiplier() -> None:
    duplicate_cases = (_cases()[0], _cases()[0])
    with pytest.raises(ValueError, match="case IDs must be unique"):
        analyse_macro_sensitivity(_scenario_ecl(), 10_000.0, duplicate_cases)

    invalid_multiplier = replace(
        _cases()[0],
        scenario_ecl_multipliers={"downside": -0.1},
    )
    with pytest.raises(ValueError, match="must be nonnegative"):
        analyse_macro_sensitivity(_scenario_ecl(), 10_000.0, (invalid_multiplier,))

    invalid_baseline_flag = replace(_cases()[0], is_baseline="yes")
    with pytest.raises(ValueError, match="is_baseline must be boolean"):
        analyse_macro_sensitivity(_scenario_ecl(), 10_000.0, (invalid_baseline_flag,))

    boolean_weight = replace(
        _cases()[0],
        scenario_weights={"base": True, "downside": 0.0},
    )
    with pytest.raises(TypeError, match="Scenario weight for base must be numeric"):
        analyse_macro_sensitivity(_scenario_ecl(), 10_000.0, (boolean_weight,))


def test_sql_schema_persists_sensitivity_overlay_and_reconciliation_controls() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    schema = (project_dir / "sql" / "schema.sql").read_text(encoding="utf-8")

    with sqlite3.connect(":memory:") as connection:
        connection.executescript(schema)
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "ecl_macro_sensitivity_case",
            "ecl_management_overlay",
            "ecl_reporting_reconciliation",
        }.issubset(table_names)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_management_overlay (
                    overlay_id, risk_driver, scope, trigger_metric, trigger_operator,
                    observed_value, trigger_threshold, trigger_met, requested_amount,
                    cap_ratio_of_modelled_ecl, cap_amount, cap_binding,
                    overlap_assessment, modelled_risk_reference,
                    double_counting_check, approval_status, approved_by, rationale,
                    recognition_status, recognized_amount
                ) VALUES (
                    'OVL-INVALID', 'driver', 'portfolio', 'metric',
                    'greater_than_or_equal', 0.2, 0.1, TRUE, 100, 0.1, 100,
                    FALSE, 'distinct', 'reference', 'pass', 'approved', NULL,
                    'missing approver', 'recognized', 100
                )
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_management_overlay (
                    overlay_id, risk_driver, scope, trigger_metric, trigger_operator,
                    observed_value, trigger_threshold, trigger_met, requested_amount,
                    cap_ratio_of_modelled_ecl, cap_amount, cap_binding,
                    overlap_assessment, modelled_risk_reference,
                    double_counting_check, approval_status, approved_by, rationale,
                    recognition_status, recognized_amount
                ) VALUES (
                    'OVL-INCONSISTENT', 'driver', 'portfolio', 'metric',
                    'greater_than_or_equal', 0.05, 0.1, FALSE, 100, 0.1, 100,
                    FALSE, 'distinct', 'reference', 'pass', 'pending', NULL,
                    'failed controls', 'recognized', 100
                )
                """
            )


def test_macro_overlay_cli_writes_reproducible_governance_reports(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    expected_files = [
        "ecl_reconciliation.csv",
        "macro_overlay_report.md",
        "macro_sensitivity_detail.csv",
        "macro_sensitivity_summary.csv",
        "management_overlay_register.csv",
    ]

    for output_dir in [first_output, second_output]:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_macro_overlay.py"),
                "--output-dir",
                str(output_dir),
            ],
            cwd=project_dir,
            check=True,
        )
        assert sorted(path.name for path in output_dir.iterdir()) == expected_files

    for report_name in expected_files:
        assert (first_output / report_name).read_bytes() == (
            second_output / report_name
        ).read_bytes()

    register = pd.read_csv(first_output / "management_overlay_register.csv")
    assert set(register["recognition_status"]) == {
        "blocked_model_overlap",
        "pending_approval",
        "recognized_capped",
    }
    reconciliation = pd.read_csv(first_output / "ecl_reconciliation.csv").iloc[0]
    assert reconciliation["illustrative_reported_ecl"] > reconciliation[
        "baseline_modelled_ecl"
    ]
