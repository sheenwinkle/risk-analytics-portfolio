from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from ifrs9_ecl_engine.cashflow_demo import (
    build_demo_cashflow_inputs,
    run_cashflow_sensitivity_pipeline,
)


def test_demo_contractual_schedule_reconciles_to_synthetic_exposures() -> None:
    (
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
        scenario_weights,
        cases,
    ) = build_demo_cashflow_inputs()

    scheduled = contractual_schedule.groupby("account_id")[
        "contractual_principal_due"
    ].sum()
    exposures = accounts.set_index("account_id")["gross_exposure"]
    assert scheduled.sort_index().tolist() == pytest.approx(
        exposures.sort_index().tolist()
    )
    assert contractual_schedule.groupby("account_id")["month"].count().eq(36).all()
    assert set(marginal_pd_curves["scenario"]) == set(scenario_weights)
    assert len(recovery_assumptions) == len(accounts) * len(scenario_weights)
    assert [case.case_id for case in cases] == [
        "baseline",
        "low_prepayment",
        "low_cure",
        "collateral_downturn",
        "delayed_recovery",
        "combined_downside",
    ]
    assert sum(case.is_baseline for case in cases) == 1
    assert all(account_id.startswith("SYN-") for account_id in accounts["account_id"])


def test_demo_sensitivities_reconcile_and_each_downside_increases_ecl(
    tmp_path: Path,
) -> None:
    output = run_cashflow_sensitivity_pipeline(tmp_path)
    summary = output.analysis.portfolio_summary.set_index("case_id")
    baseline_ecl = summary.loc["baseline", "modelled_ecl"]

    assert (summary.drop(index="baseline")["modelled_ecl"] > baseline_ecl).all()
    assert summary.loc["combined_downside", "modelled_ecl"] == pytest.approx(
        summary["modelled_ecl"].max()
    )
    assert summary.loc["baseline", "ecl_change"] == pytest.approx(0.0)
    assert summary.loc["baseline", "ecl_change_pct"] == pytest.approx(0.0)

    reconciliation = output.reconciliation.set_index("case_id")
    assert reconciliation["reconciliation_difference"].abs().max() < 1e-9
    assert reconciliation["reconciled"].all()

    account_summary = output.analysis.account_summary
    stage_counts = account_summary.groupby(["case_id", "stage"])["account_id"].count()
    baseline_counts = stage_counts.loc["baseline"]
    for case_id in summary.index:
        assert stage_counts.loc[case_id].to_dict() == baseline_counts.to_dict()

    monthly = output.monthly_portfolio_projection
    assert len(monthly) == 6 * 3 * 36
    assert (monthly["portfolio_ead"] >= 0).all()
    assert monthly["ead_weighted_lgd"].between(0, 1).all()

    forbidden_columns = {
        "actual_default",
        "customer_id",
        "borrower_id",
        "realized_recovery",
        "future_outcome",
    }
    public_frames = [
        output.analysis.portfolio_summary,
        output.analysis.account_summary,
        output.reconciliation,
        output.monthly_portfolio_projection,
        output.contractual_schedule,
        output.recovery_assumptions,
    ]
    assert all(forbidden_columns.isdisjoint(frame.columns) for frame in public_frames)


def test_cashflow_cli_writes_reproducible_public_reports(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    expected_files = [
        "account_ecl_sensitivity.csv",
        "cashflow_reconciliation.csv",
        "cashflow_sensitivity_report.md",
        "cashflow_sensitivity_summary.csv",
        "contractual_schedule.csv",
        "monthly_portfolio_projection.csv",
        "recovery_assumptions.csv",
    ]

    for output_dir in [first_output, second_output]:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_cashflow_sensitivity.py"),
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

    report = (first_output / "cashflow_sensitivity_report.md").read_text(
        encoding="utf-8"
    )
    assert "not an IFRS 9 compliance conclusion" in report
    assert "contractual cash-flow" in report
    summary = pd.read_csv(first_output / "cashflow_sensitivity_summary.csv")
    assert summary["case_id"].tolist()[0] == "baseline"


def test_sql_schema_enforces_cashflow_sensitivity_controls() -> None:
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
            "ecl_contractual_cashflow",
            "ecl_recovery_assumption",
            "ecl_cashflow_sensitivity_case",
            "ecl_cashflow_account_result",
            "ecl_cashflow_monthly_projection",
            "ecl_cashflow_reconciliation",
        }.issubset(table_names)

        valid_case = (
            "baseline",
            "Neutral baseline",
            True,
            1.0,
            1.0,
            1.0,
            0.0,
            0,
            0,
            1000.0,
            100.0,
            0.1,
            0.0,
            0.0,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_cashflow_sensitivity_case VALUES (
                    'invalid_baseline', 'Non-neutral baseline', TRUE,
                    1, 0.8, 1, 0, 0, 0, 1000, 100, 0.1, 0, 0
                )
                """
            )
        connection.execute(
            """
            INSERT INTO ecl_cashflow_sensitivity_case VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            valid_case,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_cashflow_sensitivity_case VALUES (
                    'second_baseline', 'Invalid duplicate', TRUE,
                    1, 1, 1, 0, 0, 0, 1000, 100, 0.1, 0, 0
                )
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_recovery_assumption VALUES (
                    'SYN-ECL-001', 'base', 'unsecured', 'synthetic',
                    0.20, 0.50, 1.5, 0, 0.20, 0.05, 6, FALSE, FALSE
                )
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_recovery_assumption VALUES (
                    'SYN-ECL-001', 'base', 'unsecured', 'synthetic',
                    1.20, 0.50, 3, 0, 0.20, 0.05, 6, FALSE, FALSE
                )
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_cashflow_reconciliation VALUES (
                    'baseline', 100, 90, 0, TRUE
                )
                """
            )
