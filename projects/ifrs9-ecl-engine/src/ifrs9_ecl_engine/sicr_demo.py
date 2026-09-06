from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.demo import build_demo_inputs
from ifrs9_ecl_engine.engine import ECLResult, run_ecl_engine
from ifrs9_ecl_engine.sicr import SICRRebuttal

REPORTING_DATE = "2023-12-31"


@dataclass(frozen=True)
class SICRRebuttalPipelineOutput:
    baseline_result: ECLResult
    governed_result: ECLResult
    account_comparison: pd.DataFrame
    reconciliation: pd.DataFrame
    report_paths: dict[str, Path]


def build_demo_sicr_inputs(
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, float],
    tuple[SICRRebuttal, ...],
]:
    accounts, term_structures, scenario_weights = build_demo_inputs()
    accounts = accounts.copy()
    accounts.loc[accounts["account_id"] == "SYN-ECL-002", "days_past_due"] = 34
    rebuttals = (
        SICRRebuttal(
            rebuttal_id="SICR-REB-001",
            account_id="SYN-ECL-003",
            observed_days_past_due=36,
            evidence_reference="SYN-EVIDENCE-001",
            evidence_summary=(
                "Synthetic administrative delay evidence with unchanged forward risk"
            ),
            reasonable_and_supportable=True,
            forward_looking_review_completed=True,
            other_sicr_indicators_present=False,
            decision_date="2023-12-20",
            valid_until="2024-03-31",
            approval_status="approved",
            approved_by="Synthetic ECL Committee",
        ),
        SICRRebuttal(
            rebuttal_id="SICR-REB-002",
            account_id="SYN-ECL-002",
            observed_days_past_due=34,
            evidence_reference="SYN-EVIDENCE-002",
            evidence_summary="Synthetic operational delay evidence awaiting committee review",
            reasonable_and_supportable=True,
            forward_looking_review_completed=True,
            other_sicr_indicators_present=False,
            decision_date="2023-12-22",
            valid_until="2024-03-31",
            approval_status="pending",
            approved_by=None,
        ),
        SICRRebuttal(
            rebuttal_id="SICR-REB-003",
            account_id="SYN-ECL-005",
            observed_days_past_due=74,
            evidence_reference="SYN-EVIDENCE-003",
            evidence_summary=(
                "Synthetic payment-delay explanation contradicted by another SICR signal"
            ),
            reasonable_and_supportable=True,
            forward_looking_review_completed=True,
            other_sicr_indicators_present=False,
            decision_date="2023-12-18",
            valid_until="2024-03-31",
            approval_status="approved",
            approved_by="Synthetic ECL Committee",
        ),
    )
    return accounts, term_structures, scenario_weights, rebuttals


def run_sicr_rebuttal_pipeline(
    output_dir: str | Path = "reports/sicr_rebuttal",
) -> SICRRebuttalPipelineOutput:
    accounts, term_structures, scenario_weights, rebuttals = build_demo_sicr_inputs()
    baseline_result = run_ecl_engine(accounts, term_structures, scenario_weights)
    governed_result = run_ecl_engine(
        accounts,
        term_structures,
        scenario_weights,
        reporting_date=REPORTING_DATE,
        sicr_rebuttals=rebuttals,
    )
    account_comparison = _account_comparison(baseline_result, governed_result)
    reconciliation = _reconciliation(baseline_result, governed_result)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = write_sicr_rebuttal_reports(
        governed_result.sicr_rebuttal_register,
        account_comparison,
        reconciliation,
        output_path,
    )
    return SICRRebuttalPipelineOutput(
        baseline_result=baseline_result,
        governed_result=governed_result,
        account_comparison=account_comparison,
        reconciliation=reconciliation,
        report_paths=report_paths,
    )


def write_sicr_rebuttal_reports(
    register: pd.DataFrame,
    account_comparison: pd.DataFrame,
    reconciliation: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    outputs = {
        "sicr_rebuttal_register": output_dir / "sicr_rebuttal_register.csv",
        "account_stage_comparison": output_dir / "account_stage_comparison.csv",
        "ecl_impact_reconciliation": output_dir / "ecl_impact_reconciliation.csv",
    }
    frames = {
        "sicr_rebuttal_register": register,
        "account_stage_comparison": account_comparison,
        "ecl_impact_reconciliation": reconciliation,
    }
    for name, frame in frames.items():
        frame.to_csv(
            outputs[name],
            index=False,
            float_format="%.6f",
            lineterminator="\n",
        )
    report_path = output_dir / "sicr_rebuttal_report.md"
    report_path.write_text(
        _markdown_report(register, account_comparison, reconciliation),
        encoding="utf-8",
        newline="\n",
    )
    return {**outputs, "sicr_rebuttal_report": report_path}


def _account_comparison(
    baseline_result: ECLResult,
    governed_result: ECLResult,
) -> pd.DataFrame:
    baseline = baseline_result.account_ecl[
        ["account_id", "days_past_due", "stage", "stage_reason", "weighted_ecl"]
    ].rename(
        columns={
            "stage": "baseline_stage",
            "stage_reason": "baseline_stage_reason",
            "weighted_ecl": "baseline_weighted_ecl",
        }
    )
    governed = governed_result.account_ecl[
        ["account_id", "stage", "stage_reason", "weighted_ecl"]
    ].rename(
        columns={
            "stage": "governed_stage",
            "stage_reason": "governed_stage_reason",
            "weighted_ecl": "governed_weighted_ecl",
        }
    )
    decisions = governed_result.sicr_rebuttal_register[
        ["account_id", "rebuttal_id", "decision_outcome"]
    ]
    comparison = baseline.merge(governed, on="account_id", validate="one_to_one")
    comparison = comparison.merge(decisions, on="account_id", how="left", validate="one_to_one")
    comparison["rebuttal_id"] = comparison["rebuttal_id"].fillna("")
    comparison["decision_outcome"] = comparison["decision_outcome"].fillna("not_requested")
    comparison["stage_changed"] = comparison["baseline_stage"] != comparison["governed_stage"]
    comparison["ecl_change"] = (
        comparison["governed_weighted_ecl"] - comparison["baseline_weighted_ecl"]
    )
    return comparison[
        [
            "account_id",
            "days_past_due",
            "rebuttal_id",
            "decision_outcome",
            "baseline_stage",
            "baseline_stage_reason",
            "governed_stage",
            "governed_stage_reason",
            "stage_changed",
            "baseline_weighted_ecl",
            "governed_weighted_ecl",
            "ecl_change",
        ]
    ].sort_values("account_id").reset_index(drop=True)


def _reconciliation(
    baseline_result: ECLResult,
    governed_result: ECLResult,
) -> pd.DataFrame:
    baseline_total = _total_row(baseline_result)
    governed_total = _total_row(governed_result)
    baseline_ecl = float(baseline_total["weighted_ecl"])
    governed_ecl = float(governed_total["weighted_ecl"])
    ecl_reduction = baseline_ecl - governed_ecl
    register = governed_result.sicr_rebuttal_register
    baseline_counts = baseline_result.account_ecl["stage"].value_counts()
    governed_counts = governed_result.account_ecl["stage"].value_counts()
    outcomes = register["decision_outcome"]
    return pd.DataFrame(
        [
            {
                "reporting_date": REPORTING_DATE,
                "gross_exposure": float(governed_total["gross_exposure"]),
                "baseline_modelled_ecl": baseline_ecl,
                "governed_modelled_ecl": governed_ecl,
                "ecl_change": governed_ecl - baseline_ecl,
                "ecl_reduction": ecl_reduction,
                "ecl_reduction_pct": ecl_reduction / baseline_ecl if baseline_ecl else 0.0,
                "baseline_stage1_accounts": int(baseline_counts.get(1, 0)),
                "baseline_stage2_accounts": int(baseline_counts.get(2, 0)),
                "baseline_stage3_accounts": int(baseline_counts.get(3, 0)),
                "governed_stage1_accounts": int(governed_counts.get(1, 0)),
                "governed_stage2_accounts": int(governed_counts.get(2, 0)),
                "governed_stage3_accounts": int(governed_counts.get(3, 0)),
                "rebuttal_request_count": len(register),
                "effective_rebuttal_count": int(outcomes.eq("approved_effective").sum()),
                "pending_rebuttal_count": int(outcomes.eq("pending_approval").sum()),
                "blocked_rebuttal_count": int(outcomes.str.startswith("blocked_").sum()),
            }
        ]
    )


def _total_row(result: ECLResult) -> pd.Series:
    total = result.portfolio_summary[result.portfolio_summary["stage"].astype(str) == "Total"]
    if len(total) != 1:
        raise ValueError("portfolio_summary must contain exactly one Total row")
    return total.iloc[0]


def _markdown_report(
    register: pd.DataFrame,
    account_comparison: pd.DataFrame,
    reconciliation: pd.DataFrame,
) -> str:
    total = reconciliation.iloc[0]
    changed = account_comparison[account_comparison["stage_changed"]]
    return "\n".join(
        [
            "# SICR Rebuttal Governance Report",
            "",
            (
                "Deterministic synthetic evidence generated by "
                "`scripts/run_sicr_rebuttal.py`."
            ),
            "",
            "## Portfolio Impact",
            "",
            f"- Reporting date: {total['reporting_date']}",
            f"- Rebuttal requests: {int(total['rebuttal_request_count'])}",
            f"- Effective rebuttals: {int(total['effective_rebuttal_count'])}",
            f"- Baseline modelled ECL: {total['baseline_modelled_ecl']:,.2f}",
            f"- Governed modelled ECL: {total['governed_modelled_ecl']:,.2f}",
            (
                "- ECL change (governed - baseline): "
                f"{total['ecl_change']:,.2f} ({-total['ecl_reduction_pct']:.2%})"
            ),
            f"- Accounts with changed stage: {len(changed)}",
            "",
            "## Decision Outcomes",
            "",
            _format_markdown_table(
                register[
                    [
                        "rebuttal_id",
                        "account_id",
                        "current_days_past_due",
                        "approval_status",
                        "decision_outcome",
                        "stage_without_rebuttal",
                        "stage_with_rebuttal",
                    ]
                ]
            ),
            "",
            "## Stage and ECL Impact",
            "",
            _format_markdown_table(
                account_comparison[
                    [
                        "account_id",
                        "decision_outcome",
                        "baseline_stage",
                        "governed_stage",
                        "baseline_weighted_ecl",
                        "governed_weighted_ecl",
                        "ecl_change",
                    ]
                ]
            ),
            "",
            "## Caveat",
            "",
            (
                "All accounts, evidence references, committee decisions, and dates are "
                "synthetic. This demonstrates controls, not an accounting conclusion."
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
