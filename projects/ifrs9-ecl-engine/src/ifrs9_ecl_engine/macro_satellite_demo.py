from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.demo import build_demo_inputs
from ifrs9_ecl_engine.engine import ECLResult, run_ecl_engine
from ifrs9_ecl_engine.macro_data import sha256_file
from ifrs9_ecl_engine.macro_satellite import MacroSatelliteResult, run_macro_satellite


@dataclass(frozen=True)
class MacroSatellitePipelineOutput:
    satellite: MacroSatelliteResult
    incumbent_ecl: ECLResult
    challenger_ecl: ECLResult
    ecl_comparison: pd.DataFrame
    ecl_scenario_comparison: pd.DataFrame
    report_paths: dict[str, Path]


def run_macro_satellite_pipeline(
    data_path: str | Path,
    output_dir: str | Path,
) -> MacroSatellitePipelineOutput:
    source_path = Path(data_path)
    data = pd.read_csv(source_path)
    satellite = run_macro_satellite(data)
    challenger_multipliers = {
        str(row["scenario"]): float(row["npl_multiplier"])
        for row in satellite.scenario_response.to_dict("records")
    }

    incumbent_inputs = build_demo_inputs()
    challenger_inputs = build_demo_inputs(challenger_multipliers)
    incumbent = run_ecl_engine(*incumbent_inputs)
    challenger = run_ecl_engine(*challenger_inputs)
    ecl_comparison = _compare_ecl(incumbent, challenger)
    scenario_comparison = _compare_scenario_ecl(incumbent, challenger)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = _write_reports(
        satellite=satellite,
        incumbent=incumbent,
        challenger=challenger,
        ecl_comparison=ecl_comparison,
        scenario_comparison=scenario_comparison,
        source_path=source_path,
        source_data=data,
        output_dir=output_path,
    )
    return MacroSatellitePipelineOutput(
        satellite=satellite,
        incumbent_ecl=incumbent,
        challenger_ecl=challenger,
        ecl_comparison=ecl_comparison,
        ecl_scenario_comparison=scenario_comparison,
        report_paths=report_paths,
    )


def _compare_ecl(incumbent: ECLResult, challenger: ECLResult) -> pd.DataFrame:
    incumbent_rows = incumbent.portfolio_summary.set_index(
        incumbent.portfolio_summary["stage"].astype(str)
    )
    rows = []
    for variant, result, evidence_basis in [
        (
            "incumbent_manual",
            incumbent,
            "Illustrative fixed PD multipliers: base 1.00, upside 0.75, downside 1.65",
        ),
        (
            "challenger_empirical",
            challenger,
            "APRA/RBA constrained macro satellite NPL response",
        ),
    ]:
        for result_row in result.portfolio_summary.to_dict("records"):
            stage = str(result_row["stage"])
            incumbent_ecl = float(incumbent_rows.loc[stage, "weighted_ecl"])
            modelled_ecl = float(result_row["weighted_ecl"])
            change = modelled_ecl - incumbent_ecl
            rows.append(
                {
                    "variant": variant,
                    "evidence_basis": evidence_basis,
                    "stage": stage,
                    "gross_exposure": float(result_row["gross_exposure"]),
                    "modelled_ecl": modelled_ecl,
                    "coverage_ratio": float(result_row["coverage_ratio"]),
                    "change_vs_incumbent": change,
                    "change_pct_vs_incumbent": (
                        change / incumbent_ecl if incumbent_ecl else 0.0
                    ),
                }
            )
    return pd.DataFrame(rows)


def _compare_scenario_ecl(incumbent: ECLResult, challenger: ECLResult) -> pd.DataFrame:
    rows = []
    for variant, result in [
        ("incumbent_manual", incumbent),
        ("challenger_empirical", challenger),
    ]:
        summary = (
            result.scenario_ecl.groupby("scenario", as_index=False)
            .agg(
                scenario_weight=("scenario_weight", "first"),
                scenario_ecl=("scenario_ecl", "sum"),
                weighted_scenario_ecl=("weighted_scenario_ecl", "sum"),
            )
            .sort_values("scenario")
        )
        summary.insert(0, "variant", variant)
        rows.extend(summary.to_dict("records"))
    return pd.DataFrame(rows)


def _write_reports(
    *,
    satellite: MacroSatelliteResult,
    incumbent: ECLResult,
    challenger: ECLResult,
    ecl_comparison: pd.DataFrame,
    scenario_comparison: pd.DataFrame,
    source_path: Path,
    source_data: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    csv_outputs = {
        "model_tuning": (output_dir / "model_tuning.csv", satellite.tuning),
        "model_coefficients": (
            output_dir / "model_coefficients.csv",
            satellite.coefficients,
        ),
        "backtest_predictions": (
            output_dir / "backtest_predictions.csv",
            satellite.predictions,
        ),
        "backtest_performance": (
            output_dir / "backtest_performance.csv",
            satellite.performance,
        ),
        "scenario_pd_multipliers": (
            output_dir / "scenario_pd_multipliers.csv",
            satellite.scenario_response,
        ),
        "ecl_ab_comparison": (output_dir / "ecl_ab_comparison.csv", ecl_comparison),
        "ecl_scenario_comparison": (
            output_dir / "ecl_scenario_comparison.csv",
            scenario_comparison,
        ),
    }
    for path, frame in csv_outputs.values():
        frame.to_csv(
            path,
            index=False,
            date_format="%Y-%m-%d",
            float_format="%.10f",
            lineterminator="\n",
        )

    audit = pd.DataFrame(
        [
            {
                "source_file": source_path.name,
                "source_sha256": sha256_file(source_path),
                "quarterly_observations": len(source_data),
                "coverage_start": str(source_data["quarter"].iloc[0]),
                "coverage_end": str(source_data["quarter"].iloc[-1]),
                "reporting_basis": source_data["apra_reporting_basis"].iloc[0],
                "post_aps_220_rows": int(
                    (pd.to_datetime(source_data["quarter"]) >= "2022-03-31").sum()
                ),
            }
        ]
    )
    audit_path = output_dir / "data_audit.csv"
    audit.to_csv(audit_path, index=False, lineterminator="\n")

    specification_path = output_dir / "model_specification.json"
    specification_path.write_text(
        json.dumps(
            {
                "alpha_grid": satellite.tuning["alpha"].tolist(),
                "benchmark": "previous-quarter NPL proxy ratio",
                "constraint": "all standardized coefficients nonnegative",
                "development_end": "2015-12-31",
                "features": [
                    "lagged logit NPL proxy ratio",
                    "contemporaneous unemployment rate",
                    "negative contemporaneous year-ended real GDP growth",
                ],
                "intended_use": "sensitivity challenger only",
                "macro_data_vintage": (
                    "2026 source snapshot with revised historical observations; "
                    "real-time release vintages not reconstructed"
                ),
                "oot_end": "2021-12-31",
                "selected_alpha": satellite.selected_alpha,
                "target": (
                    "logit of APRA impaired-plus-past-due facilities divided by "
                    "gross loans and advances"
                ),
                "validation_end": "2018-12-31",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    report_path = output_dir / "macro_satellite_report.md"
    report_path.write_text(
        _markdown_report(satellite, incumbent, challenger, ecl_comparison),
        encoding="utf-8",
        newline="\n",
    )
    return {
        **{name: path for name, (path, _) in csv_outputs.items()},
        "data_audit": audit_path,
        "model_specification": specification_path,
        "macro_satellite_report": report_path,
    }


def _markdown_report(
    satellite: MacroSatelliteResult,
    incumbent: ECLResult,
    challenger: ECLResult,
    ecl_comparison: pd.DataFrame,
) -> str:
    oot = satellite.performance.set_index("split").loc["oot"]
    total = ecl_comparison[ecl_comparison["stage"] == "Total"].set_index("variant")
    incumbent_total = total.loc["incumbent_manual"]
    challenger_total = total.loc["challenger_empirical"]
    downside = satellite.scenario_response.set_index("scenario").loc["downside"]
    unemployment = satellite.coefficients.set_index("feature").loc[
        "unemployment_rate_pct"
    ]
    return "\n".join(
        [
            "# Australian Macro Satellite and ECL Challenger Report",
            "",
            (
                "A frozen, directionally constrained model maps public Australian macro "
                "conditions to an aggregate bank NPL proxy."
            ),
            "",
            "## Data and Design",
            "",
            "- Target: APRA impaired plus past-due facilities divided by gross loans.",
            "- Macro drivers: ABS unemployment and real GDP series distributed by the RBA.",
            "- Development ends 2015 Q4, tuning ends 2018 Q4, and OOT ends 2021 Q4.",
            "- The APS 220 definition change from 2022 Q1 is excluded rather than spliced.",
            (
                "- The 2026 macro snapshot contains revised historical observations; "
                "release-date vintages are not reconstructed."
            ),
            "- Coefficients are constrained nonnegative after GDP is expressed as a stress factor.",
            "",
            "## Frozen Backtest",
            "",
            f"- OOT observations: {int(oot['observations'])}",
            f"- Satellite MAE: {oot['model_mae']:.6f}",
            f"- Persistence MAE: {oot['persistence_mae']:.6f}",
            (
                "- MAE improvement versus persistence: "
                f"{oot['mae_improvement_vs_persistence']:.1%}"
            ),
            (
                "- Unemployment coefficient: "
                f"{unemployment['standardized_coefficient']:.6f} "
                "(the constrained fit did not retain incremental level sensitivity)"
            ),
            "",
            "## Scenario Translation",
            "",
            (
                "- Downside shock: unemployment +3.0pp and real GDP growth -6.0pp; "
                f"estimated NPL multiplier {downside['npl_multiplier']:.3f}."
            ),
            "- Scenario multipliers are diagnostic proxies, not accounting-approved PD calibrations.",
            "",
            "## A/B ECL Impact",
            "",
            (
                "- Incumbent manual-multiplier ECL: "
                f"{incumbent_total['modelled_ecl']:,.2f}"
            ),
            (
                "- Empirical challenger ECL: "
                f"{challenger_total['modelled_ecl']:,.2f}"
            ),
            (
                "- Challenger change: "
                f"{challenger_total['change_vs_incumbent']:,.2f} "
                f"({challenger_total['change_pct_vs_incumbent']:.1%})"
            ),
            "- The A/B comparison changes only scenario PD multipliers; accounts, LGD, EAD, and weights are held fixed.",
            "",
            "## Use Restriction",
            "",
            (
                "The challenger is not approved for point forecasting because it does not "
                "beat the persistence benchmark on the frozen OOT period. It may be used only "
                "as transparent sensitivity evidence pending remediation and revalidation."
            ),
            "",
            "## Reconciliation",
            "",
            f"- Incumbent engine total: {_total_ecl(incumbent):,.2f}",
            f"- Challenger engine total: {_total_ecl(challenger):,.2f}",
            "",
        ]
    )


def _total_ecl(result: ECLResult) -> float:
    total = result.portfolio_summary[
        result.portfolio_summary["stage"].astype(str) == "Total"
    ]
    if len(total) != 1:
        raise ValueError("ECL result must contain exactly one Total row")
    return float(total.iloc[0]["weighted_ecl"])
