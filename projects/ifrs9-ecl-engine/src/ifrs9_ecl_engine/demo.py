from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.engine import ECLResult, run_ecl_engine

SCENARIO_WEIGHTS = {"base": 0.6, "upside": 0.15, "downside": 0.25}
SCENARIO_PD_MULTIPLIERS = {"base": 1.0, "upside": 0.75, "downside": 1.65}
SCENARIO_LGD_ADDONS = {"base": 0.0, "upside": -0.03, "downside": 0.08}


@dataclass(frozen=True)
class DemoPipelineOutput:
    result: ECLResult
    report_paths: dict[str, Path]


def build_demo_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    accounts = pd.DataFrame(
        [
            _account("SYN-ECL-001", 0, False, False, 1, 0.105, 150_000, 0.0011, 0.33),
            _account("SYN-ECL-002", 12, False, False, 1, 0.118, 95_000, 0.0018, 0.38),
            _account("SYN-ECL-003", 36, False, False, 1, 0.132, 82_000, 0.0034, 0.42),
            _account("SYN-ECL-004", 8, True, False, 1, 0.098, 120_000, 0.0042, 0.39),
            _account("SYN-ECL-005", 74, True, False, 2, 0.145, 62_000, 0.0075, 0.47),
            _account("SYN-ECL-006", 102, True, True, 2, 0.157, 45_000, 0.0120, 0.58),
        ]
    )
    term_structures = pd.DataFrame(_term_rows(accounts))
    account_columns = [
        "account_id",
        "days_past_due",
        "sicr",
        "credit_impaired",
        "prior_stage",
        "effective_interest_rate",
        "gross_exposure",
    ]
    return accounts[account_columns], term_structures, dict(SCENARIO_WEIGHTS)


def run_demo_pipeline(output_dir: str | Path = "reports") -> DemoPipelineOutput:
    accounts, term_structures, scenario_weights = build_demo_inputs()
    result = run_ecl_engine(accounts, term_structures, scenario_weights)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = write_reports(result, output_path)
    return DemoPipelineOutput(result=result, report_paths=report_paths)


def write_reports(result: ECLResult, output_dir: Path) -> dict[str, Path]:
    outputs = {
        "account_ecl": output_dir / "account_ecl.csv",
        "scenario_ecl": output_dir / "scenario_ecl.csv",
        "portfolio_summary": output_dir / "portfolio_summary.csv",
        "stage_migration": output_dir / "stage_migration.csv",
    }
    result.account_ecl.to_csv(outputs["account_ecl"], index=False, float_format="%.6f")
    result.scenario_ecl.to_csv(outputs["scenario_ecl"], index=False, float_format="%.6f")
    result.portfolio_summary.to_csv(
        outputs["portfolio_summary"],
        index=False,
        float_format="%.6f",
    )
    result.stage_migration.to_csv(
        outputs["stage_migration"],
        index=False,
        float_format="%.6f",
    )
    report_path = output_dir / "ecl_report.md"
    report_path.write_text(_markdown_report(result), encoding="utf-8")
    return {**outputs, "ecl_report": report_path}


def _account(
    account_id: str,
    days_past_due: int,
    sicr: bool,
    credit_impaired: bool,
    prior_stage: int,
    effective_interest_rate: float,
    gross_exposure: int,
    base_monthly_pd: float,
    base_lgd: float,
) -> dict:
    return {
        "account_id": account_id,
        "days_past_due": days_past_due,
        "sicr": sicr,
        "credit_impaired": credit_impaired,
        "prior_stage": prior_stage,
        "effective_interest_rate": effective_interest_rate,
        "gross_exposure": gross_exposure,
        "base_monthly_pd": base_monthly_pd,
        "base_lgd": base_lgd,
    }


def _term_rows(accounts: pd.DataFrame) -> list[dict]:
    rows = []
    for account in accounts.to_dict("records"):
        for scenario in ["base", "upside", "downside"]:
            for month in range(1, 37):
                seasoning = 1.0 + (month - 1) * 0.012
                marginal_pd = account["base_monthly_pd"] * SCENARIO_PD_MULTIPLIERS[scenario]
                lgd = account["base_lgd"] + SCENARIO_LGD_ADDONS[scenario]
                amortisation = max(0.35, 1.0 - (month - 1) * 0.015)
                rows.append(
                    {
                        "account_id": account["account_id"],
                        "scenario": scenario,
                        "month": month,
                        "marginal_pd": round(min(marginal_pd * seasoning, 0.08), 6),
                        "lgd": round(min(max(lgd, 0.0), 1.0), 6),
                        "ead": round(account["gross_exposure"] * amortisation, 2),
                    }
                )
    return rows


def _markdown_report(result: ECLResult) -> str:
    total = result.portfolio_summary[result.portfolio_summary["stage"] == "Total"].iloc[0]
    total_exposure = total["gross_exposure"]
    total_ecl = total["weighted_ecl"]
    coverage_ratio = total["coverage_ratio"]
    scenario_summary = (
        result.scenario_ecl.groupby("scenario", as_index=False)
        .agg(
            scenario_weight=("scenario_weight", "first"),
            scenario_ecl=("scenario_ecl", "sum"),
            weighted_scenario_ecl=("weighted_scenario_ecl", "sum"),
        )
        .sort_values("scenario")
    )
    return "\n".join(
        [
            "# IFRS 9 ECL Demo Report",
            "",
            "Synthetic educational demo output generated from `scripts/run_pipeline.py`.",
            "",
            "## Portfolio Summary",
            "",
            f"- Gross exposure: {total_exposure:,.2f}",
            f"- Probability-weighted ECL: {total_ecl:,.2f}",
            f"- Coverage ratio: {coverage_ratio:.4%}",
            f"- Account count: {int(total['account_count'])}",
            "",
            "## Stage Summary",
            "",
            _format_markdown_table(result.portfolio_summary),
            "",
            "## Scenario Contribution",
            "",
            _format_markdown_table(scenario_summary),
            "",
            "## Stage Migration",
            "",
            _format_markdown_table(result.stage_migration),
            "",
            "## Caveat",
            "",
            "This is a simplified educational PD/LGD/EAD implementation, not accounting advice.",
            "Stage 3 uses the same proxy and is not a production credit-impaired cash-shortfall model.",
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
