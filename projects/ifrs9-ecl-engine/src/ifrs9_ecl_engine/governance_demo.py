from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.demo import build_demo_inputs
from ifrs9_ecl_engine.engine import run_ecl_engine
from ifrs9_ecl_engine.governance import (
    MacroOverlayAnalysisResult,
    MacroSensitivityCase,
    ManagementOverlay,
    run_macro_overlay_analysis,
)


@dataclass(frozen=True)
class MacroOverlayPipelineOutput:
    analysis: MacroOverlayAnalysisResult
    report_paths: dict[str, Path]


def build_demo_governance_inputs(
    scenario_pd_multipliers: Mapping[str, float] | None = None,
) -> tuple[tuple[MacroSensitivityCase, ...], tuple[ManagementOverlay, ...]]:
    multipliers = _validate_satellite_multipliers(
        scenario_pd_multipliers
        if scenario_pd_multipliers is not None
        else {"upside": 0.95, "base": 1.0, "downside": 1.10}
    )
    downside_multiplier = multipliers["downside"]
    cases = (
        MacroSensitivityCase(
            case_id="baseline",
            description="Modelled 60% base, 15% upside, and 25% downside weights",
            scenario_weights={"base": 0.60, "upside": 0.15, "downside": 0.25},
            is_baseline=True,
        ),
        MacroSensitivityCase(
            case_id="downside_weight_plus_10pp",
            description="Shift 10 percentage points from base to downside",
            scenario_weights={"base": 0.50, "upside": 0.15, "downside": 0.35},
        ),
        MacroSensitivityCase(
            case_id="empirical_downside_severity",
            description=(
                "Apply the APRA/RBA satellite downside NPL multiplier "
                f"of {downside_multiplier:.3f} as a sensitivity proxy"
            ),
            scenario_weights={"base": 0.60, "upside": 0.15, "downside": 0.25},
            scenario_ecl_multipliers={"downside": downside_multiplier},
        ),
        MacroSensitivityCase(
            case_id="combined_empirical_downside",
            description="Combine the downside weight shift and APRA/RBA severity proxy",
            scenario_weights={"base": 0.50, "upside": 0.15, "downside": 0.35},
            scenario_ecl_multipliers={"downside": downside_multiplier},
        ),
    )
    overlays = (
        ManagementOverlay(
            overlay_id="OVL-001",
            risk_driver="post_cutoff_servicing_cost_pressure",
            scope="stage_2_portfolio",
            trigger_metric="synthetic_exposed_share",
            trigger_operator="greater_than_or_equal",
            observed_value=0.22,
            trigger_threshold=0.15,
            requested_amount=4_000.0,
            cap_ratio_of_modelled_ecl=0.08,
            overlap_assessment="distinct",
            modelled_risk_reference=(
                "Post-cutoff risk is absent from the frozen scenario term structures"
            ),
            approval_status="approved",
            approved_by="Synthetic ECL Committee",
            rationale="Illustrate a capped overlay for a triggered risk outside the model",
        ),
        ManagementOverlay(
            overlay_id="OVL-002",
            risk_driver="broad_macro_deterioration",
            scope="portfolio",
            trigger_metric="downside_scenario_weight",
            trigger_operator="greater_than_or_equal",
            observed_value=0.25,
            trigger_threshold=0.20,
            requested_amount=5_000.0,
            cap_ratio_of_modelled_ecl=0.10,
            overlap_assessment="captured_by_model",
            modelled_risk_reference=(
                "Captured by downside_weight_plus_10pp and "
                "combined_empirical_downside sensitivities"
            ),
            approval_status="approved",
            approved_by="Synthetic ECL Committee",
            rationale="Demonstrate the double-counting control for modelled macro risk",
        ),
        ManagementOverlay(
            overlay_id="OVL-003",
            risk_driver="emerging_industry_concentration",
            scope="stage_1_portfolio",
            trigger_metric="synthetic_concentration_share",
            trigger_operator="greater_than_or_equal",
            observed_value=0.18,
            trigger_threshold=0.15,
            requested_amount=1_500.0,
            cap_ratio_of_modelled_ecl=0.05,
            overlap_assessment="distinct",
            modelled_risk_reference="Not represented by a sector-specific model factor",
            approval_status="pending",
            approved_by=None,
            rationale="Demonstrate that a triggered but unapproved overlay is not recognized",
        ),
    )
    return cases, overlays


def run_macro_overlay_pipeline(
    output_dir: str | Path = "reports/macro_overlay",
    scenario_multiplier_path: str | Path | None = None,
) -> MacroOverlayPipelineOutput:
    accounts, term_structures, scenario_weights = build_demo_inputs()
    ecl_result = run_ecl_engine(accounts, term_structures, scenario_weights)
    multiplier_path = (
        Path(scenario_multiplier_path)
        if scenario_multiplier_path is not None
        else Path(__file__).resolve().parents[2]
        / "reports"
        / "macro_satellite"
        / "scenario_pd_multipliers.csv"
    )
    satellite_multipliers = _read_satellite_multipliers(multiplier_path)
    cases, overlays = build_demo_governance_inputs(satellite_multipliers)
    analysis = run_macro_overlay_analysis(ecl_result, cases, overlays)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = write_macro_overlay_reports(analysis, output_path)
    return MacroOverlayPipelineOutput(analysis=analysis, report_paths=report_paths)


def write_macro_overlay_reports(
    analysis: MacroOverlayAnalysisResult,
    output_dir: Path,
) -> dict[str, Path]:
    outputs = {
        "macro_sensitivity_summary": output_dir / "macro_sensitivity_summary.csv",
        "macro_sensitivity_detail": output_dir / "macro_sensitivity_detail.csv",
        "management_overlay_register": output_dir / "management_overlay_register.csv",
        "ecl_reconciliation": output_dir / "ecl_reconciliation.csv",
    }
    frames = {
        "macro_sensitivity_summary": analysis.macro_summary,
        "macro_sensitivity_detail": analysis.macro_detail,
        "management_overlay_register": analysis.overlay_register,
        "ecl_reconciliation": analysis.reconciliation,
    }
    for name, frame in frames.items():
        frame.to_csv(
            outputs[name],
            index=False,
            float_format="%.6f",
            lineterminator="\n",
        )
    report_path = output_dir / "macro_overlay_report.md"
    report_path.write_text(
        _markdown_report(analysis),
        encoding="utf-8",
        newline="\n",
    )
    return {**outputs, "macro_overlay_report": report_path}


def _markdown_report(analysis: MacroOverlayAnalysisResult) -> str:
    reconciliation = analysis.reconciliation.iloc[0]
    recognized = analysis.overlay_register[
        analysis.overlay_register["recognized_amount"] > 0
    ]
    blocked = analysis.overlay_register[
        analysis.overlay_register["recognized_amount"] == 0
    ]
    return "\n".join(
        [
            "# ECL Macro Sensitivity and Management Overlay Report",
            "",
            (
                "Deterministic synthetic governance evidence generated by "
                "`scripts/run_macro_overlay.py`. Sensitivities are not booked adjustments."
            ),
            "",
            "## ECL Reconciliation",
            "",
            f"- Baseline modelled ECL: {reconciliation['baseline_modelled_ecl']:,.2f}",
            (
                "- Highest sensitivity: "
                f"{reconciliation['highest_sensitivity_case_id']} at "
                f"{reconciliation['highest_sensitivity_ecl']:,.2f} "
                "(not booked)"
            ),
            (
                "- Recognized management overlay: "
                f"{reconciliation['recognized_management_overlay']:,.2f}"
            ),
            (
                "- Illustrative reported ECL: "
                f"{reconciliation['illustrative_reported_ecl']:,.2f}"
            ),
            "",
            "## Macro Sensitivity",
            "",
            _format_markdown_table(analysis.macro_summary),
            "",
            "## Overlay Control Outcomes",
            "",
            f"- Recognized requests: {len(recognized)}",
            f"- Disclosed but unrecognized requests: {len(blocked)}",
            "- Booking requires a met trigger, distinct risk, completed approval, and cap.",
            "",
            _format_markdown_table(
                analysis.overlay_register[
                    [
                        "overlay_id",
                        "risk_driver",
                        "trigger_met",
                        "double_counting_check",
                        "approval_status",
                        "recognition_status",
                        "requested_amount",
                        "recognized_amount",
                    ]
                ]
            ),
            "",
            "## Caveat",
            "",
            "This is a synthetic governance demonstration, not an accounting conclusion.",
            (
                "The severity proxy comes from the restricted APRA/RBA macro satellite; "
                "scenario weights and overlay evidence remain illustrative and unapproved."
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


def _read_satellite_multipliers(path: Path) -> dict[str, float]:
    if not path.is_file():
        raise FileNotFoundError(f"Satellite multiplier report not found: {path}")
    frame = pd.read_csv(path)
    required = {"scenario", "npl_multiplier", "evidence_use"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            "Satellite multiplier report missing columns: " + ", ".join(sorted(missing))
        )
    if set(frame["evidence_use"]) != {"sensitivity_only"}:
        raise ValueError("Satellite multiplier report must be restricted to sensitivity_only")
    if len(frame) != 3 or frame["scenario"].duplicated().any():
        raise ValueError(
            "Satellite multiplier report must contain each scenario exactly once"
        )
    return _validate_satellite_multipliers(
        dict(zip(frame["scenario"], frame["npl_multiplier"], strict=True))
    )


def _validate_satellite_multipliers(values: Mapping[str, float]) -> dict[str, float]:
    if set(values) != {"upside", "base", "downside"}:
        raise ValueError("Satellite multipliers must cover upside, base, and downside")
    normalized = {scenario: float(value) for scenario, value in values.items()}
    if any(not math.isfinite(value) or value <= 0 for value in normalized.values()):
        raise ValueError("Satellite multipliers must be finite and positive")
    if not math.isclose(normalized["base"], 1.0, abs_tol=1e-8):
        raise ValueError("Satellite base multiplier must equal 1")
    if not normalized["upside"] < normalized["base"] < normalized["downside"]:
        raise ValueError("Satellite multipliers must increase from upside to downside")
    return normalized
