from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from ifrs9_ecl_engine.engine import ECLResult, run_ecl_engine

ACCOUNT_REQUIRED_COLUMNS = {
    "account_id",
    "effective_interest_rate",
    "gross_exposure",
}
MARGINAL_PD_REQUIRED_COLUMNS = {
    "account_id",
    "scenario",
    "month",
    "marginal_pd",
}
CONTRACTUAL_REQUIRED_COLUMNS = {
    "account_id",
    "month",
    "contractual_principal_due",
}
RECOVERY_REQUIRED_COLUMNS = {
    "account_id",
    "scenario",
    "annual_prepayment_rate",
    "cure_rate",
    "cure_delay_months",
    "collateral_value",
    "collateral_haircut",
    "recovery_cost_rate",
    "collateral_recovery_delay_months",
    "collateral_is_integral",
    "collateral_recognized_separately",
}


@dataclass(frozen=True)
class CashFlowSensitivityCase:
    case_id: str
    description: str = ""
    is_baseline: bool = False
    annual_prepayment_rate_multiplier: float = 1.0
    cure_rate_multiplier: float = 1.0
    collateral_value_multiplier: float = 1.0
    collateral_haircut_addon: float = 0.0
    cure_delay_addon_months: int = 0
    collateral_recovery_delay_addon_months: int = 0


@dataclass(frozen=True)
class CashFlowProjectionResult:
    term_structures: pd.DataFrame
    monthly_projection: pd.DataFrame


@dataclass(frozen=True)
class CashFlowSensitivityResult:
    portfolio_summary: pd.DataFrame
    account_summary: pd.DataFrame
    monthly_projection: pd.DataFrame
    case_results: dict[str, ECLResult]


def build_cashflow_ecl_terms(
    accounts: pd.DataFrame,
    marginal_pd_curves: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
    recovery_assumptions: pd.DataFrame,
    *,
    case: CashFlowSensitivityCase | None = None,
) -> CashFlowProjectionResult:
    active_case = case or CashFlowSensitivityCase(case_id="projection")
    _validate_required_columns(accounts, ACCOUNT_REQUIRED_COLUMNS, "accounts")
    _validate_required_columns(
        marginal_pd_curves,
        MARGINAL_PD_REQUIRED_COLUMNS,
        "marginal_pd_curves",
    )
    _validate_required_columns(
        contractual_schedule,
        CONTRACTUAL_REQUIRED_COLUMNS,
        "contractual_schedule",
    )
    _validate_required_columns(
        recovery_assumptions,
        RECOVERY_REQUIRED_COLUMNS,
        "recovery_assumptions",
    )
    _validate_case_adjustments(active_case)
    _validate_cashflow_input_values(
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
    )
    (
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
    ) = _normalise_cashflow_inputs(
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
    )
    _validate_recovery_financial_values(recovery_assumptions)
    _validate_recovery_scope(marginal_pd_curves, recovery_assumptions)
    _validate_matching_horizons(accounts, marginal_pd_curves, contractual_schedule)
    _validate_contractual_totals(accounts, contractual_schedule)
    account_lookup = accounts.set_index("account_id")
    recovery_lookup = recovery_assumptions.set_index(["account_id", "scenario"])
    schedule_lookup = {
        account_id: group.sort_values("month")
        for account_id, group in contractual_schedule.groupby("account_id")
    }
    rows: list[dict[str, object]] = []
    for (account_id, scenario), curve in marginal_pd_curves.groupby(
        ["account_id", "scenario"],
        sort=True,
    ):
        account = account_lookup.loc[account_id]
        assumptions = recovery_lookup.loc[(account_id, scenario)]
        schedule = schedule_lookup[account_id].set_index("month")
        opening_balance = float(account["gross_exposure"])
        effective_interest_rate = float(account["effective_interest_rate"])
        annual_prepayment_rate = (
            float(assumptions["annual_prepayment_rate"])
            * active_case.annual_prepayment_rate_multiplier
        )
        cure_rate = (
            float(assumptions["cure_rate"])
            * active_case.cure_rate_multiplier
        )
        collateral_value = (
            float(assumptions["collateral_value"])
            * active_case.collateral_value_multiplier
        )
        collateral_haircut = (
            float(assumptions["collateral_haircut"])
            + active_case.collateral_haircut_addon
        )
        _validate_adjusted_recovery_rates(
            annual_prepayment_rate,
            cure_rate,
            collateral_haircut,
        )
        monthly_prepayment_rate = _monthly_rate(annual_prepayment_rate)
        recovery_cost_rate = float(assumptions["recovery_cost_rate"])
        collateral_is_integral = bool(assumptions["collateral_is_integral"])
        collateral_recognized_separately = bool(
            assumptions["collateral_recognized_separately"]
        )
        collateral_eligible = (
            collateral_value > 0
            and collateral_is_integral
            and not collateral_recognized_separately
        )
        collateral_eligibility_reason = _collateral_eligibility_reason(
            collateral_value,
            collateral_is_integral,
            collateral_recognized_separately,
        )
        net_collateral_value = (
            collateral_value
            * (1.0 - collateral_haircut)
            * (1.0 - recovery_cost_rate)
            if collateral_eligible
            else 0.0
        )
        cure_delay_months = (
            int(assumptions["cure_delay_months"])
            + active_case.cure_delay_addon_months
        )
        collateral_recovery_delay_months = (
            int(assumptions["collateral_recovery_delay_months"])
            + active_case.collateral_recovery_delay_addon_months
        )
        for term in curve.sort_values("month").to_dict("records"):
            month = int(term["month"])
            contractual_principal_due = float(
                schedule.loc[month, "contractual_principal_due"]
            )
            scheduled_principal_applied = min(
                opening_balance,
                contractual_principal_due,
            )
            remaining_after_schedule = opening_balance - scheduled_principal_applied
            expected_prepayment = remaining_after_schedule * monthly_prepayment_rate
            closing_balance = max(
                0.0,
                remaining_after_schedule - expected_prepayment,
            )
            expected_cure_recovery = cure_rate * opening_balance
            discounted_cure_recovery = expected_cure_recovery / (
                (1.0 + effective_interest_rate) ** (cure_delay_months / 12.0)
            )
            expected_collateral_recovery = (1.0 - cure_rate) * min(
                opening_balance,
                net_collateral_value,
            )
            discounted_collateral_recovery = expected_collateral_recovery / (
                (1.0 + effective_interest_rate)
                ** (collateral_recovery_delay_months / 12.0)
            )
            discounted_expected_recovery = (
                discounted_cure_recovery + discounted_collateral_recovery
            )
            effective_lgd = (
                max(0.0, min(1.0, 1.0 - discounted_expected_recovery / opening_balance))
                if opening_balance
                else 0.0
            )
            rows.append(
                {
                    "case_id": active_case.case_id,
                    "account_id": account_id,
                    "scenario": scenario,
                    "month": month,
                    "marginal_pd": float(term["marginal_pd"]),
                    "annual_prepayment_rate": annual_prepayment_rate,
                    "monthly_prepayment_rate": monthly_prepayment_rate,
                    "opening_balance": opening_balance,
                    "contractual_principal_due": contractual_principal_due,
                    "scheduled_principal_applied": scheduled_principal_applied,
                    "expected_prepayment": expected_prepayment,
                    "closing_balance": closing_balance,
                    "ead": opening_balance,
                    "cure_rate": cure_rate,
                    "cure_delay_months": cure_delay_months,
                    "expected_cure_recovery": expected_cure_recovery,
                    "collateral_value": collateral_value,
                    "collateral_haircut": collateral_haircut,
                    "recovery_cost_rate": recovery_cost_rate,
                    "collateral_is_integral": collateral_is_integral,
                    "collateral_recognized_separately": (
                        collateral_recognized_separately
                    ),
                    "collateral_eligible": collateral_eligible,
                    "collateral_eligibility_reason": (
                        collateral_eligibility_reason
                    ),
                    "net_collateral_value": net_collateral_value,
                    "collateral_recovery_delay_months": (
                        collateral_recovery_delay_months
                    ),
                    "expected_collateral_recovery": expected_collateral_recovery,
                    "discounted_expected_recovery_at_default": (
                        discounted_expected_recovery
                    ),
                    "lgd": effective_lgd,
                }
            )
            opening_balance = closing_balance

    monthly_projection = pd.DataFrame(rows).sort_values(
        ["account_id", "scenario", "month"]
    ).reset_index(drop=True)
    return CashFlowProjectionResult(
        term_structures=monthly_projection[
            ["account_id", "scenario", "month", "marginal_pd", "lgd", "ead"]
        ].copy(),
        monthly_projection=monthly_projection,
    )


def analyse_cashflow_sensitivity(
    accounts: pd.DataFrame,
    marginal_pd_curves: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
    recovery_assumptions: pd.DataFrame,
    scenario_weights: dict[str, float],
    cases: tuple[CashFlowSensitivityCase, ...],
) -> CashFlowSensitivityResult:
    _validate_cases(cases)
    baseline_cases = [case for case in cases if case.is_baseline]

    case_results: dict[str, ECLResult] = {}
    projections = []
    account_rows = []
    portfolio_rows = []
    for case in cases:
        case_description = case.description.strip() or case.case_id
        projection = build_cashflow_ecl_terms(
            accounts,
            marginal_pd_curves,
            contractual_schedule,
            recovery_assumptions,
            case=case,
        )
        ecl_result = run_ecl_engine(
            accounts,
            projection.term_structures,
            scenario_weights,
        )
        case_results[case.case_id] = ecl_result
        projections.append(projection.monthly_projection)
        case_accounts = ecl_result.account_ecl[
            ["account_id", "stage", "stage_reason", "gross_exposure", "weighted_ecl"]
        ].copy()
        case_accounts.insert(0, "case_id", case.case_id)
        case_accounts.insert(1, "case_description", case_description)
        account_rows.append(case_accounts)
        total = ecl_result.portfolio_summary[
            ecl_result.portfolio_summary["stage"].astype(str) == "Total"
        ].iloc[0]
        portfolio_rows.append(
            {
                "case_id": case.case_id,
                "case_description": case_description,
                "is_baseline": case.is_baseline,
                "annual_prepayment_rate_multiplier": (
                    case.annual_prepayment_rate_multiplier
                ),
                "cure_rate_multiplier": case.cure_rate_multiplier,
                "collateral_value_multiplier": case.collateral_value_multiplier,
                "collateral_haircut_addon": case.collateral_haircut_addon,
                "cure_delay_addon_months": case.cure_delay_addon_months,
                "collateral_recovery_delay_addon_months": (
                    case.collateral_recovery_delay_addon_months
                ),
                "gross_exposure": float(total["gross_exposure"]),
                "modelled_ecl": float(total["weighted_ecl"]),
                "coverage_ratio": float(total["coverage_ratio"]),
            }
        )

    account_summary = pd.concat(account_rows, ignore_index=True)
    baseline_id = baseline_cases[0].case_id
    baseline_account_ecl = (
        account_summary[account_summary["case_id"] == baseline_id]
        .set_index("account_id")["weighted_ecl"]
        .rename("baseline_ecl")
    )
    account_summary = account_summary.join(baseline_account_ecl, on="account_id")
    account_summary["ecl_change"] = (
        account_summary["weighted_ecl"] - account_summary["baseline_ecl"]
    )
    account_summary["ecl_change_pct"] = account_summary.apply(
        lambda row: (
            float(row["ecl_change"]) / float(row["baseline_ecl"])
            if float(row["baseline_ecl"])
            else 0.0
        ),
        axis=1,
    )
    portfolio_summary = pd.DataFrame(portfolio_rows)
    baseline_ecl = float(
        portfolio_summary.loc[
            portfolio_summary["case_id"] == baseline_id,
            "modelled_ecl",
        ].iloc[0]
    )
    portfolio_summary["ecl_change"] = portfolio_summary["modelled_ecl"] - baseline_ecl
    portfolio_summary["ecl_change_pct"] = (
        portfolio_summary["ecl_change"] / baseline_ecl if baseline_ecl else 0.0
    )
    return CashFlowSensitivityResult(
        portfolio_summary=portfolio_summary,
        account_summary=account_summary,
        monthly_projection=pd.concat(projections, ignore_index=True),
        case_results=case_results,
    )


def _monthly_rate(annual_rate: float) -> float:
    return 1.0 - (1.0 - annual_rate) ** (1.0 / 12.0)


def _validate_required_columns(
    frame: pd.DataFrame,
    required_columns: set[str],
    label: str,
) -> None:
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing required columns: {sorted(missing)}")


def _validate_cashflow_input_values(
    accounts: pd.DataFrame,
    marginal_pd_curves: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
    recovery_assumptions: pd.DataFrame,
) -> None:
    frames = {
        "accounts": accounts,
        "marginal_pd_curves": marginal_pd_curves,
        "contractual_schedule": contractual_schedule,
        "recovery_assumptions": recovery_assumptions,
    }
    for label, frame in frames.items():
        if frame.empty:
            raise ValueError(f"{label} must not be empty")

    _validate_non_empty_text(accounts["account_id"], "accounts.account_id")
    _validate_non_empty_text(
        marginal_pd_curves["account_id"],
        "marginal_pd_curves.account_id",
    )
    _validate_non_empty_text(
        marginal_pd_curves["scenario"],
        "marginal_pd_curves.scenario",
    )
    _validate_non_empty_text(
        contractual_schedule["account_id"],
        "contractual_schedule.account_id",
    )
    _validate_non_empty_text(
        recovery_assumptions["account_id"],
        "recovery_assumptions.account_id",
    )
    _validate_non_empty_text(
        recovery_assumptions["scenario"],
        "recovery_assumptions.scenario",
    )

    normalised_account_ids = accounts["account_id"].str.strip()
    if normalised_account_ids.duplicated().any():
        raise ValueError("accounts.account_id must be unique")

    effective_interest_rates = _finite_numeric_values(
        accounts["effective_interest_rate"],
        "accounts.effective_interest_rate",
    )
    if (effective_interest_rates <= -1).any():
        raise ValueError("accounts.effective_interest_rate must be greater than -1")
    gross_exposures = _finite_numeric_values(
        accounts["gross_exposure"],
        "accounts.gross_exposure",
    )
    if (gross_exposures < 0).any():
        raise ValueError("accounts.gross_exposure must be nonnegative")

    curve_months = _positive_integer_values(
        marginal_pd_curves["month"],
        "marginal_pd_curves.month",
    )
    marginal_pds = _finite_numeric_values(
        marginal_pd_curves["marginal_pd"],
        "marginal_pd_curves.marginal_pd",
    )
    if ((marginal_pds < 0) | (marginal_pds > 1)).any():
        raise ValueError("marginal_pd_curves.marginal_pd must be between 0 and 1")

    curve_keys = pd.DataFrame(
        {
            "account_id": marginal_pd_curves["account_id"].str.strip(),
            "scenario": marginal_pd_curves["scenario"].str.strip(),
            "month": curve_months,
        }
    )
    if curve_keys.duplicated().any():
        raise ValueError(
            "marginal_pd_curves must contain one row per account/scenario/month"
        )
    cumulative_pd = pd.DataFrame(
        {
            "account_id": curve_keys["account_id"],
            "scenario": curve_keys["scenario"],
            "marginal_pd": marginal_pds,
        }
    ).groupby(["account_id", "scenario"])["marginal_pd"].sum()
    if (cumulative_pd > 1.0 + 1e-12).any():
        raise ValueError("cumulative marginal_pd must not exceed 1")

    schedule_months = _positive_integer_values(
        contractual_schedule["month"],
        "contractual_schedule.month",
    )
    principal_due = _finite_numeric_values(
        contractual_schedule["contractual_principal_due"],
        "contractual_schedule.contractual_principal_due",
    )
    if (principal_due < 0).any():
        raise ValueError(
            "contractual_schedule.contractual_principal_due must be nonnegative"
        )
    schedule_keys = pd.DataFrame(
        {
            "account_id": contractual_schedule["account_id"].str.strip(),
            "month": schedule_months,
        }
    )
    if schedule_keys.duplicated().any():
        raise ValueError("contractual_schedule must contain one row per account/month")

    expected_accounts = set(normalised_account_ids)
    if set(curve_keys["account_id"]) != expected_accounts:
        raise ValueError("marginal_pd_curves account scope must exactly match accounts")
    if set(schedule_keys["account_id"]) != expected_accounts:
        raise ValueError("contractual_schedule account scope must exactly match accounts")


def _normalise_cashflow_inputs(
    accounts: pd.DataFrame,
    marginal_pd_curves: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
    recovery_assumptions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    accounts = accounts.copy()
    marginal_pd_curves = marginal_pd_curves.copy()
    contractual_schedule = contractual_schedule.copy()
    recovery_assumptions = recovery_assumptions.copy()

    accounts["account_id"] = accounts["account_id"].str.strip()
    accounts["effective_interest_rate"] = pd.to_numeric(
        accounts["effective_interest_rate"]
    )
    accounts["gross_exposure"] = pd.to_numeric(accounts["gross_exposure"])

    marginal_pd_curves["account_id"] = marginal_pd_curves["account_id"].str.strip()
    marginal_pd_curves["scenario"] = marginal_pd_curves["scenario"].str.strip()
    marginal_pd_curves["month"] = pd.to_numeric(
        marginal_pd_curves["month"]
    ).astype(int)
    marginal_pd_curves["marginal_pd"] = pd.to_numeric(
        marginal_pd_curves["marginal_pd"]
    )

    contractual_schedule["account_id"] = contractual_schedule[
        "account_id"
    ].str.strip()
    contractual_schedule["month"] = pd.to_numeric(
        contractual_schedule["month"]
    ).astype(int)
    contractual_schedule["contractual_principal_due"] = pd.to_numeric(
        contractual_schedule["contractual_principal_due"]
    )

    recovery_assumptions["account_id"] = recovery_assumptions[
        "account_id"
    ].str.strip()
    recovery_assumptions["scenario"] = recovery_assumptions["scenario"].str.strip()
    return accounts, marginal_pd_curves, contractual_schedule, recovery_assumptions


def _validate_non_empty_text(values: pd.Series, label: str) -> None:
    if not values.map(
        lambda value: isinstance(value, str) and bool(value.strip())
    ).all():
        raise ValueError(f"{label} must contain non-empty values")


def _finite_numeric_values(values: pd.Series, label: str) -> pd.Series:
    numeric_values = pd.to_numeric(values, errors="coerce")
    if numeric_values.isna().any() or not numeric_values.map(
        lambda value: math.isfinite(float(value))
    ).all():
        raise ValueError(f"{label} must contain finite numeric values")
    if values.map(lambda value: isinstance(value, bool)).any():
        raise TypeError(f"{label} must contain finite numeric values")
    return numeric_values


def _positive_integer_values(values: pd.Series, label: str) -> pd.Series:
    numeric_values = _finite_numeric_values(values, label)
    if ((numeric_values <= 0) | (numeric_values % 1 != 0)).any():
        raise ValueError(f"{label} must contain positive integers")
    return numeric_values.astype(int)


def _validate_cases(cases: tuple[CashFlowSensitivityCase, ...]) -> None:
    if not cases:
        raise ValueError("Cash-flow sensitivity cases must be provided")
    case_ids = [case.case_id for case in cases]
    if any(not isinstance(case_id, str) or not case_id.strip() for case_id in case_ids):
        raise ValueError("case_id must be a non-empty string")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case IDs must be unique")
    for case in cases:
        _validate_case_adjustments(case)

    baseline_cases = [case for case in cases if case.is_baseline]
    if len(baseline_cases) != 1:
        raise ValueError("Exactly one cash-flow sensitivity case must be the baseline")

    baseline = baseline_cases[0]
    neutral_values = (
        baseline.annual_prepayment_rate_multiplier == 1.0
        and baseline.cure_rate_multiplier == 1.0
        and baseline.collateral_value_multiplier == 1.0
        and baseline.collateral_haircut_addon == 0.0
        and baseline.cure_delay_addon_months == 0
        and baseline.collateral_recovery_delay_addon_months == 0
    )
    if not neutral_values:
        raise ValueError("baseline case must use neutral adjustments")


def _validate_case_adjustments(case: CashFlowSensitivityCase) -> None:
    if not isinstance(case.case_id, str) or not case.case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if not isinstance(case.description, str):
        raise TypeError("case description must be a string")
    if not isinstance(case.is_baseline, bool):
        raise TypeError("is_baseline must be boolean")

    numeric_adjustment_names = [
        "annual_prepayment_rate_multiplier",
        "cure_rate_multiplier",
        "collateral_value_multiplier",
        "collateral_haircut_addon",
    ]
    delay_adjustment_names = [
        "cure_delay_addon_months",
        "collateral_recovery_delay_addon_months",
    ]
    for name in numeric_adjustment_names:
        value = getattr(case, name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value < 0
        ):
            raise ValueError("case adjustments must be finite and nonnegative")
    for name in delay_adjustment_names:
        value = getattr(case, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("case adjustments must be finite and nonnegative")


def _validate_adjusted_recovery_rates(
    annual_prepayment_rate: float,
    cure_rate: float,
    collateral_haircut: float,
) -> None:
    adjusted_rates = (
        annual_prepayment_rate,
        cure_rate,
        collateral_haircut,
    )
    if any(rate < 0 or rate > 1 for rate in adjusted_rates):
        raise ValueError("adjusted prepayment, cure, and haircut rates must be between 0 and 1")


def _validate_contractual_totals(
    accounts: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
) -> None:
    scheduled_totals = contractual_schedule.groupby("account_id")[
        "contractual_principal_due"
    ].sum()
    for account in accounts.to_dict("records"):
        scheduled_total = float(scheduled_totals.get(account["account_id"], 0.0))
        if not math.isclose(
            scheduled_total,
            float(account["gross_exposure"]),
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            raise ValueError(
                "contractual principal must fully amortise gross exposure"
            )


def _validate_recovery_financial_values(
    recovery_assumptions: pd.DataFrame,
) -> None:
    rate_columns = [
        "annual_prepayment_rate",
        "cure_rate",
        "collateral_haircut",
        "recovery_cost_rate",
    ]
    numeric_columns = [*rate_columns, "collateral_value"]
    numeric_values: dict[str, pd.Series] = {}
    for column in numeric_columns:
        values = pd.to_numeric(recovery_assumptions[column], errors="coerce")
        if not values.map(math.isfinite).all():
            raise ValueError(
                "recovery assumptions must contain finite numeric values"
            )
        numeric_values[column] = values
    if any(
        ((numeric_values[column] < 0) | (numeric_values[column] > 1)).any()
        for column in rate_columns
    ):
        raise ValueError("recovery rates must be between 0 and 1")
    if (numeric_values["collateral_value"] < 0).any():
        raise ValueError("collateral_value must be nonnegative")

    for column in ["cure_delay_months", "collateral_recovery_delay_months"]:
        raw_values = recovery_assumptions[column]
        values = pd.to_numeric(raw_values, errors="coerce")
        if (
            raw_values.map(lambda value: isinstance(value, bool)).any()
            or not values.map(math.isfinite).all()
            or (values < 0).any()
            or (values % 1 != 0).any()
        ):
            raise ValueError("recovery delays must be nonnegative integers")

    for column in [
        "collateral_is_integral",
        "collateral_recognized_separately",
    ]:
        if not recovery_assumptions[column].map(
            lambda value: isinstance(value, bool)
        ).all():
            raise TypeError("collateral eligibility flags must be boolean")


def _validate_recovery_scope(
    marginal_pd_curves: pd.DataFrame,
    recovery_assumptions: pd.DataFrame,
) -> None:
    keys = ["account_id", "scenario"]
    expected_pairs = set(
        marginal_pd_curves[keys].drop_duplicates().itertuples(index=False, name=None)
    )
    actual_pair_rows = recovery_assumptions[keys]
    actual_pairs = set(actual_pair_rows.itertuples(index=False, name=None))
    if actual_pair_rows.duplicated().any() or actual_pairs != expected_pairs:
        raise ValueError(
            "recovery assumptions must cover each account/scenario exactly once"
        )


def _validate_matching_horizons(
    accounts: pd.DataFrame,
    marginal_pd_curves: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
) -> None:
    for account_id in accounts["account_id"]:
        schedule_months = sorted(
            contractual_schedule.loc[
                contractual_schedule["account_id"] == account_id,
                "month",
            ].astype(int)
        )
        if not schedule_months or schedule_months != list(
            range(1, max(schedule_months) + 1)
        ):
            raise ValueError(
                "contractual schedule and marginal PD curves must share a contiguous horizon"
            )
        account_curves = marginal_pd_curves[
            marginal_pd_curves["account_id"] == account_id
        ]
        if account_curves.empty:
            raise ValueError(
                "contractual schedule and marginal PD curves must share a contiguous horizon"
            )
        for _, curve in account_curves.groupby("scenario"):
            curve_months = sorted(curve["month"].astype(int))
            if curve_months != schedule_months:
                raise ValueError(
                    "contractual schedule and marginal PD curves must share a contiguous horizon"
                )


def _collateral_eligibility_reason(
    collateral_value: float,
    collateral_is_integral: bool,
    collateral_recognized_separately: bool,
) -> str:
    if collateral_value <= 0:
        return "not_applicable_no_collateral"
    if collateral_recognized_separately:
        return "excluded_separately_recognized"
    if not collateral_is_integral:
        return "excluded_not_integral"
    return "included_integral_not_separate"
