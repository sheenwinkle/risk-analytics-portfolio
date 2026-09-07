from __future__ import annotations

import pandas as pd
import pytest

from ifrs9_ecl_engine import (
    CashFlowSensitivityCase,
    analyse_cashflow_sensitivity,
    build_cashflow_ecl_terms,
)


def _accounts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-CF-001",
                "effective_interest_rate": 0.12,
                "gross_exposure": 1_200.0,
            }
        ]
    )


def _marginal_pd_curves() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-CF-001",
                "scenario": "base",
                "month": month,
                "marginal_pd": 0.01,
            }
            for month in range(1, 13)
        ]
    )


def _contractual_schedule() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-CF-001",
                "month": month,
                "contractual_principal_due": 100.0,
            }
            for month in range(1, 13)
        ]
    )


def _recovery_assumptions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "SYN-ECL-CF-001",
                "scenario": "base",
                "annual_prepayment_rate": 0.0,
                "cure_rate": 0.0,
                "cure_delay_months": 0,
                "collateral_value": 0.0,
                "collateral_haircut": 0.0,
                "recovery_cost_rate": 0.0,
                "collateral_recovery_delay_months": 0,
                "collateral_is_integral": False,
                "collateral_recognized_separately": False,
            }
        ]
    )


def test_build_cashflow_terms_rolls_contractual_principal_into_engine_ead() -> None:
    result = build_cashflow_ecl_terms(
        _accounts(),
        _marginal_pd_curves(),
        _contractual_schedule(),
        _recovery_assumptions(),
    )

    projection = result.monthly_projection
    assert projection["opening_balance"].tolist() == pytest.approx(
        list(range(1_200, 0, -100))
    )
    assert projection["closing_balance"].iloc[-1] == pytest.approx(0.0)
    assert projection["opening_balance"].tolist() == pytest.approx(
        (
            projection["scheduled_principal_applied"]
            + projection["expected_prepayment"]
            + projection["closing_balance"]
        ).tolist()
    )

    terms = result.term_structures
    assert terms["ead"].tolist() == pytest.approx(list(range(1_200, 0, -100)))
    assert terms["lgd"].tolist() == pytest.approx([1.0] * 12)
    assert terms["marginal_pd"].tolist() == pytest.approx([0.01] * 12)


def test_annual_cpr_is_converted_to_monthly_prepayment_before_balance_rollforward() -> None:
    assumptions = _recovery_assumptions().assign(annual_prepayment_rate=0.12)

    result = build_cashflow_ecl_terms(
        _accounts(),
        _marginal_pd_curves(),
        _contractual_schedule(),
        assumptions,
    )

    monthly_rate = 1.0 - (1.0 - 0.12) ** (1.0 / 12.0)
    expected_prepayment = (1_200.0 - 100.0) * monthly_rate
    first = result.monthly_projection.iloc[0]
    second = result.monthly_projection.iloc[1]
    assert first["monthly_prepayment_rate"] == pytest.approx(monthly_rate)
    assert first["expected_prepayment"] == pytest.approx(expected_prepayment)
    assert first["closing_balance"] == pytest.approx(
        1_200.0 - 100.0 - expected_prepayment
    )
    assert second["opening_balance"] == pytest.approx(first["closing_balance"])
    assert result.term_structures.iloc[1]["ead"] == pytest.approx(
        second["opening_balance"]
    )


def test_full_cure_after_delay_retains_the_time_value_cash_shortfall() -> None:
    assumptions = _recovery_assumptions().assign(
        cure_rate=1.0,
        cure_delay_months=12,
    )

    result = build_cashflow_ecl_terms(
        _accounts(),
        _marginal_pd_curves(),
        _contractual_schedule(),
        assumptions,
    )

    expected_lgd = 1.0 - 1.0 / 1.12
    assert result.term_structures["lgd"].tolist() == pytest.approx(
        [expected_lgd] * 12
    )
    projection = result.monthly_projection
    assert projection["expected_cure_recovery"].tolist() == pytest.approx(
        projection["ead"].tolist()
    )
    assert projection["discounted_expected_recovery_at_default"].tolist() == (
        pytest.approx((projection["ead"] / 1.12).tolist())
    )


def test_integral_collateral_is_capped_net_of_haircut_cost_and_delay() -> None:
    assumptions = _recovery_assumptions().assign(
        cure_rate=0.25,
        collateral_value=1_000.0,
        collateral_haircut=0.20,
        recovery_cost_rate=0.10,
        collateral_recovery_delay_months=12,
        collateral_is_integral=True,
    )

    result = build_cashflow_ecl_terms(
        _accounts(),
        _marginal_pd_curves(),
        _contractual_schedule(),
        assumptions,
    )

    first = result.monthly_projection.iloc[0]
    assert first["net_collateral_value"] == pytest.approx(720.0)
    assert first["expected_cure_recovery"] == pytest.approx(300.0)
    assert first["expected_collateral_recovery"] == pytest.approx(540.0)
    expected_discounted_recovery = 300.0 + 540.0 / 1.12
    assert first["discounted_expected_recovery_at_default"] == pytest.approx(
        expected_discounted_recovery
    )
    assert first["lgd"] == pytest.approx(
        1.0 - expected_discounted_recovery / 1_200.0
    )

    last = result.monthly_projection.iloc[-1]
    assert last["expected_collateral_recovery"] <= last["ead"] * 0.75
    assert 0.0 <= last["lgd"] <= 1.0


@pytest.mark.parametrize(
    ("integral", "recognized_separately", "expected_reason"),
    [
        (False, False, "excluded_not_integral"),
        (True, True, "excluded_separately_recognized"),
    ],
)
def test_ineligible_collateral_is_excluded_with_auditable_reason(
    integral: bool,
    recognized_separately: bool,
    expected_reason: str,
) -> None:
    assumptions = _recovery_assumptions().assign(
        collateral_value=5_000.0,
        collateral_is_integral=integral,
        collateral_recognized_separately=recognized_separately,
    )

    result = build_cashflow_ecl_terms(
        _accounts(),
        _marginal_pd_curves(),
        _contractual_schedule(),
        assumptions,
    )

    projection = result.monthly_projection
    assert not projection["collateral_eligible"].any()
    assert set(projection["collateral_eligibility_reason"]) == {expected_reason}
    assert not projection["expected_collateral_recovery"].any()
    assert set(result.term_structures["lgd"]) == {1.0}


def test_contractual_schedule_must_fully_amortise_reporting_exposure() -> None:
    incomplete_schedule = _contractual_schedule().assign(
        contractual_principal_due=90.0
    )

    with pytest.raises(
        ValueError,
        match="contractual principal must fully amortise gross exposure",
    ):
        build_cashflow_ecl_terms(
            _accounts(),
            _marginal_pd_curves(),
            incomplete_schedule,
            _recovery_assumptions(),
        )


def test_contractual_schedule_and_pd_curve_require_the_same_contiguous_horizon() -> None:
    schedule = _contractual_schedule()
    schedule.loc[schedule["month"] == 11, "contractual_principal_due"] = 200.0
    schedule = schedule[schedule["month"] != 12]

    with pytest.raises(
        ValueError,
        match="contractual schedule and marginal PD curves must share a contiguous horizon",
    ):
        build_cashflow_ecl_terms(
            _accounts(),
            _marginal_pd_curves(),
            schedule,
            _recovery_assumptions(),
        )


def test_lower_prepayment_case_flows_through_to_higher_engine_ecl() -> None:
    accounts = _accounts().assign(
        days_past_due=45,
        sicr=False,
        credit_impaired=False,
        defaulted=False,
        prior_stage=1,
    )
    assumptions = _recovery_assumptions().assign(annual_prepayment_rate=0.12)
    cases = (
        CashFlowSensitivityCase(case_id="baseline", is_baseline=True),
        CashFlowSensitivityCase(
            case_id="low_prepayment",
            annual_prepayment_rate_multiplier=0.0,
        ),
    )

    result = analyse_cashflow_sensitivity(
        accounts,
        _marginal_pd_curves(),
        _contractual_schedule(),
        assumptions,
        {"base": 1.0},
        cases,
    )

    summary = result.portfolio_summary.set_index("case_id")
    assert summary.loc["baseline", "ecl_change"] == pytest.approx(0.0)
    assert summary.loc["low_prepayment", "modelled_ecl"] > summary.loc[
        "baseline", "modelled_ecl"
    ]
    low_prepayment_accounts = result.account_summary[
        result.account_summary["case_id"] == "low_prepayment"
    ]
    assert summary.loc["low_prepayment", "ecl_change"] == pytest.approx(
        low_prepayment_accounts["ecl_change"].sum()
    )


def test_recovery_and_combined_downside_cases_increase_ecl() -> None:
    accounts = _accounts().assign(
        days_past_due=45,
        sicr=False,
        credit_impaired=False,
        defaulted=False,
        prior_stage=1,
    )
    assumptions = _recovery_assumptions().assign(
        annual_prepayment_rate=0.12,
        cure_rate=0.40,
        cure_delay_months=3,
        collateral_value=600.0,
        collateral_haircut=0.10,
        recovery_cost_rate=0.05,
        collateral_recovery_delay_months=9,
        collateral_is_integral=True,
    )
    cases = (
        CashFlowSensitivityCase(case_id="baseline", is_baseline=True),
        CashFlowSensitivityCase(case_id="low_cure", cure_rate_multiplier=0.50),
        CashFlowSensitivityCase(
            case_id="collateral_downturn",
            collateral_value_multiplier=0.75,
            collateral_haircut_addon=0.10,
        ),
        CashFlowSensitivityCase(
            case_id="delayed_recovery",
            cure_delay_addon_months=6,
            collateral_recovery_delay_addon_months=6,
        ),
        CashFlowSensitivityCase(
            case_id="combined_downside",
            annual_prepayment_rate_multiplier=0.50,
            cure_rate_multiplier=0.50,
            collateral_value_multiplier=0.75,
            collateral_haircut_addon=0.10,
            cure_delay_addon_months=6,
            collateral_recovery_delay_addon_months=6,
        ),
    )

    result = analyse_cashflow_sensitivity(
        accounts,
        _marginal_pd_curves(),
        _contractual_schedule(),
        assumptions,
        {"base": 1.0},
        cases,
    )

    summary = result.portfolio_summary.set_index("case_id")
    baseline_ecl = summary.loc["baseline", "modelled_ecl"]
    for case_id in ["low_cure", "collateral_downturn", "delayed_recovery"]:
        assert summary.loc[case_id, "modelled_ecl"] > baseline_ecl
    assert summary.loc["combined_downside", "modelled_ecl"] > summary.loc[
        ["low_cure", "collateral_downturn", "delayed_recovery"],
        "modelled_ecl",
    ].max()


@pytest.mark.parametrize(
    ("cases", "expected_message"),
    [
        (
            (
                CashFlowSensitivityCase(case_id="same", is_baseline=True),
                CashFlowSensitivityCase(case_id="same"),
            ),
            "case IDs must be unique",
        ),
        (
            (
                CashFlowSensitivityCase(
                    case_id="baseline",
                    is_baseline=True,
                    cure_rate_multiplier=0.90,
                ),
                CashFlowSensitivityCase(case_id="stress"),
            ),
            "baseline case must use neutral adjustments",
        ),
        (
            (
                CashFlowSensitivityCase(case_id="baseline", is_baseline=True),
                CashFlowSensitivityCase(
                    case_id="stress",
                    collateral_value_multiplier=-0.10,
                ),
            ),
            "case adjustments must be finite and nonnegative",
        ),
        (
            (CashFlowSensitivityCase(case_id="baseline", is_baseline=0),),
            "is_baseline must be boolean",
        ),
    ],
)
def test_cashflow_sensitivity_cases_are_governed(
    cases: tuple[CashFlowSensitivityCase, ...],
    expected_message: str,
) -> None:
    accounts = _accounts().assign(
        days_past_due=45,
        sicr=False,
        credit_impaired=False,
        defaulted=False,
        prior_stage=1,
    )

    with pytest.raises((TypeError, ValueError), match=expected_message):
        analyse_cashflow_sensitivity(
            accounts,
            _marginal_pd_curves(),
            _contractual_schedule(),
            _recovery_assumptions(),
            {"base": 1.0},
            cases,
        )


@pytest.mark.parametrize(
    ("column", "invalid_value", "expected_message"),
    [
        ("annual_prepayment_rate", 1.01, "recovery rates must be between 0 and 1"),
        ("cure_rate", -0.01, "recovery rates must be between 0 and 1"),
        ("collateral_haircut", 1.01, "recovery rates must be between 0 and 1"),
        ("recovery_cost_rate", -0.01, "recovery rates must be between 0 and 1"),
        ("collateral_value", -1.0, "collateral_value must be nonnegative"),
        ("cure_delay_months", 1.5, "recovery delays must be nonnegative integers"),
        (
            "collateral_recovery_delay_months",
            True,
            "recovery delays must be nonnegative integers",
        ),
        (
            "collateral_is_integral",
            "yes",
            "collateral eligibility flags must be boolean",
        ),
        (
            "annual_prepayment_rate",
            None,
            "recovery assumptions must contain finite numeric values",
        ),
    ],
)
def test_recovery_assumptions_reject_invalid_financial_values(
    column: str,
    invalid_value: object,
    expected_message: str,
) -> None:
    assumptions = _recovery_assumptions().copy()
    assumptions[column] = invalid_value

    with pytest.raises((TypeError, ValueError), match=expected_message):
        build_cashflow_ecl_terms(
            _accounts(),
            _marginal_pd_curves(),
            _contractual_schedule(),
            assumptions,
        )


@pytest.mark.parametrize(
    ("assumption_updates", "case_updates"),
    [
        (
            {"annual_prepayment_rate": 0.60},
            {"annual_prepayment_rate_multiplier": 2.0},
        ),
        ({"cure_rate": 0.60}, {"cure_rate_multiplier": 2.0}),
        ({"collateral_haircut": 0.60}, {"collateral_haircut_addon": 0.50}),
    ],
)
def test_sensitivity_case_cannot_push_adjusted_rates_outside_unit_interval(
    assumption_updates: dict[str, float],
    case_updates: dict[str, float],
) -> None:
    assumptions = _recovery_assumptions().assign(**assumption_updates)
    case = CashFlowSensitivityCase(case_id="invalid_adjustment", **case_updates)

    with pytest.raises(
        ValueError,
        match="adjusted prepayment, cure, and haircut rates must be between 0 and 1",
    ):
        build_cashflow_ecl_terms(
            _accounts(),
            _marginal_pd_curves(),
            _contractual_schedule(),
            assumptions,
            case=case,
        )


@pytest.mark.parametrize("scope_issue", ["missing_pair", "duplicate_pair"])
def test_recovery_assumptions_must_match_pd_curve_scope_one_to_one(
    scope_issue: str,
) -> None:
    curves = pd.concat(
        [
            _marginal_pd_curves(),
            _marginal_pd_curves().assign(scenario="downside"),
        ],
        ignore_index=True,
    )
    assumptions = pd.concat(
        [
            _recovery_assumptions(),
            _recovery_assumptions().assign(scenario="downside"),
        ],
        ignore_index=True,
    )
    if scope_issue == "missing_pair":
        assumptions = assumptions[assumptions["scenario"] != "downside"]
    else:
        assumptions = pd.concat([assumptions, assumptions.iloc[[0]]], ignore_index=True)

    with pytest.raises(
        ValueError,
        match="recovery assumptions must cover each account/scenario exactly once",
    ):
        build_cashflow_ecl_terms(
            _accounts(),
            curves,
            _contractual_schedule(),
            assumptions,
        )


@pytest.mark.parametrize(
    ("input_name", "missing_column"),
    [
        ("accounts", "effective_interest_rate"),
        ("marginal_pd_curves", "marginal_pd"),
        ("contractual_schedule", "contractual_principal_due"),
        ("recovery_assumptions", "cure_rate"),
    ],
)
def test_cashflow_inputs_report_missing_required_columns(
    input_name: str,
    missing_column: str,
) -> None:
    inputs = {
        "accounts": _accounts(),
        "marginal_pd_curves": _marginal_pd_curves(),
        "contractual_schedule": _contractual_schedule(),
        "recovery_assumptions": _recovery_assumptions(),
    }
    inputs[input_name] = inputs[input_name].drop(columns=missing_column)

    with pytest.raises(ValueError, match=f"{input_name} missing required columns"):
        build_cashflow_ecl_terms(
            inputs["accounts"],
            inputs["marginal_pd_curves"],
            inputs["contractual_schedule"],
            inputs["recovery_assumptions"],
        )


@pytest.mark.parametrize(
    ("data_issue", "expected_message"),
    [
        ("duplicate_account", "accounts.account_id must be unique"),
        ("blank_scenario", "scenario must contain non-empty values"),
        ("invalid_eir", "effective_interest_rate must be greater than -1"),
        ("negative_exposure", "gross_exposure must be nonnegative"),
        ("invalid_pd", "marginal_pd must be between 0 and 1"),
        ("negative_principal", "contractual_principal_due must be nonnegative"),
        ("duplicate_curve_month", "one row per account/scenario/month"),
        ("duplicate_schedule_month", "one row per account/month"),
    ],
)
def test_cashflow_inputs_reject_invalid_keys_and_amounts(
    data_issue: str,
    expected_message: str,
) -> None:
    accounts = _accounts()
    curves = _marginal_pd_curves()
    schedule = _contractual_schedule()
    assumptions = _recovery_assumptions()
    if data_issue == "duplicate_account":
        accounts = pd.concat([accounts, accounts], ignore_index=True)
    elif data_issue == "blank_scenario":
        curves = curves.assign(scenario=" ")
        assumptions = assumptions.assign(scenario=" ")
    elif data_issue == "invalid_eir":
        accounts = accounts.assign(effective_interest_rate=-1.0)
    elif data_issue == "negative_exposure":
        accounts = accounts.assign(gross_exposure=-1_200.0)
        schedule = schedule.assign(contractual_principal_due=-100.0)
    elif data_issue == "invalid_pd":
        curves.loc[curves["month"] == 1, "marginal_pd"] = 1.01
    elif data_issue == "negative_principal":
        schedule.loc[schedule["month"] == 1, "contractual_principal_due"] = -100.0
        schedule.loc[schedule["month"] == 2, "contractual_principal_due"] = 300.0
    elif data_issue == "duplicate_curve_month":
        curves = pd.concat([curves, curves.iloc[[0]]], ignore_index=True)
    elif data_issue == "duplicate_schedule_month":
        schedule = pd.concat([schedule, schedule.iloc[[0]]], ignore_index=True)

    with pytest.raises((TypeError, ValueError), match=expected_message):
        build_cashflow_ecl_terms(accounts, curves, schedule, assumptions)
