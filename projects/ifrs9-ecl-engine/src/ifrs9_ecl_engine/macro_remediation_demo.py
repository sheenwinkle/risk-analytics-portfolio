from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.macro_data import sha256_file
from ifrs9_ecl_engine.macro_remediation import (
    MacroRemediationResult,
    run_macro_satellite_remediation,
)


@dataclass(frozen=True)
class MacroRemediationPipelineOutput:
    remediation: MacroRemediationResult
    input_audit: pd.DataFrame
    report_paths: dict[str, Path]


def run_macro_remediation_pipeline(
    data_path: str | Path,
    output_dir: str | Path,
) -> MacroRemediationPipelineOutput:
    source_path = Path(data_path)
    data = pd.read_csv(source_path, parse_dates=["quarter"])
    result = run_macro_satellite_remediation(data)
    input_audit = _input_audit(source_path, data)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = _write_reports(result, input_audit, output_path)
    return MacroRemediationPipelineOutput(
        remediation=result,
        input_audit=input_audit,
        report_paths=report_paths,
    )


def _input_audit(source_path: Path, data: pd.DataFrame) -> pd.DataFrame:
    quarters = pd.to_datetime(data["quarter"])
    return pd.DataFrame(
        [
            {
                "source_file": source_path.name,
                "source_sha256": sha256_file(source_path),
                "quarterly_observations": len(data),
                "coverage_start": quarters.min().date(),
                "coverage_end": quarters.max().date(),
                "reporting_basis": str(data["apra_reporting_basis"].iloc[0]),
                "post_aps_220_rows": int((quarters >= "2022-03-31").sum()),
            }
        ]
    )


def _write_reports(
    result: MacroRemediationResult,
    input_audit: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    frames = {
        "candidate_register.csv": result.candidate_register,
        "candidate_tuning.csv": result.tuning,
        "selected_coefficients.csv": result.coefficients,
        "frozen_predictions.csv": result.predictions,
        "performance_summary.csv": result.performance,
        "oot_comparison.csv": result.oot_comparison,
        "governance_decision.csv": result.governance_decision,
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

    selected = result.selection.iloc[0]
    selected_register = result.candidate_register.loc[
        result.candidate_register["candidate_id"].eq(
            selected["selected_candidate_id"]
        )
    ].iloc[0]
    selected_model_path = output_dir / "selected_model.json"
    selected_model_path.write_text(
        json.dumps(
            {
                "alpha_grid": sorted(result.tuning["alpha"].unique().tolist()),
                "candidate_id": str(selected["selected_candidate_id"]),
                "coefficient_constraint": str(
                    selected_register["coefficient_constraint"]
                ),
                "development_end": "2015-12-31",
                "eligible_candidates": int(selected["eligible_candidates"]),
                "features": str(selected_register["features"]).split("|"),
                "forecast_horizon_quarters": int(
                    selected_register["forecast_horizon_quarters"]
                ),
                "intended_use": "sensitivity_only",
                "macro_lag_quarters": int(
                    selected_register["macro_lag_quarters"]
                ),
                "oot_end": "2021-12-31",
                "oot_evidence_freshness": str(
                    selected["oot_evidence_freshness"]
                ),
                "oot_used_for_selection": bool(selected["oot_used_for_selection"]),
                "selected_alpha": float(selected["selected_alpha"]),
                "selection_metric": str(selected["selection_metric"]),
                "selection_window": str(selected["selection_window"]),
                "target_form": str(selected_register["target_form"]),
                "validation_end": "2018-12-31",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_paths[selected_model_path.name] = selected_model_path

    report_path = output_dir / "remediation_report.md"
    report_path.write_text(
        _markdown_report(result),
        encoding="utf-8",
        newline="\n",
    )
    report_paths[report_path.name] = report_path
    return report_paths


def _markdown_report(result: MacroRemediationResult) -> str:
    selected = result.selection.iloc[0]
    validation = result.performance.set_index("split").loc["validation"]
    oot = result.performance.set_index("split").loc["oot"]
    comparison = result.oot_comparison.set_index("variant")
    challenger = comparison.loc["selected_remediation"]
    decision = result.governance_decision.iloc[0]
    active_macro = result.coefficients.loc[
        result.coefficients["feature_role"].eq("macro_stress")
        & result.coefficients["standardized_coefficient"].gt(1e-12)
    ]
    return "\n".join(
        [
            "# Australian Macro Satellite Remediation",
            "",
            "## Developer Decision",
            "",
            "- Recommendation: **RETAIN RESTRICTED USE** (`sensitivity_only`).",
            f"- Reused-OOT retest result: **{decision['retest_result']}**.",
            "- This developer remediation does not close MSV-001.",
            "",
            "## Controlled Selection",
            "",
            (
                f"- Pre-registered candidates: {int(selected['eligible_candidates'])}; "
                f"candidate-alpha evaluations: {int(selected['hyperparameters_evaluated'])}."
            ),
            f"- Selected candidate: `{selected['selected_candidate_id']}`.",
            f"- Selected Ridge alpha: {selected['selected_alpha']:.0f}.",
            f"- Selection period: {selected['selection_window']}.",
            (
                "- OOT was not used for candidate or hyperparameter selection; the "
                "2019Q1-2021Q4 window was revealed only after the specification was frozen."
            ),
            "- Every eligible macro input is lagged to the forecast origin.",
            "",
            "## Validation Selection Evidence",
            "",
            f"- Validation MAE: {validation['model_mae']:.6f}.",
            f"- Validation persistence MAE: {validation['persistence_mae']:.6f}.",
            f"- Composite MAE/RMSE ratio: {selected['selection_score']:.4f}.",
            "",
            "## Reused OOT Evidence",
            "",
            f"- OOT observations: {int(oot['observations'])}.",
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
            (
                "- MAE reduction versus the incumbent satellite: "
                f"{challenger['mae_reduction_vs_incumbent']:.2%}."
            ),
            (
                "- RMSE reduction versus the incumbent satellite: "
                f"{challenger['rmse_reduction_vs_incumbent']:.2%}."
            ),
            f"- Active lagged macro drivers: {len(active_macro)}.",
            "",
            "## Governance Boundary",
            "",
            (
                "The error reductions are historical model-performance deltas, not a "
                "realised loss saving or accounting benefit. The OOT period has already "
                "been observed during remediation, so it is supporting evidence rather "
                "than fresh closure evidence."
            ),
            f"Closure blocker: {decision['closure_blocker']}",
            "",
            "Educational portfolio case study; not a production model-change approval.",
            "",
        ]
    )
