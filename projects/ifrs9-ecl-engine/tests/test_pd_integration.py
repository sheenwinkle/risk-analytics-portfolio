from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from ifrs9_ecl_engine import (
    PDIntegrationConfig,
    PDScenarioAssumption,
    build_ecl_inputs_from_pd_snapshot,
    read_pd_predictions,
    select_evenly_spaced_pd_sample,
    select_pd_reporting_cohort,
)


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "customer_id": "C001",
                "observation_date": "2022-06-01",
                "actual_default": 1,
                "recalibrated_pd": 0.120000,
            },
            {
                "customer_id": "C002",
                "observation_date": "2022-06-01",
                "actual_default": 0,
                "recalibrated_pd": 0.060000,
            },
            {
                "customer_id": "C003",
                "observation_date": "2022-05-01",
                "actual_default": 1,
                "recalibrated_pd": 0.090000,
            },
        ]
    )


def _assumptions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "customer_id": "C001",
                "account_id": "SYN-PD-ECL-001",
                "gross_exposure": 100_000,
                "lgd": 0.40,
                "remaining_maturity_months": 24,
                "effective_interest_rate": 0.10,
                "days_past_due": 0,
                "sicr": False,
                "credit_impaired": False,
                "defaulted": False,
                "prior_stage": 1,
            },
            {
                "customer_id": "C002",
                "account_id": "SYN-PD-ECL-002",
                "gross_exposure": 80_000,
                "lgd": 0.35,
                "remaining_maturity_months": 18,
                "effective_interest_rate": 0.08,
                "days_past_due": 45,
                "sicr": False,
                "credit_impaired": False,
                "defaulted": False,
                "prior_stage": 1,
            },
        ]
    )


def test_bridge_builds_ecl_inputs_from_selected_recalibrated_pd_snapshot() -> None:
    predictions = _predictions()
    predictions_with_flipped_outcomes = predictions.assign(
        actual_default=1 - predictions["actual_default"]
    )
    assumptions = _assumptions()
    config = PDIntegrationConfig(
        scenarios=(
            PDScenarioAssumption("upside", 0.2, 0.75, -0.03),
            PDScenarioAssumption("base", 0.5, 1.0, 0.0),
            PDScenarioAssumption("downside", 0.3, 1.5, 0.05),
        )
    )

    selected = select_pd_reporting_cohort(predictions, reporting_date="2022-06-01")
    selected_again = select_pd_reporting_cohort(
        predictions_with_flipped_outcomes,
        reporting_date="2022-06-01",
    )

    bridge = build_ecl_inputs_from_pd_snapshot(selected, assumptions, config=config)
    bridge_again = build_ecl_inputs_from_pd_snapshot(selected_again, assumptions, config=config)

    pd.testing.assert_frame_equal(bridge.accounts, bridge_again.accounts)
    pd.testing.assert_frame_equal(bridge.term_structures, bridge_again.term_structures)
    assert "actual_default" not in bridge.input_audit.columns

    account_rows = bridge.accounts.set_index("account_id")
    assert account_rows.loc["SYN-PD-ECL-001", "gross_exposure"] == 100_000
    assert account_rows.loc["SYN-PD-ECL-002", "days_past_due"] == 45

    terms = bridge.term_structures.set_index(["account_id", "scenario", "month"])
    annual_hazard = -math.log(1 - 0.12)
    monthly_q = 1 - math.exp(-annual_hazard / 12)
    assert terms.loc[("SYN-PD-ECL-001", "base", 1), "marginal_pd"] == pytest.approx(
        monthly_q
    )
    assert terms.loc[("SYN-PD-ECL-001", "base", 2), "marginal_pd"] == pytest.approx(
        (1 - monthly_q) * monthly_q
    )
    first_year_pd = terms.loc[
        ("SYN-PD-ECL-001", "base", slice(1, 12)),
        "marginal_pd",
    ].sum()
    assert first_year_pd == pytest.approx(0.12)
    assert terms.loc[("SYN-PD-ECL-001", "base", 1), "ead"] == 100_000
    assert terms.loc[("SYN-PD-ECL-001", "base", 24), "ead"] == pytest.approx(
        100_000 / 24
    )

    cumulative_pd = bridge.term_structures.groupby(["account_id", "scenario"])[
        "marginal_pd"
    ].sum()
    assert (cumulative_pd <= 1).all()
    account_one = cumulative_pd.loc["SYN-PD-ECL-001"]
    assert account_one["upside"] < account_one["base"] < account_one["downside"]


def test_bridge_validates_inputs_and_does_not_mutate_callers() -> None:
    predictions = _predictions()
    assumptions = _assumptions()
    predictions_before = predictions.copy(deep=True)
    assumptions_before = assumptions.copy(deep=True)

    with pytest.raises(ValueError, match="Reporting date 2022-12-01 is absent"):
        select_pd_reporting_cohort(predictions, reporting_date="2022-12-01")

    selected = select_pd_reporting_cohort(predictions, reporting_date="2022-06-01")
    with pytest.raises(ValueError, match="missing customer_id records.*C002"):
        build_ecl_inputs_from_pd_snapshot(selected, assumptions.iloc[[0]])

    extra_assumption = pd.concat(
        [
            assumptions,
            assumptions.iloc[[0]].assign(customer_id="C999", account_id="SYN-PD-ECL-999"),
        ],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="records absent from PD snapshot.*C999"):
        build_ecl_inputs_from_pd_snapshot(selected, extra_assumption)

    with pytest.raises(ValueError, match="account_assumptions.account_id must be unique"):
        build_ecl_inputs_from_pd_snapshot(
            selected,
            assumptions.assign(account_id="SYN-PD-ECL-001"),
        )

    with pytest.raises(ValueError, match="recalibrated_pd.*less than 1"):
        build_ecl_inputs_from_pd_snapshot(selected.assign(recalibrated_pd=1.0), assumptions)

    with pytest.raises(ValueError, match="remaining_maturity_months must be a positive integer"):
        build_ecl_inputs_from_pd_snapshot(
            selected,
            assumptions.assign(remaining_maturity_months=0),
        )

    with pytest.raises(ValueError, match="Scenario hazard multipliers must satisfy"):
        PDIntegrationConfig(
            scenarios=(
                PDScenarioAssumption("upside", 0.2, 1.2, -0.03),
                PDScenarioAssumption("base", 0.5, 1.0, 0.0),
                PDScenarioAssumption("downside", 0.3, 1.5, 0.05),
            )
        )

    with pytest.raises(ValueError, match="Scenario LGD add-on for downside produces LGD"):
        build_ecl_inputs_from_pd_snapshot(
            selected,
            assumptions,
            config=PDIntegrationConfig(
                scenarios=(
                    PDScenarioAssumption("base", 0.6, 1.0, 0.0),
                    PDScenarioAssumption("downside", 0.4, 1.5, 0.7),
                )
            ),
        )

    pd.testing.assert_frame_equal(predictions, predictions_before)
    pd.testing.assert_frame_equal(assumptions, assumptions_before)


def test_reporting_cohort_rejects_empty_predictions_with_actionable_error() -> None:
    empty_predictions = pd.DataFrame(
        columns=["customer_id", "observation_date", "recalibrated_pd"]
    )

    with pytest.raises(ValueError, match="predictions must contain at least one row"):
        select_pd_reporting_cohort(empty_predictions)


def test_read_pd_predictions_rejects_a_directory_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found or is not a file"):
        read_pd_predictions(tmp_path)


@pytest.mark.parametrize("reporting_date", ["", []])
def test_reporting_cohort_rejects_invalid_reporting_date(reporting_date: object) -> None:
    with pytest.raises(ValueError, match="reporting_date must be a valid date"):
        select_pd_reporting_cohort(
            _predictions(),
            reporting_date=reporting_date,  # type: ignore[arg-type]
        )


def test_bridge_rejects_empty_pd_snapshot_with_actionable_error() -> None:
    empty_snapshot = pd.DataFrame(
        columns=["customer_id", "observation_date", "recalibrated_pd"]
    )

    with pytest.raises(ValueError, match="pd_snapshot must contain at least one row"):
        build_ecl_inputs_from_pd_snapshot(empty_snapshot, _assumptions())


def test_bridge_rejects_empty_account_assumptions_with_actionable_error() -> None:
    snapshot = select_pd_reporting_cohort(_predictions(), reporting_date="2022-06-01")
    empty_assumptions = _assumptions().iloc[0:0]

    with pytest.raises(
        ValueError,
        match="account_assumptions must contain at least one row",
    ):
        build_ecl_inputs_from_pd_snapshot(snapshot, empty_assumptions)


def test_pd_integration_config_rejects_invalid_scenario_objects() -> None:
    with pytest.raises(
        TypeError,
        match="scenarios must contain only PDScenarioAssumption values",
    ):
        PDIntegrationConfig(scenarios=("base",))  # type: ignore[arg-type]


def test_pd_scenario_normalizes_numeric_inputs() -> None:
    scenario = PDScenarioAssumption(
        "base",
        "1.0",  # type: ignore[arg-type]
        "1.0",  # type: ignore[arg-type]
        "0.0",  # type: ignore[arg-type]
    )

    assert scenario.weight == 1.0
    assert scenario.hazard_multiplier == 1.0
    assert scenario.lgd_addon == 0.0
    assert all(
        isinstance(value, float)
        for value in (scenario.weight, scenario.hazard_multiplier, scenario.lgd_addon)
    )


def test_evenly_spaced_sample_is_unique_and_order_independent() -> None:
    cohort = pd.DataFrame(
        [
            {
                "customer_id": f"C{i:03d}",
                "observation_date": "2022-07-01",
                "recalibrated_pd": pd_value,
            }
            for i, pd_value in enumerate([0.01, 0.03, 0.05, 0.08, 0.13, 0.21], start=1)
        ]
    )
    shuffled = cohort.sample(frac=1, random_state=7).reset_index(drop=True)

    for sample_size in range(1, len(cohort) + 1):
        selected = select_evenly_spaced_pd_sample(cohort, sample_size)
        selected_again = select_evenly_spaced_pd_sample(shuffled, sample_size)

        pd.testing.assert_frame_equal(selected, selected_again)
        assert selected["customer_id"].is_unique


def test_pd_integration_cli_writes_reproducible_reports_without_term_structure(
    tmp_path: Path,
) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    prediction_path = tmp_path / "oot_predictions.csv"
    pd.DataFrame(
        [
            {
                "customer_id": f"C{i:03d}",
                "observation_date": "2022-07-01",
                "actual_default": i % 2,
                "recalibrated_pd": pd_value,
            }
            for i, pd_value in enumerate([0.02, 0.04, 0.08, 0.12, 0.18], start=1)
        ]
        + [
            {
                "customer_id": "C999",
                "observation_date": "2022-06-01",
                "actual_default": 1,
                "recalibrated_pd": 0.50,
            }
        ]
    ).to_csv(prediction_path, index=False)

    expected_files = [
        "account_ecl.csv",
        "input_audit.csv",
        "pd_integration_report.md",
        "portfolio_summary.csv",
        "scenario_ecl.csv",
        "stage_migration.csv",
    ]
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    for output_dir in [first_output, second_output]:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_pd_integration.py"),
                "--prediction-path",
                str(prediction_path),
                "--sample-size",
                "3",
                "--output-dir",
                str(output_dir),
            ],
            cwd=project_dir,
            check=True,
        )
        assert sorted(path.name for path in output_dir.iterdir()) == expected_files

    for report_name in expected_files:
        first_bytes = (first_output / report_name).read_bytes()
        second_bytes = (second_output / report_name).read_bytes()
        assert first_bytes == second_bytes
        assert b"\r\n" not in first_bytes

    input_audit = pd.read_csv(first_output / "input_audit.csv")
    assert input_audit["account_id"].tolist() == [
        "SYN-PD-ECL-001",
        "SYN-PD-ECL-002",
        "SYN-PD-ECL-003",
    ]
    assert input_audit["customer_id"].tolist() == ["C001", "C003", "C005"]
    assert "actual_default" not in input_audit.columns
    assert input_audit["observation_date"].eq("2022-07-01").all()

    account_ecl = pd.read_csv(first_output / "account_ecl.csv")
    assert account_ecl["account_id"].str.startswith("SYN-PD-ECL-").all()
    scenario_ecl = pd.read_csv(first_output / "scenario_ecl.csv")
    assert {"hazard_multiplier", "lgd_addon"}.issubset(scenario_ecl.columns)
    base_scenario = scenario_ecl[scenario_ecl["scenario"] == "base"]
    assert base_scenario["hazard_multiplier"].eq(1.0).all()
    assert base_scenario["lgd_addon"].eq(0.0).all()
    assert (first_output / "pd_integration_report.md").read_text(encoding="utf-8").find(
        "terminal-outcome proxy"
    ) >= 0
