from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.cashflow import (
    CashFlowSensitivityCase,
    CashFlowSensitivityResult,
    analyse_cashflow_sensitivity,
)
from ifrs9_ecl_engine.demo import build_demo_inputs


@dataclass(frozen=True)
class CashFlowSensitivityPipelineOutput:
    analysis: CashFlowSensitivityResult
    reconciliation: pd.DataFrame
    monthly_portfolio_projection: pd.DataFrame
    contractual_schedule: pd.DataFrame
    recovery_assumptions: pd.DataFrame
    report_paths: dict[str, Path]


def build_demo_cashflow_inputs(
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, float],
    tuple[CashFlowSensitivityCase, ...],
]:
    accounts, term_structures, scenario_weights = build_demo_inputs()
    marginal_pd_curves = term_structures[
        ["account_id", "scenario", "month", "marginal_pd"]
    ].copy()
    contractual_schedule = _build_contractual_schedule(accounts)
    recovery_assumptions = _build_recovery_assumptions(accounts)
    cases = _build_sensitivity_cases()
    return (
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
        scenario_weights,
        cases,
    )


def run_cashflow_sensitivity_pipeline(
    output_dir: str | Path = "reports/cashflow_sensitivity",
) -> CashFlowSensitivityPipelineOutput:
    (
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
        scenario_weights,
        cases,
    ) = build_demo_cashflow_inputs()
    analysis = analyse_cashflow_sensitivity(
        accounts,
        marginal_pd_curves,
        contractual_schedule,
        recovery_assumptions,
        scenario_weights,
        cases,
    )
    reconciliation = _build_reconciliation(analysis)
    monthly_portfolio_projection = _aggregate_monthly_projection(
        analysis.monthly_projection,
        scenario_weights,
        cases,
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = write_cashflow_sensitivity_reports(
        analysis,
        reconciliation,
        monthly_portfolio_projection,
        contractual_schedule,
        recovery_assumptions,
        output_path,
    )
    return CashFlowSensitivityPipelineOutput(
        analysis=analysis,
        reconciliation=reconciliation,
        monthly_portfolio_projection=monthly_portfolio_projection,
        contractual_schedule=contractual_schedule,
        recovery_assumptions=recovery_assumptions,
        report_paths=report_paths,
    )


def write_cashflow_sensitivity_reports(
    analysis: CashFlowSensitivityResult,
    reconciliation: pd.DataFrame,
    monthly_portfolio_projection: pd.DataFrame,
    contractual_schedule: pd.DataFrame,
    recovery_assumptions: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    outputs = {
        "cashflow_sensitivity_summary": output_dir
        / "cashflow_sensitivity_summary.csv",
        "account_ecl_sensitivity": output_dir / "account_ecl_sensitivity.csv",
        "cashflow_reconciliation": output_dir / "cashflow_reconciliation.csv",
        "monthly_portfolio_projection": output_dir
        / "monthly_portfolio_projection.csv",
        "contractual_schedule": output_dir / "contractual_schedule.csv",
        "recovery_assumptions": output_dir / "recovery_assumptions.csv",
    }
    frames = {
        "cashflow_sensitivity_summary": analysis.portfolio_summary,
        "account_ecl_sensitivity": analysis.account_summary,
        "cashflow_reconciliation": reconciliation,
        "monthly_portfolio_projection": monthly_portfolio_projection,
        "contractual_schedule": contractual_schedule,
        "recovery_assumptions": recovery_assumptions,
    }
    for name, frame in frames.items():
        frame.to_csv(
            outputs[name],
            index=False,
            float_format="%.6f",
            lineterminator="\n",
        )
    report_path = output_dir / "cashflow_sensitivity_report.md"
    report_path.write_text(
        _markdown_report(analysis, reconciliation),
        encoding="utf-8",
        newline="\n",
    )
    return {**outputs, "cashflow_sensitivity_report": report_path}


def _build_contractual_schedule(accounts: pd.DataFrame) -> pd.DataFrame:
    profiles = {
        "SYN-ECL-001": "level_36_month",
        "SYN-ECL-002": "level_24_month",
        "SYN-ECL-003": "50pct_balloon_month_36",
        "SYN-ECL-004": "level_36_month",
        "SYN-ECL-005": "65pct_balloon_month_36",
        "SYN-ECL-006": "bullet_month_36",
    }
    rows: list[dict[str, object]] = []
    for account in accounts.to_dict("records"):
        account_id = str(account["account_id"])
        exposure = float(account["gross_exposure"])
        profile = profiles[account_id]
        principal = _principal_profile(exposure, profile)
        for month, amount in enumerate(principal, start=1):
            rows.append(
                {
                    "account_id": account_id,
                    "repayment_profile": profile,
                    "month": month,
                    "contractual_principal_due": amount,
                }
            )
    return pd.DataFrame(rows).sort_values(["account_id", "month"]).reset_index(drop=True)


def _principal_profile(exposure: float, profile: str) -> list[float]:
    if profile == "level_36_month":
        values = [exposure / 36.0] * 35
        return [*values, exposure - sum(values)]
    if profile == "level_24_month":
        values = [exposure / 24.0] * 23
        return [*values, exposure - sum(values), *([0.0] * 12)]
    if profile == "50pct_balloon_month_36":
        values = [exposure * 0.50 / 35.0] * 35
        return [*values, exposure - sum(values)]
    if profile == "65pct_balloon_month_36":
        values = [exposure * 0.35 / 35.0] * 35
        return [*values, exposure - sum(values)]
    if profile == "bullet_month_36":
        return [*([0.0] * 35), exposure]
    raise ValueError(f"Unsupported contractual repayment profile: {profile}")


def _build_recovery_assumptions(accounts: pd.DataFrame) -> pd.DataFrame:
    account_profiles = {
        "SYN-ECL-001": (0.14, 0.70, 0.00, "unsecured", False, False),
        "SYN-ECL-002": (0.11, 0.62, 0.25, "separate_guarantee", True, True),
        "SYN-ECL-003": (0.08, 0.52, 0.75, "residential_property", True, False),
        "SYN-ECL-004": (0.10, 0.56, 0.65, "commercial_property", True, False),
        "SYN-ECL-005": (0.05, 0.38, 0.55, "equipment", True, False),
        "SYN-ECL-006": (0.02, 0.22, 0.95, "residential_property", True, False),
    }
    scenario_profiles = {
        "base": (1.00, 0.00, 1.00, 0.20, 0.06, 4, 9),
        "upside": (1.25, 0.08, 1.05, 0.12, 0.04, 2, 6),
        "downside": (0.60, -0.12, 0.85, 0.35, 0.09, 8, 15),
    }
    exposures = accounts.set_index("account_id")["gross_exposure"]
    rows: list[dict[str, object]] = []
    for account_id, profile in account_profiles.items():
        base_cpr, base_cure, collateral_fraction, security_type, integral, separate = (
            profile
        )
        for scenario, scenario_profile in scenario_profiles.items():
            (
                cpr_multiplier,
                cure_addon,
                collateral_multiplier,
                haircut,
                recovery_cost,
                cure_delay,
                collateral_delay,
            ) = scenario_profile
            rows.append(
                {
                    "account_id": account_id,
                    "scenario": scenario,
                    "security_type": security_type,
                    "assumption_basis": "synthetic_scenario_policy",
                    "annual_prepayment_rate": base_cpr * cpr_multiplier,
                    "cure_rate": max(0.0, base_cure + cure_addon),
                    "cure_delay_months": cure_delay,
                    "collateral_value": (
                        float(exposures.loc[account_id])
                        * collateral_fraction
                        * collateral_multiplier
                    ),
                    "collateral_haircut": haircut,
                    "recovery_cost_rate": recovery_cost,
                    "collateral_recovery_delay_months": collateral_delay,
                    "collateral_is_integral": integral,
                    "collateral_recognized_separately": separate,
                }
            )
    return pd.DataFrame(rows).sort_values(["account_id", "scenario"]).reset_index(
        drop=True
    )


def _build_sensitivity_cases() -> tuple[CashFlowSensitivityCase, ...]:
    return (
        CashFlowSensitivityCase(
            case_id="baseline",
            description="Contractual schedule and approved synthetic recovery assumptions",
            is_baseline=True,
        ),
        CashFlowSensitivityCase(
            case_id="low_prepayment",
            description="Reduce annual CPR assumptions by 50 percent",
            annual_prepayment_rate_multiplier=0.50,
        ),
        CashFlowSensitivityCase(
            case_id="low_cure",
            description="Reduce cure-rate assumptions by 35 percent",
            cure_rate_multiplier=0.65,
        ),
        CashFlowSensitivityCase(
            case_id="collateral_downturn",
            description="Reduce collateral values by 25 percent and add 10pp haircut",
            collateral_value_multiplier=0.75,
            collateral_haircut_addon=0.10,
        ),
        CashFlowSensitivityCase(
            case_id="delayed_recovery",
            description="Delay cure and collateral recovery by six months",
            cure_delay_addon_months=6,
            collateral_recovery_delay_addon_months=6,
        ),
        CashFlowSensitivityCase(
            case_id="combined_downside",
            description="Combine lower CPR, cure, collateral and slower recovery",
            annual_prepayment_rate_multiplier=0.50,
            cure_rate_multiplier=0.65,
            collateral_value_multiplier=0.75,
            collateral_haircut_addon=0.10,
            cure_delay_addon_months=6,
            collateral_recovery_delay_addon_months=6,
        ),
    )


def _build_reconciliation(analysis: CashFlowSensitivityResult) -> pd.DataFrame:
    account_totals = (
        analysis.account_summary.groupby("case_id", as_index=False)["weighted_ecl"]
        .sum()
        .rename(columns={"weighted_ecl": "account_ecl_sum"})
    )
    reconciliation = analysis.portfolio_summary[
        ["case_id", "modelled_ecl"]
    ].merge(account_totals, on="case_id", validate="one_to_one")
    reconciliation["reconciliation_difference"] = (
        reconciliation["modelled_ecl"] - reconciliation["account_ecl_sum"]
    )
    reconciliation["reconciled"] = reconciliation[
        "reconciliation_difference"
    ].abs().le(1e-9)
    return reconciliation


def _aggregate_monthly_projection(
    projection: pd.DataFrame,
    scenario_weights: dict[str, float],
    cases: tuple[CashFlowSensitivityCase, ...],
) -> pd.DataFrame:
    monthly = projection.copy()
    monthly["lgd_x_ead"] = monthly["lgd"] * monthly["ead"]
    aggregated = (
        monthly.groupby(["case_id", "scenario", "month"], as_index=False)
        .agg(
            portfolio_ead=("ead", "sum"),
            lgd_x_ead=("lgd_x_ead", "sum"),
            contractual_principal_due=("contractual_principal_due", "sum"),
            scheduled_principal_applied=("scheduled_principal_applied", "sum"),
            expected_prepayment=("expected_prepayment", "sum"),
            closing_balance=("closing_balance", "sum"),
            expected_cure_recovery=("expected_cure_recovery", "sum"),
            expected_collateral_recovery=("expected_collateral_recovery", "sum"),
            discounted_expected_recovery_at_default=(
                "discounted_expected_recovery_at_default",
                "sum",
            ),
        )
    )
    aggregated["scenario_weight"] = aggregated["scenario"].map(scenario_weights)
    aggregated["ead_weighted_lgd"] = aggregated.apply(
        lambda row: (
            float(row["lgd_x_ead"]) / float(row["portfolio_ead"])
            if float(row["portfolio_ead"])
            else 0.0
        ),
        axis=1,
    )
    case_order = {case.case_id: index for index, case in enumerate(cases)}
    aggregated["case_order"] = aggregated["case_id"].map(case_order)
    aggregated = aggregated.sort_values(
        ["case_order", "scenario", "month"]
    ).reset_index(drop=True)
    return aggregated[
        [
            "case_id",
            "scenario",
            "scenario_weight",
            "month",
            "portfolio_ead",
            "ead_weighted_lgd",
            "contractual_principal_due",
            "scheduled_principal_applied",
            "expected_prepayment",
            "closing_balance",
            "expected_cure_recovery",
            "expected_collateral_recovery",
            "discounted_expected_recovery_at_default",
        ]
    ]


def _markdown_report(
    analysis: CashFlowSensitivityResult,
    reconciliation: pd.DataFrame,
) -> str:
    summary = analysis.portfolio_summary
    baseline = summary[summary["is_baseline"]].iloc[0]
    combined = summary[summary["case_id"] == "combined_downside"].iloc[0]
    return "\n".join(
        [
            "# Contractual Cash-flow and Recovery Sensitivity Report",
            "",
            (
                "Deterministic synthetic evidence generated by "
                "`scripts/run_cashflow_sensitivity.py`."
            ),
            "",
            "## Portfolio Impact",
            "",
            f"- Gross exposure: {baseline['gross_exposure']:,.2f}",
            f"- Baseline modelled ECL: {baseline['modelled_ecl']:,.2f}",
            f"- Baseline coverage ratio: {baseline['coverage_ratio']:.4%}",
            (
                "- Combined-downside modelled ECL: "
                f"{combined['modelled_ecl']:,.2f}"
            ),
            (
                "- Combined-downside increase: "
                f"{combined['ecl_change']:,.2f} ({combined['ecl_change_pct']:.2%})"
            ),
            "",
            "## Sensitivity Cases",
            "",
            _format_markdown_table(
                summary[
                    [
                        "case_id",
                        "case_description",
                        "modelled_ecl",
                        "coverage_ratio",
                        "ecl_change",
                        "ecl_change_pct",
                    ]
                ]
            ),
            "",
            "## Method",
            "",
            (
                "- Contractual principal schedules roll opening EAD forward each month; "
                "annual CPR is converted to a single-month mortality rate."
            ),
            (
                "- Cure and eligible collateral recoveries are discounted from their "
                "expected recovery dates using the account effective interest rate."
            ),
            (
                "- Collateral is included only when integral to the contractual terms "
                "and not recognized separately, net of haircut and recovery cost."
            ),
            (
                "- The existing probability-weighted ECL engine consumes the resulting "
                "monthly marginal PD, EAD, and effective LGD term structures."
            ),
            "",
            "## Controls",
            "",
            f"- Sensitivity cases reconciled to account ECL: {reconciliation['reconciled'].all()}",
            "- Exactly one neutral baseline is required.",
            "- Rates, delays, horizons, key uniqueness, and account coverage are validated.",
            "- Separately recognized and non-integral collateral is excluded with a reason.",
            "",
            "## Accounting Boundary",
            "",
            (
                "This contractual cash-flow component supplies cash-flow-informed EAD "
                "and LGD assumptions to the portfolio engine; it is not a full direct "
                "cash-shortfall valuation and not an IFRS 9 compliance conclusion."
            ),
            (
                "Cure is an illustrative conditional recovery assumption, not a staging "
                "cure policy or accounting presentation conclusion."
            ),
            "All accounts, schedules, collateral values, and recovery assumptions are synthetic.",
            "",
            "## Primary References",
            "",
            (
                "- [IFRS 9 Financial Instruments](https://www.ifrs.org/content/dam/"
                "ifrs/publications/pdf-standards/english/2022/issued/part-a/"
                "ifrs-9-financial-instruments.pdf?bypass=on)"
            ),
            (
                "- [IFRS Transition Resource Group staff paper on collateral](https://"
                "www.ifrs.org/content/dam/ifrs/meetings/2015/december/itg/impairment-"
                "of-financial-instruments/ap5-collateral-and-other-credit-enhancements.pdf)"
            ),
            "",
        ]
    )


def _format_markdown_table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    rows = ["| " + " | ".join(headers) + " |"]
    rows.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in frame.to_dict("records"):
        rows.append("| " + " | ".join(_format_cell(row[column]) for column in headers) + " |")
    return "\n".join(rows)


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)
