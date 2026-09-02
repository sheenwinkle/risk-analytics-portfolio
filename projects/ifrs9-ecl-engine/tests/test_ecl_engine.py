from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from ifrs9_ecl_engine import StagingPolicy, run_ecl_engine


def _term_rows(account_id: str, months: int, pd_rate: float, lgd: float, ead: float) -> list[dict]:
    rows = []
    for scenario in ["base", "upside"]:
        multiplier = 1.0 if scenario == "base" else 0.8
        for month in range(1, months + 1):
            rows.append(
                {
                    "account_id": account_id,
                    "scenario": scenario,
                    "month": month,
                    "marginal_pd": pd_rate * multiplier,
                    "lgd": lgd,
                    "ead": ead,
                }
            )
    return rows


def _discounted_loss(months: int, pd_rate: float, lgd: float, ead: float, eir: float) -> float:
    return sum(pd_rate * lgd * ead / ((1 + eir) ** (month / 12)) for month in range(1, months + 1))


def test_run_ecl_engine_stages_accounts_and_weights_scenario_losses() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            },
            {
                "account_id": "SYN-ECL-002",
                "days_past_due": 45,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.06,
                "gross_exposure": 80_000,
            },
            {
                "account_id": "SYN-ECL-003",
                "days_past_due": 95,
                "sicr": True,
                "credit_impaired": False,
                "prior_stage": 2,
                "effective_interest_rate": 0.09,
                "gross_exposure": 30_000,
            },
        ]
    )
    term_structures = pd.DataFrame(
        _term_rows("SYN-ECL-001", 18, 0.001, 0.35, 100_000)
        + _term_rows("SYN-ECL-002", 18, 0.002, 0.40, 80_000)
        + _term_rows("SYN-ECL-003", 18, 0.008, 0.55, 30_000)
    )

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
    )

    account_rows = result.account_ecl.set_index("account_id")
    assert account_rows["stage"].to_dict() == {
        "SYN-ECL-001": 1,
        "SYN-ECL-002": 2,
        "SYN-ECL-003": 3,
    }
    assert account_rows["stage_reason"].to_dict() == {
        "SYN-ECL-001": "performing",
        "SYN-ECL-002": "30_dpd_backstop",
        "SYN-ECL-003": "90_dpd_backstop",
    }

    scenario_rows = result.scenario_ecl.set_index(["account_id", "scenario"])
    assert scenario_rows.loc[("SYN-ECL-001", "base"), "scenario_ecl"] == pytest.approx(
        _discounted_loss(12, 0.001, 0.35, 100_000, 0.12)
    )
    assert scenario_rows.loc[("SYN-ECL-002", "base"), "scenario_ecl"] == pytest.approx(
        _discounted_loss(18, 0.002, 0.40, 80_000, 0.06)
    )
    assert scenario_rows.loc[("SYN-ECL-003", "upside"), "scenario_ecl"] == pytest.approx(
        _discounted_loss(18, 0.008 * 0.8, 0.55, 30_000, 0.09)
    )

    expected_weighted = (
        _discounted_loss(12, 0.001, 0.35, 100_000, 0.12) * 0.7
        + _discounted_loss(12, 0.001 * 0.8, 0.35, 100_000, 0.12) * 0.3
    )
    assert account_rows.loc["SYN-ECL-001", "weighted_ecl"] == pytest.approx(expected_weighted)


def test_run_ecl_engine_rejects_scenario_weights_that_do_not_sum_to_one() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))

    with pytest.raises(ValueError, match="Scenario weights must sum to 1"):
        run_ecl_engine(
            accounts,
            term_structures,
            scenario_weights={"base": 0.7, "upside": 0.2},
        )


def test_run_ecl_engine_rejects_invalid_account_and_term_inputs() -> None:
    valid_accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            },
            {
                "account_id": "SYN-ECL-002",
                "days_past_due": 35,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.10,
                "gross_exposure": 80_000,
            },
        ]
    )
    valid_terms = pd.DataFrame(
        _term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000)
        + _term_rows("SYN-ECL-002", 12, 0.002, 0.40, 80_000)
    )

    cases = [
        (
            valid_accounts.drop(columns=["days_past_due"]),
            valid_terms,
            "accounts missing required columns: days_past_due",
        ),
        (
            valid_accounts.drop(columns=["gross_exposure"]),
            valid_terms,
            "accounts missing required columns: gross_exposure",
        ),
        (
            pd.concat([valid_accounts, valid_accounts.iloc[[0]]], ignore_index=True),
            valid_terms,
            "Account IDs must be unique",
        ),
        (
            valid_accounts,
            pd.concat([valid_terms, valid_terms.iloc[[0]]], ignore_index=True),
            "term_structures must contain one row per account/scenario/month",
        ),
        (
            valid_accounts,
            valid_terms.assign(marginal_pd=float("nan")),
            "term_structures.marginal_pd must contain finite numeric values",
        ),
        (
            valid_accounts,
            valid_terms.assign(month=0),
            "term_structures.month must be a positive integer",
        ),
        (
            valid_accounts,
            valid_terms.assign(lgd=1.2),
            "term_structures.lgd must be between 0 and 1",
        ),
        (
            valid_accounts,
            valid_terms.assign(ead=-1),
            "term_structures.ead must be nonnegative",
        ),
        (
            valid_accounts.assign(effective_interest_rate=-1.0),
            valid_terms,
            "accounts.effective_interest_rate must be greater than -1",
        ),
        (
            valid_accounts.assign(gross_exposure=-1.0),
            valid_terms,
            "accounts.gross_exposure must be nonnegative",
        ),
        (
            valid_accounts,
            valid_terms[valid_terms["scenario"] == "base"],
            "Term structures must cover every scenario weight",
        ),
        (
            valid_accounts,
            valid_terms[valid_terms["month"] != 6],
            "Term structures must contain contiguous monthly terms",
        ),
    ]

    for bad_accounts, bad_terms, message in cases:
        with pytest.raises(ValueError, match=message):
            run_ecl_engine(
                bad_accounts,
                bad_terms,
                scenario_weights={"base": 0.7, "upside": 0.3},
            )


def test_run_ecl_engine_applies_default_flags_and_configurable_dpd_backstops() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 95,
                "sicr": False,
                "credit_impaired": False,
                "defaulted": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            },
            {
                "account_id": "SYN-ECL-002",
                "days_past_due": 5,
                "sicr": False,
                "credit_impaired": False,
                "defaulted": True,
                "prior_stage": 2,
                "effective_interest_rate": 0.10,
                "gross_exposure": 80_000,
            },
        ]
    )
    term_structures = pd.DataFrame(
        _term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000)
        + _term_rows("SYN-ECL-002", 12, 0.002, 0.40, 80_000)
    )

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
        policy=StagingPolicy(stage2_dpd_backstop=None, stage3_dpd_backstop=None),
    )

    account_rows = result.account_ecl.set_index("account_id")
    assert account_rows["stage"].to_dict() == {"SYN-ECL-001": 1, "SYN-ECL-002": 3}
    assert account_rows.loc["SYN-ECL-002", "stage_reason"] == "defaulted"
    assert account_rows.loc["SYN-ECL-002", "defaulted"] is True


def test_default_cli_pipeline_writes_reproducible_reports(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    expected_files = [
        "account_ecl.csv",
        "scenario_ecl.csv",
        "portfolio_summary.csv",
        "stage_migration.csv",
        "ecl_report.md",
    ]

    for output_dir in [first_output, second_output]:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_pipeline.py"),
                "--output-dir",
                str(output_dir),
            ],
            cwd=project_dir,
            check=True,
        )
        assert sorted(path.name for path in output_dir.iterdir()) == sorted(expected_files)

    for report_name in expected_files:
        assert (first_output / report_name).read_bytes() == (
            second_output / report_name
        ).read_bytes()

    account_ecl = pd.read_csv(first_output / "account_ecl.csv")
    assert account_ecl["account_id"].str.startswith("SYN-ECL-").all()


def test_run_ecl_engine_returns_auditable_account_and_scenario_rows() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 31,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 15, 0.001, 0.35, 100_000))

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
    )

    account_row = result.account_ecl.iloc[0]
    assert account_row["stage"] == 2
    assert account_row["stage_reason"] == "30_dpd_backstop"
    assert account_row["days_past_due"] == 31
    assert account_row["sicr"] is False
    assert account_row["credit_impaired"] is False
    assert account_row["defaulted"] is False
    assert account_row["effective_interest_rate"] == 0.12

    scenario_row = result.scenario_ecl.set_index("scenario").loc["base"]
    assert scenario_row["ecl_horizon"] == "lifetime"
    assert scenario_row["months_included"] == 15
    assert scenario_row["first_month"] == 1
    assert scenario_row["last_month"] == 15
    assert scenario_row["scenario_weight"] == 0.7
    assert scenario_row["stage_reason"] == "30_dpd_backstop"


def test_run_ecl_engine_rejects_governance_edge_cases() -> None:
    valid_accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )
    valid_terms = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))

    cases = [
        (
            valid_accounts.iloc[0:0],
            valid_terms,
            "accounts must contain at least one row",
        ),
        (
            valid_accounts,
            valid_terms.iloc[0:0],
            "term_structures must contain at least one row",
        ),
        (
            valid_accounts.assign(account_id=""),
            valid_terms,
            "accounts.account_id must contain non-empty values",
        ),
        (
            valid_accounts,
            valid_terms.assign(scenario=""),
            "term_structures.scenario must contain non-empty values",
        ),
        (
            valid_accounts.assign(sicr="yes"),
            valid_terms,
            "accounts.sicr must contain only boolean values",
        ),
        (
            valid_accounts.assign(prior_stage=4),
            valid_terms,
            "accounts.prior_stage must be one of 1, 2, or 3",
        ),
        (
            valid_accounts,
            valid_terms[~(valid_terms["scenario"].eq("upside") & valid_terms["month"].eq(12))],
            "Term structures must have coherent scenario horizons",
        ),
        (
            valid_accounts,
            valid_terms.assign(marginal_pd=0.10),
            "Cumulative marginal PD must be less than or equal to 1",
        ),
    ]

    for bad_accounts, bad_terms, message in cases:
        with pytest.raises(ValueError, match=message):
            run_ecl_engine(
                bad_accounts,
                bad_terms,
                scenario_weights={"base": 0.7, "upside": 0.3},
            )

    with pytest.raises(ValueError, match="stage2_dpd_backstop must be positive when set"):
        StagingPolicy(stage2_dpd_backstop=0)


def test_run_ecl_engine_reports_zero_coverage_ratio_for_zero_exposure() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 0,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 0))

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
    )

    assert result.account_ecl.loc[0, "coverage_ratio"] == 0
    total = result.portfolio_summary[result.portfolio_summary["stage"] == "Total"].iloc[0]
    assert total["coverage_ratio"] == 0


def test_run_ecl_engine_uses_reporting_date_gross_exposure() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 125_000,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))
    term_structures.loc[term_structures["scenario"] == "upside", "ead"] = 80_000

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
    )

    account_row = result.account_ecl.iloc[0]
    assert account_row["gross_exposure"] == 125_000
    assert account_row["coverage_ratio"] == pytest.approx(
        account_row["weighted_ecl"] / 125_000
    )


def test_run_ecl_engine_normalizes_numeric_string_inputs() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": "31",
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": "1",
                "effective_interest_rate": "0.12",
                "gross_exposure": "100000",
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))
    for column in ["month", "marginal_pd", "lgd", "ead"]:
        term_structures[column] = term_structures[column].astype(str)

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": "0.7", "upside": "0.3"},
    )

    account_row = result.account_ecl.iloc[0]
    assert account_row["stage"] == 2
    assert account_row["gross_exposure"] == 100_000
    assert account_row["weighted_ecl"] > 0


def test_run_ecl_engine_validates_and_reports_optional_default_flag() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "defaulted": True,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))

    with pytest.raises(ValueError, match="accounts.defaulted must contain only boolean values"):
        run_ecl_engine(
            accounts.assign(defaulted="yes"),
            term_structures,
            scenario_weights={"base": 0.7, "upside": 0.3},
        )

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
    )
    account_row = result.account_ecl.iloc[0]
    assert account_row["defaulted"] is True
    assert account_row["stage_reason"] == "defaulted"


def test_run_ecl_engine_reports_configured_dpd_backstop() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 50,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))

    result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights={"base": 0.7, "upside": 0.3},
        policy=StagingPolicy(stage2_dpd_backstop=45, stage3_dpd_backstop=120),
    )

    assert result.account_ecl.loc[0, "stage"] == 2
    assert result.account_ecl.loc[0, "stage_reason"] == "45_dpd_backstop"


def test_run_ecl_engine_rejects_invalid_scenario_weight_values_and_names() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-001",
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "prior_stage": 1,
                "effective_interest_rate": 0.12,
                "gross_exposure": 100_000,
            }
        ]
    )
    term_structures = pd.DataFrame(_term_rows("SYN-ECL-001", 12, 0.001, 0.35, 100_000))

    with pytest.raises(ValueError, match="Scenario weight for base must be numeric"):
        run_ecl_engine(
            accounts,
            term_structures,
            scenario_weights={"base": "invalid", "upside": 0.3},
        )

    blank_scenario_terms = term_structures.assign(scenario=" ")
    with pytest.raises(ValueError, match="Scenario weights must use non-empty scenario names"):
        run_ecl_engine(
            accounts,
            blank_scenario_terms,
            scenario_weights={" ": 1.0},
        )


def test_sql_schema_and_example_queries_execute() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    schema = (project_dir / "sql" / "schema.sql").read_text(encoding="utf-8")
    queries = (project_dir / "sql" / "example_queries.sql").read_text(encoding="utf-8")

    with sqlite3.connect(":memory:") as connection:
        connection.executescript(schema)
        connection.executescript(queries)
