from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from model_validation.macro_remediation import (
    MacroRemediationValidationResult,
    validate_macro_remediation,
)


@dataclass(frozen=True)
class MacroRemediationValidationOutput:
    result: MacroRemediationValidationResult
    input_audit: pd.DataFrame
    report_paths: dict[str, Path]


def run_macro_remediation_validation(
    developer_remediation_dir: str | Path,
    incumbent_report_dir: str | Path,
    initial_validation_dir: str | Path,
    output_dir: str | Path,
) -> MacroRemediationValidationOutput:
    remediation_dir = Path(developer_remediation_dir)
    incumbent_dir = Path(incumbent_report_dir)
    validation_dir = Path(initial_validation_dir)
    inputs = {
        "candidate_register": remediation_dir / "candidate_register.csv",
        "candidate_tuning": remediation_dir / "candidate_tuning.csv",
        "selected_model": remediation_dir / "selected_model.json",
        "selected_coefficients": remediation_dir / "selected_coefficients.csv",
        "frozen_predictions": remediation_dir / "frozen_predictions.csv",
        "oot_comparison": remediation_dir / "oot_comparison.csv",
        "governance_decision": remediation_dir / "governance_decision.csv",
        "incumbent_predictions": incumbent_dir / "backtest_predictions.csv",
        "initial_findings": validation_dir / "validation_findings.csv",
    }
    frames = {
        name: pd.read_csv(path)
        for name, path in inputs.items()
        if path.suffix == ".csv"
    }
    selected_model = json.loads(inputs["selected_model"].read_text(encoding="utf-8"))
    result = validate_macro_remediation(
        frames["candidate_register"],
        frames["candidate_tuning"],
        selected_model,
        frames["selected_coefficients"],
        frames["frozen_predictions"],
        frames["oot_comparison"],
        frames["governance_decision"],
        frames["incumbent_predictions"],
        frames["initial_findings"],
    )
    input_audit = pd.DataFrame(
        [
            {
                "artifact": name,
                "file_name": path.name,
                "row_count": 1 if path.suffix == ".json" else len(frames[name]),
                "sha256": _sha256(path),
            }
            for name, path in inputs.items()
        ]
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = _write_reports(result, input_audit, output_path)
    return MacroRemediationValidationOutput(
        result=result,
        input_audit=input_audit,
        report_paths=report_paths,
    )


def _write_reports(
    result: MacroRemediationValidationResult,
    input_audit: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    frames = {
        "validation_summary.csv": result.validation_summary,
        "selection_reperformance.csv": result.selection_reperformance,
        "replicated_performance.csv": result.replicated_performance,
        "finding_lifecycle.csv": result.finding_lifecycle,
        "input_audit.csv": input_audit,
    }
    report_paths: dict[str, Path] = {}
    for file_name, frame in frames.items():
        path = output_dir / file_name
        frame.to_csv(
            path,
            index=False,
            date_format="%Y-%m-%d",
            float_format="%.17g",
            lineterminator="\n",
        )
        report_paths[file_name] = path
    report_path = output_dir / "macro_remediation_validation_report.md"
    report_path.write_text(
        _markdown_report(result),
        encoding="utf-8",
        newline="\n",
    )
    report_paths[report_path.name] = report_path
    return report_paths


def _markdown_report(result: MacroRemediationValidationResult) -> str:
    selection = result.selection_reperformance.iloc[0]
    performance = result.replicated_performance.set_index("variant")
    incumbent = performance.loc["incumbent_satellite"]
    challenger = performance.loc["selected_remediation"]
    mae_reduction = (
        float(incumbent["model_mae"]) - float(challenger["model_mae"])
    ) / float(incumbent["model_mae"])
    rmse_reduction = (
        float(incumbent["model_rmse"]) - float(challenger["model_rmse"])
    ) / float(incumbent["model_rmse"])
    failed = result.validation_summary.loc[
        result.validation_summary["status"].eq("fail")
    ]
    warnings = result.validation_summary.loc[
        result.validation_summary["status"].eq("warning")
    ]
    lifecycle = result.finding_lifecycle.set_index("finding_id")
    return "\n".join(
        [
            "# Independent Macro Satellite Remediation Validation",
            "",
            f"## Opinion: {result.overall_opinion.upper()}",
            "",
            (
                "The challenger remains restricted to sensitivity evidence and is not "
                "approved for point forecasting or accounting calibration."
            ),
            "",
            "## Selection Reperformance",
            "",
            f"- Developer candidate: `{selection['developer_candidate_id']}`.",
            f"- Independently selected candidate: `{selection['reperformed_candidate_id']}`.",
            f"- Developer and reperformed alpha: {selection['developer_alpha']:.0f}.",
            f"- Maximum selection arithmetic gap: {selection['maximum_arithmetic_gap']:.2e}.",
            f"- Selection reconciled: **{bool(selection['selection_reconciled'])}**.",
            "- The selected row uses validation metrics only; OOT evidence is reused.",
            "",
            "## Independent OOT Reperformance",
            "",
            f"- OOT period: {challenger['period_start']:%Y-%m-%d} to {challenger['period_end']:%Y-%m-%d}.",
            f"- Challenger MAE: {challenger['model_mae']:.6f}.",
            f"- Persistence MAE: {challenger['persistence_mae']:.6f}.",
            (
                "- MAE improvement versus persistence: "
                f"{challenger['mae_improvement_vs_persistence']:.2%}."
            ),
            (
                "- RMSE improvement versus persistence: "
                f"{challenger['rmse_improvement_vs_persistence']:.2%}."
            ),
            f"- MAE reduction versus incumbent: {mae_reduction:.2%}.",
            f"- RMSE reduction versus incumbent: {rmse_reduction:.2%}.",
            "",
            "## Control Results",
            "",
            f"- Passed controls: {int(result.validation_summary['status'].eq('pass').sum())}.",
            f"- Failed controls: {len(failed)}.",
            f"- Warnings: {len(warnings)}.",
            "",
            "## Finding Lifecycle",
            "",
            (
                f"- MSV-001 remains {lifecycle.loc['MSV-001', 'closure_status']}: "
                f"{lifecycle.loc['MSV-001', 'closure_reason']}"
            ),
            (
                f"- MSV-002 is {lifecycle.loc['MSV-002', 'closure_status']}: "
                f"{lifecycle.loc['MSV-002', 'closure_reason']}"
            ),
            (
                f"- MSV-003 remains {lifecycle.loc['MSV-003', 'closure_status']}: "
                f"{lifecycle.loc['MSV-003', 'closure_reason']}"
            ),
            "- No finding is closed by reused OOT evidence.",
            "",
            "## Required Next Evidence",
            "",
            (
                "Collect a genuinely post-selection outcome window under a comparable "
                "target definition, preserve release-date macro vintages, and repeat the "
                "benchmark and coefficient-stability tests before requesting closure."
            ),
            "",
            "Educational portfolio case study; not a production validation approval.",
            "",
        ]
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
