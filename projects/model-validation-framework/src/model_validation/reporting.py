from __future__ import annotations

from pathlib import Path

import pandas as pd

from model_validation.policy import ValidationPolicy

REPORT_TABLES = (
    "input_audit",
    "model_metrics",
    "metric_uncertainty",
    "calibration_by_decile",
    "monthly_performance",
    "vintage_performance",
    "segment_performance",
    "stability_summary",
    "stability_bins",
    "benchmark_comparison",
    "validation_summary",
    "validation_findings",
    "model_limitations",
)


def build_validation_summary(
    *,
    model_metrics: pd.DataFrame,
    stability_summary: pd.DataFrame,
    benchmark_comparison: pd.DataFrame,
    selected_model: str,
    policy: ValidationPolicy,
) -> pd.DataFrame:
    selected = model_metrics[
        model_metrics["model_name"].eq(selected_model)
        & model_metrics["score_version"].eq("recalibrated")
    ].iloc[0]
    challenger_margin = benchmark_comparison.loc[
        benchmark_comparison["comparison"].eq(
            "selected_recalibrated_vs_unselected_raw_challenger"
        ),
        "auc_delta",
    ].iloc[0]
    psi = stability_summary["population_stability_index"].iloc[0]

    rows = [
        {
            "check": "auc",
            "metric_value": float(selected["roc_auc"]),
            "direction": "higher_is_better",
            "green_threshold": policy.auc_green_min,
            "warning_threshold": policy.auc_warning_min,
            "status": policy.status_for_minimum(
                float(selected["roc_auc"]), policy.auc_green_min, policy.auc_warning_min
            ),
            "detail": "Selected recalibrated model discrimination by ROC AUC.",
        },
        {
            "check": "ks",
            "metric_value": float(selected["ks"]),
            "direction": "higher_is_better",
            "green_threshold": policy.ks_green_min,
            "warning_threshold": policy.ks_warning_min,
            "status": policy.status_for_minimum(
                float(selected["ks"]), policy.ks_green_min, policy.ks_warning_min
            ),
            "detail": "Selected recalibrated model separation by KS statistic.",
        },
        {
            "check": "absolute_calibration_gap",
            "metric_value": float(selected["absolute_calibration_gap"]),
            "direction": "lower_is_better",
            "green_threshold": policy.absolute_calibration_gap_green_max,
            "warning_threshold": policy.absolute_calibration_gap_warning_max,
            "status": policy.status_for_maximum(
                float(selected["absolute_calibration_gap"]),
                policy.absolute_calibration_gap_green_max,
                policy.absolute_calibration_gap_warning_max,
            ),
            "detail": "Absolute gap between observed default rate and mean recalibrated PD.",
        },
        {
            "check": "population_stability_index",
            "metric_value": float(psi),
            "direction": "lower_is_better",
            "green_threshold": policy.psi_green_max,
            "warning_threshold": policy.psi_warning_max,
            "status": policy.status_for_maximum(
                float(psi), policy.psi_green_max, policy.psi_warning_max
            ),
            "detail": "PSI comparing current score distribution with the reference period.",
        },
        {
            "check": "challenger_auc_margin",
            "metric_value": float(challenger_margin),
            "direction": "lower_is_better",
            "green_threshold": policy.challenger_auc_margin_green_max,
            "warning_threshold": policy.challenger_auc_margin_warning_max,
            "status": policy.status_for_maximum(
                float(challenger_margin),
                policy.challenger_auc_margin_green_max,
                policy.challenger_auc_margin_warning_max,
            ),
            "detail": "Unselected raw challenger AUC minus selected recalibrated incumbent AUC.",
        },
    ]
    return pd.DataFrame(rows)


def build_validation_findings(validation_summary: pd.DataFrame) -> pd.DataFrame:
    labels = {
        "auc": "ROC-AUC",
        "ks": "KS statistic",
        "absolute_calibration_gap": "Absolute calibration gap",
        "population_stability_index": "Population Stability Index",
        "challenger_auc_margin": "Challenger AUC margin",
    }
    actions = {
        "auc": "Review rank ordering, reject-inference assumptions, and candidate segmentation.",
        "ks": "Inspect score distribution overlap and consider model redevelopment triggers.",
        "absolute_calibration_gap": "Re-estimate calibration on a fresh holdout and review portfolio mix shift.",
        "population_stability_index": "Drill into shifted score bands and compare application mix drivers.",
        "challenger_auc_margin": "Run challenger governance review before retaining the incumbent score.",
    }
    rows = []
    for _, check in validation_summary.iterrows():
        if check["status"] == "pass":
            continue
        rows.append(
            {
                "status": check["status"],
                "check": check["check"],
                "finding": (
                    f"{labels[check['check']]} reached {check['status']} status at "
                    f"{_format_float(check['metric_value'])}."
                ),
                "recommended_action": actions[check["check"]],
            }
        )
    return pd.DataFrame(rows, columns=["status", "check", "finding", "recommended_action"])


def build_model_limitations(
    *,
    data_context: str = "synthetic",
    observation_start: object | None = None,
    observation_end: object | None = None,
) -> pd.DataFrame:
    if data_context == "synthetic":
        context_limitations = [
            {
                "limitation": "synthetic_data",
                "severity": "medium",
                "description": "Inputs are synthetic and cannot prove live portfolio performance.",
                "mitigation": (
                    "Validate on locally downloaded public LendingClub data before production use."
                ),
            }
        ]
    elif data_context == "public_lendingclub":
        context_limitations = [
            {
                "limitation": "accepted_loan_selection_bias",
                "severity": "medium",
                "description": (
                    "Public LendingClub data contains accepted loans rather than all applications."
                ),
                "mitigation": (
                    "Do not generalise approval-strategy results to the full applicant population."
                ),
            }
        ]
    else:
        raise ValueError(f"Unsupported data_context: {data_context}")

    horizon_description = "Out-of-time validation horizon is limited."
    if observation_start is not None and observation_end is not None:
        start = pd.Timestamp(observation_start).date().isoformat()
        end = pd.Timestamp(observation_end).date().isoformat()
        horizon_description = f"Out-of-time validation covers {start} to {end}."

    return pd.DataFrame(
        [
            *context_limitations,
            {
                "limitation": "terminal_outcome_proxy",
                "severity": "medium",
                "description": "Observed defaults use a terminal-outcome proxy rather than serviced account history.",
                "mitigation": "Replace with contractual default definitions and observation windows.",
            },
            {
                "limitation": "limited_oot_horizon",
                "severity": "medium",
                "description": horizon_description,
                "mitigation": "Extend monitoring across additional vintages when data is available.",
            },
            {
                "limitation": "limited_feature_replication",
                "severity": "medium",
                "description": (
                    "Independent validation consumes frozen scores, outcomes, and two "
                    "business segmentation fields rather than the full development feature set."
                ),
                "mitigation": "Add feature-level replication and challenger rebuild testing in a later slice.",
            },
        ]
    )


def write_validation_reports(result: object, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_paths: dict[str, str] = {}
    for table_name in REPORT_TABLES:
        filename = f"{table_name}.csv"
        path = output_dir / filename
        table = getattr(result, table_name)
        table.to_csv(path, index=False, float_format="%.6f", lineterminator="\n")
        report_paths[filename] = str(path)

    report_path = output_dir / "validation_report.md"
    report_path.write_text(build_markdown_report(result), encoding="utf-8", newline="\n")
    report_paths["validation_report.md"] = str(report_path)
    return report_paths


def build_markdown_report(result: object) -> str:
    selected = result.model_metrics[
        result.model_metrics["score_version"].eq("recalibrated")
    ].iloc[0]
    stability = result.stability_summary.iloc[0]
    overall_outcome = _overall_policy_outcome(result.validation_summary)
    summary_lines = [
        "# PD Model Validation Case Study",
        "",
        "## Scope and Disclaimer",
        "",
        (
            "Educational portfolio case study. This report is not a regulatory approval, "
            "accounting opinion, or production-use decision."
        ),
        "",
        "## Executive Summary",
        "",
        (
            f"- Selected model: {selected['model_name']} "
            f"({selected['score_version']} score `{selected['score_column']}`)."
        ),
        f"- Observations: {int(selected['observations'])}. Defaults: {int(selected['defaults'])}.",
        (
            f"- Mean predicted PD: {_format_float(selected['mean_predicted_pd'])}. "
            f"Observed default rate: {_format_float(selected['observed_default_rate'])}."
        ),
        f"- AUC: {_format_float(selected['roc_auc'])}. KS: {_format_float(selected['ks'])}.",
        (
            "- Absolute calibration gap: "
            f"{_format_float(selected['absolute_calibration_gap'])}."
        ),
        (
            "- PSI period split: "
            f"{stability['reference_start']} to {stability['reference_end']} versus "
            f"{stability['current_start']} to {stability['current_end']}."
        ),
        f"- PSI: {_format_float(stability['population_stability_index'])}.",
        f"- Overall policy outcome: **{overall_outcome.upper()}**.",
        "",
        "## Methodology",
        "",
        "- Reperformed AUC, Gini, tie-safe KS, Brier score, and portfolio calibration.",
        "- Quantified uncertainty with DeLong, Wilson score, normal-mean, and paired intervals.",
        "- Reviewed rank-based calibration deciles and monthly performance.",
        "- Backtested calibration and discrimination by origination quarter and business segment.",
        "- Measured score drift with reference-period quantile midpoint PSI bins.",
        "- Compared the selected recalibrated incumbent with the unselected raw challenger.",
        "",
        "## Policy Checks",
        "",
        _markdown_table(result.validation_summary),
        "",
        "## Calibration by Decile",
        "",
        _markdown_table(result.calibration_by_decile),
        "",
        "## Metric Uncertainty",
        "",
        _markdown_table(result.metric_uncertainty),
        "",
        "## Vintage Performance",
        "",
        _markdown_table(result.vintage_performance),
        "",
        "## Segment Performance",
        "",
        _markdown_table(result.segment_performance),
        "",
        "## Stability Summary",
        "",
        _markdown_table(result.stability_summary),
        "",
        "## Benchmark Comparison",
        "",
        _markdown_table(result.benchmark_comparison),
        "",
        "## Findings",
        "",
        _markdown_table(result.validation_findings)
        if not result.validation_findings.empty
        else "No warning or fail findings were raised under the configured policy.",
        "",
        "## Limitations",
        "",
        _markdown_table(result.model_limitations),
        "",
    ]
    return "\n".join(summary_lines)


def _overall_policy_outcome(validation_summary: pd.DataFrame) -> str:
    statuses = set(validation_summary["status"].astype(str))
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    header = "| " + " | ".join(frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(frame.columns)) + " |"
    rows = []
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(_markdown_value(row[column]) for column in frame.columns) + " |")
    return "\n".join([header, separator, *rows])


def _markdown_value(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    if isinstance(value, float):
        return _format_float(value)
    return str(value)


def _format_float(value: object) -> str:
    return f"{float(value):.6f}"
