from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from model_validation.macro_satellite import (
    MacroSatelliteValidationResult,
    validate_macro_satellite,
)


@dataclass(frozen=True)
class MacroSatelliteValidationOutput:
    result: MacroSatelliteValidationResult
    input_audit: pd.DataFrame
    report_paths: dict[str, Path]


def run_macro_satellite_validation(
    developer_report_dir: str | Path,
    output_dir: str | Path,
) -> MacroSatelliteValidationOutput:
    source_dir = Path(developer_report_dir)
    inputs = {
        "predictions": source_dir / "backtest_predictions.csv",
        "coefficients": source_dir / "model_coefficients.csv",
        "tuning": source_dir / "model_tuning.csv",
        "scenarios": source_dir / "scenario_pd_multipliers.csv",
        "developer_performance": source_dir / "backtest_performance.csv",
    }
    frames = {name: pd.read_csv(path) for name, path in inputs.items()}
    result = validate_macro_satellite(
        frames["predictions"],
        frames["coefficients"],
        frames["tuning"],
        frames["scenarios"],
        frames["developer_performance"],
    )
    input_audit = pd.DataFrame(
        [
            {
                "artifact": name,
                "file_name": path.name,
                "row_count": len(frames[name]),
                "sha256": _sha256(path),
            }
            for name, path in inputs.items()
        ]
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = _write_reports(result, input_audit, output_path)
    return MacroSatelliteValidationOutput(
        result=result,
        input_audit=input_audit,
        report_paths=report_paths,
    )


def _write_reports(
    result: MacroSatelliteValidationResult,
    input_audit: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    outputs = {
        "validation_summary": output_dir / "validation_summary.csv",
        "validation_findings": output_dir / "validation_findings.csv",
        "replicated_performance": output_dir / "replicated_performance.csv",
        "input_audit": output_dir / "input_audit.csv",
    }
    frames = {
        "validation_summary": result.validation_summary,
        "validation_findings": result.findings,
        "replicated_performance": result.replicated_performance,
        "input_audit": input_audit,
    }
    for name, frame in frames.items():
        frame.to_csv(
            outputs[name],
            index=False,
            date_format="%Y-%m-%d",
            float_format="%.10f",
            lineterminator="\n",
        )
    report_path = output_dir / "macro_validation_report.md"
    report_path.write_text(
        _markdown_report(result),
        encoding="utf-8",
        newline="\n",
    )
    return {**outputs, "macro_validation_report": report_path}


def _markdown_report(result: MacroSatelliteValidationResult) -> str:
    performance = result.replicated_performance.iloc[0]
    failed = result.validation_summary[result.validation_summary["status"] == "fail"]
    warnings = result.validation_summary[result.validation_summary["status"] == "warning"]
    return "\n".join(
        [
            "# Independent Australian Macro Satellite Validation",
            "",
            f"## Opinion: {result.overall_opinion.upper()}",
            "",
            (
                "The satellite is restricted to sensitivity evidence and is not approved "
                "for point forecasting or accounting calibration."
            ),
            "",
            "## Independent Backtest",
            "",
            f"- OOT period: {performance['period_start']:%Y-%m-%d} to {performance['period_end']:%Y-%m-%d}",
            f"- Observations: {int(performance['observations'])}",
            f"- Satellite MAE: {performance['model_mae']:.6f}",
            f"- Persistence MAE: {performance['persistence_mae']:.6f}",
            (
                "- MAE improvement versus persistence: "
                f"{performance['mae_improvement_vs_persistence']:.1%}"
            ),
            (
                "- RMSE improvement versus persistence: "
                f"{performance['rmse_improvement_vs_persistence']:.1%}"
            ),
            "",
            "## Control Results",
            "",
            f"- Failed checks: {len(failed)}",
            f"- Warning checks: {len(warnings)}",
            f"- Open findings: {len(result.findings)}",
            "",
            _markdown_table(
                result.validation_summary[
                    ["check", "metric_value", "threshold", "direction", "status"]
                ]
            ),
            "",
            "## Findings",
            "",
            _markdown_table(result.findings),
            "",
            "## Required Decision",
            "",
            (
                "Retain the incumbent for the educational ECL baseline. Use the empirical "
                "challenger only to quantify sensitivity until alternative specifications "
                "pass a new frozen OOT benchmark comparison."
            ),
            "",
        ]
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    rows = ["| " + " | ".join(headers) + " |"]
    rows.append("| " + " | ".join("---" for _ in headers) + " |")
    for record in frame.to_dict("records"):
        rows.append(
            "| "
            + " | ".join(_format_cell(record[column]) for column in headers)
            + " |"
        )
    return "\n".join(rows)


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
