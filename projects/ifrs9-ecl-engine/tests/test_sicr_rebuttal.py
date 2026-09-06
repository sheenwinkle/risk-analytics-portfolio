from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from ifrs9_ecl_engine import SICRRebuttal, run_ecl_engine


def _account(*, days_past_due: int = 36, sicr: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": days_past_due,
                "sicr": sicr,
                "credit_impaired": False,
                "defaulted": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )


def _terms() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "scenario": scenario,
                "month": month,
                "marginal_pd": 0.001,
                "lgd": 0.35,
                "ead": 100_000,
            }
            for scenario in ["base", "downside"]
            for month in range(1, 25)
        ]
    )


def _approved_rebuttal() -> SICRRebuttal:
    return SICRRebuttal(
        rebuttal_id="SICR-REB-001",
        account_id="SYN-ECL-001",
        observed_days_past_due=36,
        evidence_reference="SYN-EVIDENCE-001",
        evidence_summary="Documented administrative payment delay with unchanged risk",
        reasonable_and_supportable=True,
        forward_looking_review_completed=True,
        other_sicr_indicators_present=False,
        decision_date="2023-12-20",
        valid_until="2024-03-31",
        approval_status="approved",
        approved_by="Synthetic ECL Committee",
    )


def test_effective_sicr_rebuttal_changes_only_the_30_dpd_presumption() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(_approved_rebuttal(),),
    )

    account = result.account_ecl.iloc[0]
    assert account["stage"] == 1
    assert account["stage_reason"] == "30_dpd_rebuttal_approved"
    assert set(result.scenario_ecl["ecl_horizon"]) == {"12-month"}
    assert set(result.scenario_ecl["months_included"]) == {12}

    decision = result.sicr_rebuttal_register.iloc[0]
    assert decision["decision_outcome"] == "approved_effective"
    assert decision["stage_without_rebuttal"] == 2
    assert decision["stage_with_rebuttal"] == 1


def test_explicit_sicr_indicator_cannot_be_rebutted_by_a_dpd_decision() -> None:
    result = run_ecl_engine(
        _account(sicr=True),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(_approved_rebuttal(),),
    )

    account = result.account_ecl.iloc[0]
    assert account["stage"] == 2
    assert account["stage_reason"] == "sicr_indicator"
    decision = result.sicr_rebuttal_register.iloc[0]
    assert decision["decision_outcome"] == "blocked_other_sicr_indicator"
    assert decision["stage_with_rebuttal"] == 2


def test_rebuttal_declared_other_sicr_indicator_blocks_stage_change() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(
            replace(_approved_rebuttal(), other_sicr_indicators_present=True),
        ),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert (
        result.sicr_rebuttal_register.loc[0, "decision_outcome"]
        == "blocked_other_sicr_indicator"
    )


def test_stage3_backstop_takes_precedence_over_sicr_rebuttal() -> None:
    result = run_ecl_engine(
        _account(days_past_due=95),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(replace(_approved_rebuttal(), observed_days_past_due=95),),
    )

    account = result.account_ecl.iloc[0]
    assert account["stage"] == 3
    assert account["stage_reason"] == "90_dpd_backstop"
    decision = result.sicr_rebuttal_register.iloc[0]
    assert decision["decision_outcome"] == "blocked_stage3_precedence"
    assert decision["stage_with_rebuttal"] == 3


def test_pending_rebuttal_does_not_change_stage() -> None:
    rebuttal = replace(
        _approved_rebuttal(),
        approval_status="pending",
        approved_by=None,
    )

    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(rebuttal,),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert result.sicr_rebuttal_register.loc[0, "decision_outcome"] == "pending_approval"


def test_expired_rebuttal_does_not_change_stage() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(replace(_approved_rebuttal(), valid_until="2023-12-30"),),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert result.sicr_rebuttal_register.loc[0, "decision_outcome"] == "expired"


def test_rebuttal_without_reasonable_supportable_evidence_is_blocked() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(
            replace(_approved_rebuttal(), reasonable_and_supportable=False),
        ),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert (
        result.sicr_rebuttal_register.loc[0, "decision_outcome"]
        == "blocked_insufficient_evidence"
    )


def test_rebuttal_without_forward_looking_review_is_blocked() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(
            replace(_approved_rebuttal(), forward_looking_review_completed=False),
        ),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert (
        result.sicr_rebuttal_register.loc[0, "decision_outcome"]
        == "blocked_forward_looking_review"
    )


def test_rebuttal_with_stale_dpd_evidence_is_blocked() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(replace(_approved_rebuttal(), observed_days_past_due=31),),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert result.sicr_rebuttal_register.loc[0, "decision_outcome"] == "blocked_dpd_mismatch"


def test_rebuttal_below_dpd_backstop_is_not_applicable() -> None:
    result = run_ecl_engine(
        _account(days_past_due=12),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(replace(_approved_rebuttal(), observed_days_past_due=12),),
    )

    assert result.account_ecl.loc[0, "stage"] == 1
    assert result.account_ecl.loc[0, "stage_reason"] == "performing"
    assert result.sicr_rebuttal_register.loc[0, "decision_outcome"] == "blocked_not_applicable"


def test_future_dated_rebuttal_does_not_leak_into_reporting_date() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(
            replace(
                _approved_rebuttal(),
                decision_date="2024-01-02",
                valid_until="2024-03-31",
            ),
        ),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert result.sicr_rebuttal_register.loc[0, "decision_outcome"] == "not_yet_effective"


def test_rejected_rebuttal_remains_in_stage2() -> None:
    result = run_ecl_engine(
        _account(),
        _terms(),
        {"base": 0.7, "downside": 0.3},
        reporting_date="2023-12-31",
        sicr_rebuttals=(
            replace(
                _approved_rebuttal(),
                approval_status="rejected",
                approved_by=None,
            ),
        ),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert result.sicr_rebuttal_register.loc[0, "decision_outcome"] == "rejected"


def test_duplicate_rebuttal_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="SICR rebuttal IDs must be unique"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(_approved_rebuttal(), _approved_rebuttal()),
        )


def test_multiple_rebuttals_for_one_account_are_rejected() -> None:
    with pytest.raises(ValueError, match="Only one SICR rebuttal is allowed per account"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                _approved_rebuttal(),
                replace(_approved_rebuttal(), rebuttal_id="SICR-REB-002"),
            ),
        )


def test_rebuttal_for_unknown_account_is_rejected() -> None:
    with pytest.raises(ValueError, match="SICR rebuttals contain unknown account IDs"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                replace(_approved_rebuttal(), account_id="SYN-ECL-UNKNOWN"),
            ),
        )


def test_approved_rebuttal_requires_named_approver() -> None:
    with pytest.raises(ValueError, match="approved_by is required for approved rebuttals"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(replace(_approved_rebuttal(), approved_by=None),),
        )


def test_optional_approver_must_be_named_when_provided() -> None:
    with pytest.raises(ValueError, match="approved_by must be a non-empty string"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                replace(
                    _approved_rebuttal(),
                    approval_status="pending",
                    approved_by=" ",
                ),
            ),
        )


def test_rebuttal_requires_reporting_date() -> None:
    with pytest.raises(ValueError, match="reporting_date is required"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            sicr_rebuttals=(_approved_rebuttal(),),
        )


def test_rebuttal_rejects_unknown_approval_status() -> None:
    with pytest.raises(ValueError, match="approval_status must be one of"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                replace(_approved_rebuttal(), approval_status="approve"),
            ),
        )


def test_rebuttal_dates_must_use_iso_format() -> None:
    with pytest.raises(ValueError, match="reporting_date must use YYYY-MM-DD"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="31/12/2023",
            sicr_rebuttals=(_approved_rebuttal(),),
        )


def test_rebuttal_validity_cannot_end_before_decision_date() -> None:
    with pytest.raises(ValueError, match="valid_until must not precede decision_date"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                replace(
                    _approved_rebuttal(),
                    decision_date="2023-12-20",
                    valid_until="2023-12-19",
                ),
            ),
        )


def test_rebuttal_observed_dpd_must_be_nonnegative_integer() -> None:
    with pytest.raises(ValueError, match="observed_days_past_due must be a nonnegative integer"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                replace(_approved_rebuttal(), observed_days_past_due=True),
            ),
        )


def test_rebuttal_control_flags_must_be_boolean() -> None:
    with pytest.raises(TypeError, match="reasonable_and_supportable must be boolean"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(
                replace(_approved_rebuttal(), reasonable_and_supportable="yes"),
            ),
        )


def test_rebuttal_evidence_fields_must_be_nonempty() -> None:
    with pytest.raises(ValueError, match="evidence_summary must be a non-empty string"):
        run_ecl_engine(
            _account(),
            _terms(),
            {"base": 0.7, "downside": 0.3},
            reporting_date="2023-12-31",
            sicr_rebuttals=(replace(_approved_rebuttal(), evidence_summary=" "),),
        )


def test_sql_schema_enforces_effective_rebuttal_controls() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    schema = (project_dir / "sql" / "schema.sql").read_text(encoding="utf-8")
    columns = """
        rebuttal_id, account_id, reporting_date, observed_days_past_due,
        current_days_past_due, stage2_dpd_backstop, stage3_dpd_backstop,
        presumption_applicable, evidence_reference, evidence_summary,
        reasonable_and_supportable, forward_looking_review_completed,
        other_sicr_indicators_present, decision_date, valid_until,
        approval_status, approved_by, decision_outcome, stage_without_rebuttal,
        stage_reason_without_rebuttal, stage_with_rebuttal,
        stage_reason_with_rebuttal
    """

    with sqlite3.connect(":memory:") as connection:
        connection.executescript(schema)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "ecl_sicr_rebuttal_decision",
            "ecl_sicr_rebuttal_reconciliation",
        }.issubset(tables)

        connection.execute(
            """
            INSERT INTO ecl_account_snapshot VALUES (
                'SYN-ECL-001', '2023-12-31', 36, FALSE, FALSE, FALSE,
                1, 0.12, 100000
            )
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"""
                INSERT INTO ecl_sicr_rebuttal_decision ({columns}) VALUES (
                    'SICR-REB-001', 'SYN-ECL-001', '2023-12-31', 36, 36,
                    30, 90, TRUE, 'EVIDENCE', 'Summary', TRUE, TRUE, FALSE,
                    '2023-12-20', '2024-03-31', 'approved', NULL,
                    'approved_effective', 2, '30_dpd_backstop', 1,
                    '30_dpd_rebuttal_approved'
                )
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"""
                INSERT INTO ecl_sicr_rebuttal_decision ({columns}) VALUES (
                    'SICR-REB-003', 'SYN-ECL-001', '2023-12-31', 36, 36,
                    30, 90, TRUE, 'EVIDENCE', 'Summary', TRUE, TRUE, FALSE,
                    '2023-12-20', '2024-03-31', 'pending', ' ',
                    'pending_approval', 2, '30_dpd_backstop', 2,
                    '30_dpd_backstop'
                )
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_sicr_rebuttal_reconciliation VALUES (
                    '2023-12-31', 100000, 1000, 900, -100, 100, 0.50,
                    0, 1, 0, 1, 0, 0, 1, 1, 0, 0
                )
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"""
                INSERT INTO ecl_sicr_rebuttal_decision ({columns}) VALUES (
                    'SICR-REB-002', 'SYN-ECL-001', '2023-12-31', 36, 36,
                    30, 90, TRUE, 'EVIDENCE', 'Summary', FALSE, TRUE, FALSE,
                    '2023-12-20', '2024-03-31', 'approved', 'Committee',
                    'approved_effective', 2, '30_dpd_backstop', 1,
                    '30_dpd_rebuttal_approved'
                )
                """
            )


def test_sicr_rebuttal_cli_writes_reproducible_decision_evidence(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    expected_files = [
        "account_stage_comparison.csv",
        "ecl_impact_reconciliation.csv",
        "sicr_rebuttal_register.csv",
        "sicr_rebuttal_report.md",
    ]

    for output_dir in [first_output, second_output]:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_sicr_rebuttal.py"),
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

    register = pd.read_csv(first_output / "sicr_rebuttal_register.csv")
    assert set(register["decision_outcome"]) == {
        "approved_effective",
        "blocked_other_sicr_indicator",
        "pending_approval",
    }
    comparison = pd.read_csv(first_output / "account_stage_comparison.csv")
    assert comparison["stage_changed"].sum() == 1
    reconciliation = pd.read_csv(first_output / "ecl_impact_reconciliation.csv").iloc[0]
    assert reconciliation["effective_rebuttal_count"] == 1
    assert reconciliation["governed_modelled_ecl"] < reconciliation[
        "baseline_modelled_ecl"
    ]
    assert reconciliation["ecl_change"] == pytest.approx(comparison["ecl_change"].sum())
    assert reconciliation["ecl_reduction"] == pytest.approx(
        reconciliation["baseline_modelled_ecl"]
        - reconciliation["governed_modelled_ecl"]
    )
    assert (
        reconciliation["baseline_stage1_accounts"]
        + reconciliation["baseline_stage2_accounts"]
        + reconciliation["baseline_stage3_accounts"]
    ) == len(comparison)
    assert (
        reconciliation["governed_stage1_accounts"]
        + reconciliation["governed_stage2_accounts"]
        + reconciliation["governed_stage3_accounts"]
    ) == len(comparison)
