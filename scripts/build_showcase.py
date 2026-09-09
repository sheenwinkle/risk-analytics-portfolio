from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter

REPO_ROOT = Path(__file__).resolve().parents[1]
TEXT = "#1f2937"
MUTED = "#64748b"
GRID = "#dbe3ea"
TEAL = "#0f766e"
AMBER = "#b45309"
RED = "#b91c1c"
BLUE = "#2563eb"
LIGHT = "#f8fafc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build static portfolio showcase charts.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "assets",
        help="Directory for generated PNG charts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _configure_style()

    calibration_path = (
        REPO_ROOT
        / "projects"
        / "credit-risk-pd-model"
        / "reports"
        / "public_lendingclub"
        / "calibration_table.csv"
    )
    ecl_path = (
        REPO_ROOT / "projects" / "ifrs9-ecl-engine" / "reports" / "portfolio_summary.csv"
    )
    ecl_macro_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "macro_overlay"
        / "macro_sensitivity_summary.csv"
    )
    ecl_reconciliation_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "macro_overlay"
        / "ecl_reconciliation.csv"
    )
    macro_satellite_predictions_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "macro_satellite"
        / "backtest_predictions.csv"
    )
    macro_satellite_ecl_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "macro_satellite"
        / "ecl_ab_comparison.csv"
    )
    macro_remediation_predictions_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "macro_remediation"
        / "frozen_predictions.csv"
    )
    macro_remediation_comparison_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "macro_remediation"
        / "oot_comparison.csv"
    )
    sicr_reconciliation_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "sicr_rebuttal"
        / "ecl_impact_reconciliation.csv"
    )
    ecl_cashflow_summary_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "cashflow_sensitivity"
        / "cashflow_sensitivity_summary.csv"
    )
    ecl_cashflow_monthly_path = (
        REPO_ROOT
        / "projects"
        / "ifrs9-ecl-engine"
        / "reports"
        / "cashflow_sensitivity"
        / "monthly_portfolio_projection.csv"
    )
    validation_path = (
        REPO_ROOT
        / "projects"
        / "model-validation-framework"
        / "reports"
        / "validation_summary.csv"
    )
    public_validation_path = (
        REPO_ROOT
        / "projects"
        / "model-validation-framework"
        / "reports"
        / "public_lendingclub"
        / "validation_summary.csv"
    )
    vintage_resolution_path = (
        REPO_ROOT
        / "projects"
        / "credit-risk-pd-model"
        / "reports"
        / "public_lendingclub"
        / "vintage_resolution.csv"
    )
    vintage_performance_path = (
        REPO_ROOT
        / "projects"
        / "model-validation-framework"
        / "reports"
        / "public_lendingclub"
        / "vintage_performance.csv"
    )
    characteristic_stability_path = (
        REPO_ROOT
        / "projects"
        / "model-validation-framework"
        / "reports"
        / "public_lendingclub"
        / "characteristic_stability_summary.csv"
    )
    strategy_comparison_path = (
        REPO_ROOT
        / "projects"
        / "credit-risk-pd-model"
        / "reports"
        / "public_lendingclub"
        / "strategy_oot_comparison.csv"
    )
    strategy_impact_path = (
        REPO_ROOT
        / "projects"
        / "credit-risk-pd-model"
        / "reports"
        / "public_lendingclub"
        / "strategy_incremental_impact.csv"
    )

    outputs = (
        _build_calibration_chart(calibration_path, output_dir / "public_pd_calibration.png"),
        _build_ecl_chart(ecl_path, output_dir / "ecl_stage_coverage.png"),
        _build_ecl_macro_overlay_chart(
            ecl_macro_path,
            ecl_reconciliation_path,
            output_dir / "ecl_macro_overlay.png",
        ),
        _build_macro_satellite_chart(
            macro_satellite_predictions_path,
            macro_satellite_ecl_path,
            output_dir / "australian_macro_satellite.png",
        ),
        _build_macro_remediation_chart(
            macro_satellite_predictions_path,
            macro_remediation_predictions_path,
            macro_remediation_comparison_path,
            output_dir / "australian_macro_remediation.png",
        ),
        _build_sicr_rebuttal_chart(
            sicr_reconciliation_path,
            output_dir / "ecl_sicr_rebuttal.png",
        ),
        _build_cashflow_sensitivity_chart(
            ecl_cashflow_summary_path,
            ecl_cashflow_monthly_path,
            output_dir / "ecl_cashflow_sensitivity.png",
        ),
        _build_validation_chart(
            validation_path,
            output_dir / "validation_opinion.png",
            decision=(
                "Discrimination and stability pass; calibration requires remediation"
            ),
        ),
        _build_validation_chart(
            public_validation_path,
            output_dir / "public_validation_opinion.png",
            decision="Policy opinion covers performance, score drift, and input drift",
        ),
        _build_vintage_backtest_chart(
            vintage_resolution_path,
            vintage_performance_path,
            output_dir / "public_vintage_backtest.png",
        ),
        _build_characteristic_stability_chart(
            characteristic_stability_path,
            output_dir / "public_feature_stability.png",
        ),
        _build_strategy_chart(
            strategy_comparison_path,
            strategy_impact_path,
            output_dir / "public_strategy_backtest.png",
        ),
    )
    for output in outputs:
        print(output)


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _build_calibration_chart(input_path: Path, output_path: Path) -> Path:
    rows = _read_csv(input_path)
    x = list(range(1, len(rows) + 1))
    predicted = [float(row["predicted_pd"]) for row in rows]
    observed = [float(row["observed_default_rate"]) for row in rows]

    figure, axis = plt.subplots(figsize=(8.4, 5.2), dpi=160)
    axis.plot(
        x,
        predicted,
        color=TEAL,
        linewidth=2.4,
        marker="o",
        markersize=5,
        label="Mean recalibrated PD",
    )
    axis.plot(
        x,
        observed,
        color=BLUE,
        linewidth=2.4,
        marker="s",
        markersize=4.5,
        label="Observed default rate",
    )
    axis.fill_between(x, observed, predicted, color=AMBER, alpha=0.12, label="Calibration gap")
    axis.set_title("Public LendingClub OOT calibration", loc="left", fontsize=15, pad=18)
    axis.text(
        0,
        1.02,
        "225,639 accounts | 2017-2018 OOT cohort | D01 lowest risk to D10 highest risk",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9,
        va="bottom",
    )
    axis.set_xlabel("Predicted-PD decile")
    axis.set_ylabel("Rate")
    axis.set_xticks(x, [f"D{value:02d}" for value in x])
    axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.set_ylim(0, max(predicted) * 1.14)
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, ncol=3, loc="upper left")
    figure.tight_layout()
    _save(figure, output_path)
    return output_path


def _build_ecl_chart(input_path: Path, output_path: Path) -> Path:
    rows = [row for row in _read_csv(input_path) if row["stage"] != "Total"]
    labels = [f"Stage {row['stage']}" for row in rows]
    coverage = [float(row["coverage_ratio"]) for row in rows]
    colors = [TEAL, AMBER, RED]

    figure, axis = plt.subplots(figsize=(7.4, 4.8), dpi=160)
    bars = axis.bar(labels, coverage, color=colors, width=0.58)
    axis.set_title(
        "IFRS 9 ECL coverage rises with credit deterioration",
        loc="left",
        fontsize=15,
        pad=18,
    )
    axis.text(
        0,
        1.02,
        "Scenario-weighted ECL divided by reporting-date gross exposure",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9,
        va="bottom",
    )
    axis.set_ylabel("Coverage ratio")
    axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.set_ylim(0, max(coverage) * 1.27)
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(bars, coverage, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(coverage) * 0.035,
            f"{value:.1%}",
            ha="center",
            va="bottom",
            color=TEXT,
            fontweight="bold",
        )
    figure.tight_layout()
    _save(figure, output_path)
    return output_path


def _build_ecl_macro_overlay_chart(
    sensitivity_path: Path,
    reconciliation_path: Path,
    output_path: Path,
) -> Path:
    sensitivity = _read_csv(sensitivity_path)
    reconciliation_rows = _read_csv(reconciliation_path)
    if len(reconciliation_rows) != 1:
        raise ValueError("ECL reconciliation showcase requires exactly one row")
    reconciliation = reconciliation_rows[0]

    case_labels = {
        "baseline": "Baseline",
        "downside_weight_plus_10pp": "Downside weight\n+10pp",
        "downside_severity_plus_10pct": "Downside severity\n+10%",
        "combined_downside": "Combined\ndownside",
        "empirical_downside_severity": "Empirical\nseverity",
        "combined_empirical_downside": "Combined\nstress",
    }
    labels = [case_labels.get(row["case_id"], row["case_id"]) for row in sensitivity]
    ecl_values = [float(row["modelled_ecl"]) / 1_000 for row in sensitivity]
    changes = [float(row["change_vs_baseline"]) / 1_000 for row in sensitivity]
    colors = [BLUE if row["is_baseline"] == "True" else AMBER for row in sensitivity]

    baseline = float(reconciliation["baseline_modelled_ecl"]) / 1_000
    overlay = float(reconciliation["recognized_management_overlay"]) / 1_000
    reported = float(reconciliation["illustrative_reported_ecl"]) / 1_000

    figure, (sensitivity_axis, reconciliation_axis) = plt.subplots(
        1,
        2,
        figsize=(9.6, 5.1),
        dpi=160,
        gridspec_kw={"width_ratios": [1.45, 0.85]},
    )
    figure.suptitle(
        "ECL macro sensitivity and overlay governance",
        x=0.07,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.07,
        0.91,
        "Synthetic portfolio | sensitivity deltas are disclosed, not booked",
        color=MUTED,
        fontsize=9,
    )

    bars = sensitivity_axis.bar(labels, ecl_values, color=colors, width=0.62)
    sensitivity_axis.set_title("Controlled macro cases", loc="left", fontsize=11, pad=12)
    sensitivity_axis.set_ylabel("ECL (thousands)")
    sensitivity_axis.set_ylim(0, max(ecl_values) * 1.26)
    sensitivity_axis.grid(axis="y", color=GRID, linewidth=0.8)
    sensitivity_axis.set_axisbelow(True)
    sensitivity_axis.spines[["top", "right"]].set_visible(False)
    sensitivity_axis.tick_params(axis="x", labelsize=8.5)
    for bar, value, change in zip(bars, ecl_values, changes, strict=True):
        label = f"{value:.1f}k" if change == 0 else f"{value:.1f}k\n(+{change:.1f}k)"
        sensitivity_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(ecl_values) * 0.035,
            label,
            ha="center",
            va="bottom",
            color=TEXT,
            fontsize=8.5,
            fontweight="bold",
        )

    reconciliation_bars = reconciliation_axis.bar(
        ["Modelled", "Illustrative\nreported"],
        [baseline, reported],
        color=[BLUE, TEAL],
        width=0.58,
    )
    reconciliation_axis.set_title("Booked bridge", loc="left", fontsize=11, pad=12)
    reconciliation_axis.set_ylim(0, max(reported, baseline) * 1.26)
    reconciliation_axis.grid(axis="y", color=GRID, linewidth=0.8)
    reconciliation_axis.set_axisbelow(True)
    reconciliation_axis.spines[["top", "right"]].set_visible(False)
    reconciliation_axis.tick_params(axis="x", labelsize=8.5)
    for bar, value in zip(reconciliation_bars, [baseline, reported], strict=True):
        reconciliation_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + reported * 0.035,
            f"{value:.1f}k",
            ha="center",
            color=TEXT,
            fontweight="bold",
        )
    reconciliation_axis.text(
        0.5,
        reported * 1.17,
        f"Recognized capped overlay: +{overlay:.1f}k",
        color=TEAL,
        fontsize=8.5,
        ha="center",
        va="center",
        fontweight="bold",
        clip_on=True,
    )

    figure.text(
        0.07,
        0.025,
        "Double-counted macro request blocked | distinct request pending approval | all requests disclosed",
        color=MUTED,
        fontsize=8.5,
    )
    figure.subplots_adjust(left=0.07, right=0.98, top=0.80, bottom=0.20, wspace=0.30)
    _save(figure, output_path)
    return output_path


def _build_macro_satellite_chart(
    predictions_path: Path,
    ecl_comparison_path: Path,
    output_path: Path,
) -> Path:
    oot_rows = [row for row in _read_csv(predictions_path) if row["split"] == "oot"]
    total_rows = [row for row in _read_csv(ecl_comparison_path) if row["stage"] == "Total"]
    if len(oot_rows) != 12 or len(total_rows) != 2:
        raise ValueError("Macro satellite showcase requires 12 OOT rows and two ECL totals")

    quarters = [row["quarter"][:7] for row in oot_rows]
    x_values = list(range(len(quarters)))
    actual = [float(row["actual_npl_ratio"]) for row in oot_rows]
    model = [float(row["model_prediction"]) for row in oot_rows]
    persistence = [float(row["persistence_prediction"]) for row in oot_rows]
    ecl_by_variant = {row["variant"]: float(row["modelled_ecl"]) for row in total_rows}
    incumbent = ecl_by_variant["incumbent_manual"]
    challenger = ecl_by_variant["challenger_empirical"]
    change_pct = challenger / incumbent - 1

    figure, (backtest_axis, ecl_axis) = plt.subplots(
        1,
        2,
        figsize=(10.2, 5.2),
        dpi=160,
        gridspec_kw={"width_ratios": [1.55, 0.75]},
    )
    figure.suptitle(
        "Australian macro satellite remains sensitivity-only",
        x=0.07,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.07,
        0.91,
        "70 public quarterly observations | frozen 2019-2021 OOT | independent opinion: RESTRICTED",
        color=MUTED,
        fontsize=9,
    )

    backtest_axis.plot(x_values, actual, color=TEXT, linewidth=2.2, marker="o", label="Actual")
    backtest_axis.plot(x_values, model, color=RED, linewidth=1.8, marker="s", label="Satellite")
    backtest_axis.plot(
        x_values,
        persistence,
        color=BLUE,
        linewidth=1.6,
        linestyle="--",
        label="Persistence",
    )
    backtest_axis.set_title("Frozen out-of-time backtest", loc="left", fontsize=11, pad=12)
    backtest_axis.set_ylabel("Aggregate NPL proxy")
    backtest_axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    backtest_axis.set_xticks(x_values[::2], quarters[::2], rotation=35, ha="right")
    backtest_axis.grid(axis="y", color=GRID, linewidth=0.8)
    backtest_axis.set_axisbelow(True)
    backtest_axis.spines[["top", "right"]].set_visible(False)
    backtest_axis.legend(frameon=False, ncol=3, loc="upper left", fontsize=8.5)
    backtest_axis.text(
        0.02,
        0.05,
        "MAE improvement vs persistence: -17.7%",
        transform=backtest_axis.transAxes,
        color=RED,
        fontsize=8.5,
        fontweight="bold",
    )

    ecl_values = [incumbent / 1_000, challenger / 1_000]
    bars = ecl_axis.bar(
        ["Manual\nincumbent", "Empirical\nchallenger"],
        ecl_values,
        color=[BLUE, AMBER],
        width=0.58,
    )
    ecl_axis.set_title("ECL model-choice sensitivity", loc="left", fontsize=11, pad=12)
    ecl_axis.set_ylabel("ECL (thousands)")
    ecl_axis.set_ylim(0, max(ecl_values) * 1.3)
    ecl_axis.grid(axis="y", color=GRID, linewidth=0.8)
    ecl_axis.set_axisbelow(True)
    ecl_axis.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(bars, ecl_values, strict=True):
        ecl_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(ecl_values) * 0.04,
            f"{value:.1f}k",
            ha="center",
            color=TEXT,
            fontweight="bold",
        )
    ecl_axis.text(
        0.5,
        max(ecl_values) * 1.19,
        f"Challenger change: {change_pct:.1%}",
        ha="center",
        color=AMBER,
        fontsize=8.5,
        fontweight="bold",
    )

    figure.text(
        0.07,
        0.025,
        "APRA asset-quality proxy + ABS macro series distributed by RBA | ECL difference is not a saving",
        color=MUTED,
        fontsize=8.5,
    )
    figure.subplots_adjust(left=0.07, right=0.98, top=0.80, bottom=0.21, wspace=0.30)
    _save(figure, output_path)
    return output_path


def _build_macro_remediation_chart(
    incumbent_predictions_path: Path,
    remediation_predictions_path: Path,
    comparison_path: Path,
    output_path: Path,
) -> Path:
    incumbent_rows = [
        row for row in _read_csv(incumbent_predictions_path) if row["split"] == "oot"
    ]
    remediation_rows = [
        row for row in _read_csv(remediation_predictions_path) if row["split"] == "oot"
    ]
    comparison = {row["variant"]: row for row in _read_csv(comparison_path)}
    if (
        len(incumbent_rows) != 12
        or len(remediation_rows) != 12
        or set(comparison) != {"incumbent_satellite", "selected_remediation"}
    ):
        raise ValueError("Macro remediation showcase requires complete OOT evidence")
    if [row["quarter"] for row in incumbent_rows] != [
        row["quarter"] for row in remediation_rows
    ]:
        raise ValueError("Macro remediation OOT quarters do not align with the incumbent")

    quarters = [row["quarter"][:7] for row in remediation_rows]
    x_values = list(range(len(quarters)))
    actual = [float(row["actual_npl_ratio"]) for row in remediation_rows]
    persistence = [float(row["persistence_prediction"]) for row in remediation_rows]
    incumbent = [float(row["model_prediction"]) for row in incumbent_rows]
    remediation = [float(row["model_prediction"]) for row in remediation_rows]
    incumbent_comparison = comparison["incumbent_satellite"]
    remediation_comparison = comparison["selected_remediation"]

    figure, (backtest_axis, benchmark_axis) = plt.subplots(
        1,
        2,
        figsize=(10.4, 5.3),
        dpi=160,
        gridspec_kw={"width_ratios": [1.55, 0.85]},
    )
    figure.suptitle(
        "Macro remediation narrows the benchmark gap",
        x=0.07,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.07,
        0.91,
        "Validation-only selection | reused 2019-2021 OOT | 0 findings closed | RESTRICTED",
        color=MUTED,
        fontsize=9,
    )

    backtest_axis.plot(
        x_values,
        actual,
        color=TEXT,
        linewidth=2.2,
        marker="o",
        label="Actual",
    )
    backtest_axis.plot(
        x_values,
        persistence,
        color=BLUE,
        linewidth=1.6,
        linestyle="--",
        label="Persistence",
    )
    backtest_axis.plot(
        x_values,
        incumbent,
        color=RED,
        linewidth=1.5,
        linestyle=":",
        marker="x",
        label="Incumbent",
    )
    backtest_axis.plot(
        x_values,
        remediation,
        color=TEAL,
        linewidth=2.0,
        marker="s",
        label="Remediation",
    )
    backtest_axis.set_title("Reused OOT backtest", loc="left", fontsize=11, pad=12)
    backtest_axis.set_ylabel("Aggregate NPL proxy")
    backtest_axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    backtest_axis.set_xticks(x_values[::2], quarters[::2], rotation=35, ha="right")
    backtest_axis.grid(axis="y", color=GRID, linewidth=0.8)
    backtest_axis.set_axisbelow(True)
    backtest_axis.spines[["top", "right"]].set_visible(False)
    backtest_axis.legend(frameon=False, ncol=2, loc="upper left", fontsize=8.3)

    metric_labels = ["MAE", "RMSE"]
    positions = list(range(len(metric_labels)))
    width = 0.34
    incumbent_values = [
        float(incumbent_comparison["mae_improvement_vs_persistence"]),
        float(incumbent_comparison["rmse_improvement_vs_persistence"]),
    ]
    remediation_values = [
        float(remediation_comparison["mae_improvement_vs_persistence"]),
        float(remediation_comparison["rmse_improvement_vs_persistence"]),
    ]
    incumbent_bars = benchmark_axis.bar(
        [position - width / 2 for position in positions],
        incumbent_values,
        width=width,
        color=RED,
        label="Incumbent",
    )
    remediation_bars = benchmark_axis.bar(
        [position + width / 2 for position in positions],
        remediation_values,
        width=width,
        color=TEAL,
        label="Remediation",
    )
    benchmark_axis.axhline(0, color=TEXT, linewidth=1.0)
    benchmark_axis.set_title("Improvement vs persistence", loc="left", fontsize=11, pad=12)
    benchmark_axis.set_xticks(positions, metric_labels)
    benchmark_axis.set_ylabel("Relative error improvement")
    benchmark_axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    benchmark_axis.set_ylim(-0.36, 0.09)
    benchmark_axis.grid(axis="y", color=GRID, linewidth=0.8)
    benchmark_axis.set_axisbelow(True)
    benchmark_axis.spines[["top", "right"]].set_visible(False)
    benchmark_axis.legend(
        frameon=False,
        fontsize=8.3,
        loc="upper center",
        ncol=2,
    )
    for bars, values in (
        (incumbent_bars, incumbent_values),
        (remediation_bars, remediation_values),
    ):
        for bar, value in zip(bars, values, strict=True):
            vertical_alignment = "bottom" if value >= 0 else "top"
            offset = 0.012 if value >= 0 else -0.012
            benchmark_axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + offset,
                f"{value:.1%}",
                ha="center",
                va=vertical_alignment,
                color=TEXT,
                fontsize=8,
                fontweight="bold",
            )

    figure.text(
        0.07,
        0.025,
        "Error vs incumbent: MAE -14.7% | RMSE -24.6% | historical performance, not a saving",
        color=MUTED,
        fontsize=8.5,
    )
    figure.subplots_adjust(left=0.07, right=0.98, top=0.80, bottom=0.21, wspace=0.30)
    _save(figure, output_path)
    return output_path


def _build_sicr_rebuttal_chart(
    reconciliation_path: Path,
    output_path: Path,
) -> Path:
    rows = _read_csv(reconciliation_path)
    if len(rows) != 1:
        raise ValueError("SICR rebuttal showcase requires exactly one reconciliation row")
    row = rows[0]
    stages = ["Stage 1", "Stage 2", "Stage 3"]
    baseline_counts = [
        int(row[f"baseline_stage{stage}_accounts"])
        for stage in [1, 2, 3]
    ]
    governed_counts = [
        int(row[f"governed_stage{stage}_accounts"])
        for stage in [1, 2, 3]
    ]
    baseline_ecl = float(row["baseline_modelled_ecl"]) / 1_000
    governed_ecl = float(row["governed_modelled_ecl"]) / 1_000
    reduction = float(row["ecl_reduction"]) / 1_000
    reduction_pct = float(row["ecl_reduction_pct"])

    figure, (stage_axis, ecl_axis) = plt.subplots(
        1,
        2,
        figsize=(9.6, 5.1),
        dpi=160,
        gridspec_kw={"width_ratios": [1.25, 0.85]},
    )
    figure.suptitle(
        "SICR rebuttal governance impact",
        x=0.07,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.07,
        0.91,
        (
            f"Synthetic portfolio | {row['effective_rebuttal_count']} of "
            f"{row['rebuttal_request_count']} requests effective"
        ),
        color=MUTED,
        fontsize=9,
    )

    positions = list(range(len(stages)))
    width = 0.34
    baseline_bars = stage_axis.bar(
        [position - width / 2 for position in positions],
        baseline_counts,
        width=width,
        color=BLUE,
        label="Before rebuttal",
    )
    governed_bars = stage_axis.bar(
        [position + width / 2 for position in positions],
        governed_counts,
        width=width,
        color=TEAL,
        label="Governed result",
    )
    stage_axis.set_title("Account stage distribution", loc="left", fontsize=11, pad=12)
    stage_axis.set_ylabel("Account count")
    stage_axis.set_xticks(positions, stages)
    stage_axis.set_ylim(0, max([*baseline_counts, *governed_counts]) + 1.2)
    stage_axis.grid(axis="y", color=GRID, linewidth=0.8)
    stage_axis.set_axisbelow(True)
    stage_axis.spines[["top", "right"]].set_visible(False)
    stage_axis.legend(frameon=False, ncol=2, loc="upper right", fontsize=8.5)
    for bar in [*baseline_bars, *governed_bars]:
        stage_axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.12,
            f"{int(bar.get_height())}",
            ha="center",
            color=TEXT,
            fontweight="bold",
        )

    ecl_bars = ecl_axis.bar(
        ["Before\nrebuttal", "Governed\nresult"],
        [baseline_ecl, governed_ecl],
        width=0.58,
        color=[BLUE, TEAL],
    )
    ecl_axis.set_title("Modelled ECL impact", loc="left", fontsize=11, pad=12)
    ecl_axis.set_ylabel("ECL (thousands)")
    ecl_axis.set_ylim(0, baseline_ecl * 1.30)
    ecl_axis.grid(axis="y", color=GRID, linewidth=0.8)
    ecl_axis.set_axisbelow(True)
    ecl_axis.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(ecl_bars, [baseline_ecl, governed_ecl], strict=True):
        ecl_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + baseline_ecl * 0.035,
            f"{value:.1f}k",
            ha="center",
            color=TEXT,
            fontweight="bold",
        )
    ecl_axis.text(
        0.5,
        baseline_ecl * 1.19,
        f"Controlled impact: -{reduction:.1f}k (-{reduction_pct:.1%})",
        ha="center",
        color=TEAL,
        fontsize=8.5,
        fontweight="bold",
    )

    figure.text(
        0.07,
        0.025,
        "Approved evidence changes one stage | pending decision unchanged | explicit SICR blocks rebuttal",
        color=MUTED,
        fontsize=8.5,
    )
    figure.subplots_adjust(left=0.07, right=0.98, top=0.80, bottom=0.19, wspace=0.30)
    _save(figure, output_path)
    return output_path


def _build_cashflow_sensitivity_chart(
    summary_path: Path,
    monthly_path: Path,
    output_path: Path,
) -> Path:
    summary = _read_csv(summary_path)
    monthly = _read_csv(monthly_path)
    if not summary:
        raise ValueError("Cash-flow sensitivity showcase requires summary rows")

    case_labels = {
        "baseline": "Baseline",
        "low_prepayment": "Lower\nprepayment",
        "low_cure": "Lower\ncure",
        "collateral_downturn": "Collateral\ndownturn",
        "delayed_recovery": "Delayed\nrecovery",
        "combined_downside": "Combined\ndownside",
    }
    labels = [case_labels.get(row["case_id"], row["case_id"]) for row in summary]
    modelled_ecl = [float(row["modelled_ecl"]) / 1_000 for row in summary]
    changes = [float(row["ecl_change_pct"]) for row in summary]
    colors = [BLUE, TEAL, AMBER, RED, MUTED, TEXT]

    base_paths: dict[str, list[dict[str, str]]] = {}
    for case_id in ["baseline", "low_prepayment"]:
        base_paths[case_id] = sorted(
            [
                row
                for row in monthly
                if row["case_id"] == case_id and row["scenario"] == "base"
            ],
            key=lambda row: int(row["month"]),
        )
        if not base_paths[case_id]:
            raise ValueError(f"Missing base-scenario monthly path for {case_id}")

    figure, (impact_axis, path_axis) = plt.subplots(
        1,
        2,
        figsize=(10.8, 5.3),
        dpi=160,
        gridspec_kw={"width_ratios": [1.45, 1.0]},
    )
    figure.suptitle(
        "Contractual cash-flow assumptions change modelled ECL",
        x=0.065,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.065,
        0.91,
        "Synthetic six-account portfolio | sensitivity deltas versus neutral baseline",
        color=MUTED,
        fontsize=9,
    )

    bars = impact_axis.bar(labels, modelled_ecl, color=colors, width=0.65)
    impact_axis.set_title("Portfolio sensitivity", loc="left", fontsize=11, pad=12)
    impact_axis.set_ylabel("Modelled ECL (thousands)")
    impact_axis.set_ylim(0, max(modelled_ecl) * 1.30)
    impact_axis.grid(axis="y", color=GRID, linewidth=0.8)
    impact_axis.set_axisbelow(True)
    impact_axis.spines[["top", "right"]].set_visible(False)
    impact_axis.tick_params(axis="x", labelsize=8)
    for bar, value, change in zip(bars, modelled_ecl, changes, strict=True):
        annotation = f"{value:.1f}k" if change == 0 else f"{value:.1f}k\n+{change:.1%}"
        impact_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(modelled_ecl) * 0.035,
            annotation,
            ha="center",
            va="bottom",
            color=TEXT,
            fontsize=8.3,
            fontweight="bold",
        )

    for case_id, color, label in [
        ("baseline", BLUE, "Baseline CPR"),
        ("low_prepayment", TEAL, "CPR reduced 50%"),
    ]:
        rows = base_paths[case_id]
        path_axis.plot(
            [int(row["month"]) for row in rows],
            [float(row["portfolio_ead"]) / 1_000 for row in rows],
            color=color,
            linewidth=2.3,
            label=label,
        )
    path_axis.set_title("Base-scenario EAD path", loc="left", fontsize=11, pad=12)
    path_axis.set_xlabel("Projection month")
    path_axis.set_ylabel("Portfolio EAD (thousands)")
    path_axis.set_xlim(1, 36)
    path_axis.set_xticks([1, 6, 12, 18, 24, 30, 36])
    path_axis.grid(axis="y", color=GRID, linewidth=0.8)
    path_axis.set_axisbelow(True)
    path_axis.spines[["top", "right"]].set_visible(False)
    path_axis.legend(frameon=False, fontsize=8.5, loc="upper right")

    figure.text(
        0.065,
        0.025,
        "Lower prepayment preserves future EAD; recovery timing and collateral assumptions change effective LGD",
        color=MUTED,
        fontsize=8.5,
    )
    figure.subplots_adjust(left=0.065, right=0.985, top=0.80, bottom=0.20, wspace=0.28)
    _save(figure, output_path)
    return output_path


def _build_strategy_chart(
    comparison_path: Path,
    impact_path: Path,
    output_path: Path,
) -> Path:
    comparison = {row["policy"]: row for row in _read_csv(comparison_path)}
    if set(comparison) != {"incumbent", "challenger"}:
        raise ValueError("Strategy showcase requires incumbent and challenger rows")
    impact_rows = _read_csv(impact_path)
    if len(impact_rows) != 1:
        raise ValueError("Strategy showcase requires one incremental-impact row")
    impact = impact_rows[0]

    approval_rates = [
        float(comparison["incumbent"]["approval_rate"]),
        float(comparison["challenger"]["approval_rate"]),
    ]
    expected_increment = float(impact["incremental_expected_credit_contribution_proxy"])
    realized_increment = float(impact["incremental_realized_credit_contribution_proxy"])
    realized_lower = float(impact["realized_contribution_ci_lower"])
    realized_upper = float(impact["realized_contribution_ci_upper"])
    contribution_values = [expected_increment / 1_000_000, realized_increment / 1_000_000]
    realized_error = [
        (realized_increment - realized_lower) / 1_000_000,
        (realized_upper - realized_increment) / 1_000_000,
    ]

    figure, (approval_axis, contribution_axis) = plt.subplots(
        1,
        2,
        figsize=(9.4, 4.9),
        dpi=160,
        gridspec_kw={"width_ratios": [0.9, 1.25]},
    )
    figure.suptitle(
        "Public LendingClub credit policy backtest",
        x=0.07,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.07,
        0.91,
        "Pre-OOT selected 20% max-PD challenger | frozen 2017-2018 OOT evaluation",
        color=MUTED,
        fontsize=9,
    )

    approval_bars = approval_axis.bar(
        ["Incumbent\n15% cutoff", "Challenger\n20% cutoff"],
        approval_rates,
        color=[BLUE, TEAL],
        width=0.62,
    )
    approval_axis.set_title("Approval rate", loc="left", fontsize=11, pad=12)
    approval_axis.set_ylim(0, max(approval_rates) * 1.28)
    approval_axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    approval_axis.grid(axis="y", color=GRID, linewidth=0.8)
    approval_axis.set_axisbelow(True)
    approval_axis.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(approval_bars, approval_rates, strict=True):
        approval_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.018,
            f"{value:.1%}",
            ha="center",
            color=TEXT,
            fontweight="bold",
        )

    contribution_bars = contribution_axis.bar(
        ["Expected\ncontribution", "Realised\ncontribution"],
        contribution_values,
        color=[AMBER, TEAL],
        width=0.62,
    )
    contribution_axis.errorbar(
        1,
        contribution_values[1],
        yerr=[[realized_error[0]], [realized_error[1]]],
        color=TEXT,
        capsize=5,
        linewidth=1.4,
        zorder=3,
    )
    contribution_axis.axhline(0, color=TEXT, linewidth=0.9)
    contribution_axis.set_title("Incremental credit contribution proxy", loc="left", fontsize=11, pad=12)
    contribution_axis.set_ylabel("USD millions")
    contribution_axis.set_ylim(0, max(contribution_values) * 1.32)
    contribution_axis.grid(axis="y", color=GRID, linewidth=0.8)
    contribution_axis.set_axisbelow(True)
    contribution_axis.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(contribution_bars, contribution_values, strict=True):
        contribution_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(contribution_values) * 0.065,
            f"+${value:.1f}m",
            ha="center",
            color=TEXT,
            fontweight="bold",
        )
    contribution_axis.text(
        1,
        contribution_values[1] - max(contribution_values) * 0.15,
        (
            f"95% CI {realized_lower / 1_000_000:.1f}-"
            f"{realized_upper / 1_000_000:.1f}m"
        ),
        ha="center",
        color="white",
        fontsize=8,
        fontweight="bold",
    )

    figure.text(
        0.07,
        0.025,
        (
            f"+{int(float(impact['incremental_approved_accounts'])):,} approvals | "
            f"+${float(impact['incremental_approved_exposure']) / 1_000_000:.1f}m exposure | "
            "retrospective accepted-loan sample; not causal"
        ),
        color=MUTED,
        fontsize=8.5,
    )
    figure.subplots_adjust(left=0.07, right=0.98, top=0.79, bottom=0.18, wspace=0.34)
    _save(figure, output_path)
    return output_path


def _build_validation_chart(
    input_path: Path,
    output_path: Path,
    *,
    decision: str,
) -> Path:
    rows = _read_csv(input_path)
    labels = {
        "auc": "ROC AUC",
        "ks": "KS statistic",
        "absolute_calibration_gap": "Absolute calibration gap",
        "population_stability_index": "Population stability index",
        "challenger_auc_margin": "Challenger AUC margin",
        "maximum_characteristic_stability_index": "Maximum characteristic stability index",
    }
    status_colors = {"pass": TEAL, "warning": AMBER, "fail": RED}
    overall_status = _overall_status(rows)

    figure, axis = plt.subplots(figsize=(8.8, 5.1), dpi=160)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, len(rows) + 1.8)
    axis.axis("off")
    axis.text(0, len(rows) + 1.45, "Independent validation opinion", fontsize=15, color=TEXT)
    overall_color = status_colors[overall_status.lower()]
    axis.text(
        0,
        len(rows) + 1.02,
        f"Overall {overall_status}: {decision}",
        fontsize=9.5,
        color=overall_color,
        fontweight="bold",
    )
    axis.text(0.02, len(rows) + 0.5, "CHECK", fontsize=8.5, color=MUTED, fontweight="bold")
    axis.text(0.66, len(rows) + 0.5, "OBSERVED", fontsize=8.5, color=MUTED, fontweight="bold")
    axis.text(0.84, len(rows) + 0.5, "STATUS", fontsize=8.5, color=MUTED, fontweight="bold")

    for index, row in enumerate(rows):
        y = len(rows) - index - 0.05
        axis.add_patch(Rectangle((0, y - 0.42), 1, 0.75, facecolor=LIGHT, edgecolor=GRID))
        status = row["status"]
        metric = float(row["metric_value"])
        metric_text = f"{metric:.3f}"
        axis.text(0.02, y, labels[row["check"]], va="center", color=TEXT, fontsize=10)
        axis.text(0.66, y, metric_text, va="center", color=TEXT, fontsize=10)
        axis.scatter([0.85], [y], s=55, color=status_colors[status], zorder=3)
        axis.text(
            0.875,
            y,
            status.upper(),
            va="center",
            color=status_colors[status],
            fontsize=9,
            fontweight="bold",
        )
    figure.tight_layout()
    _save(figure, output_path)
    return output_path


def _build_characteristic_stability_chart(input_path: Path, output_path: Path) -> Path:
    rows = _read_csv(input_path)
    available = [row for row in rows if row["stability_status"] != "not_available"]
    if not available:
        raise ValueError("Showcase requires at least one available characteristic CSI")
    available.sort(key=lambda row: float(row["characteristic_stability_index"]))
    labels = [row["feature_name"].replace("_", " ") for row in available]
    values = [float(row["characteristic_stability_index"]) for row in available]
    status_colors = {
        "stable": TEAL,
        "moderate_shift": AMBER,
        "material_shift": RED,
    }
    colors = [status_colors[row["stability_status"]] for row in available]
    unavailable = [row["feature_name"] for row in rows if row["stability_status"] == "not_available"]
    period = rows[0]

    figure, axis = plt.subplots(figsize=(9.0, 6.2), dpi=160)
    bars = axis.barh(labels, values, color=colors, height=0.62)
    axis.axvline(0.10, color=AMBER, linewidth=1.4, linestyle="--")
    axis.axvline(0.25, color=RED, linewidth=1.4, linestyle="--")
    axis.set_title("Public LendingClub feature stability", loc="left", fontsize=15, pad=24)
    subtitle = (
        f"CSI: {period['reference_start']} to {period['reference_end']} vs "
        f"{period['current_start']} to {period['current_end']}"
    )
    if unavailable:
        subtitle += f" | unavailable: {', '.join(unavailable)}"
    axis.text(
        0,
        1.02,
        subtitle,
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9,
        va="bottom",
    )
    maximum = max(max(values) * 1.20, 0.29)
    axis.set_xlim(0, maximum)
    axis.set_xlabel("Characteristic Stability Index (lower is better)")
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)
    for bar, value in zip(bars, values, strict=True):
        axis.text(
            value + maximum * 0.012,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            color=TEXT,
            fontsize=8.5,
        )
    axis.legend(
        handles=[
            Rectangle((0, 0), 1, 1, color=TEAL, label="Stable (<=0.10)"),
            Rectangle((0, 0), 1, 1, color=AMBER, label="Moderate (<=0.25)"),
            Rectangle((0, 0), 1, 1, color=RED, label="Material (>0.25)"),
        ],
        frameon=True,
        framealpha=0.95,
        edgecolor="none",
        ncol=1,
        loc="upper right",
        fontsize=8.5,
    )
    figure.tight_layout()
    _save(figure, output_path)
    return output_path


def _overall_status(rows: list[dict[str, str]]) -> str:
    statuses = {row["status"] for row in rows}
    if "fail" in statuses:
        return "FAIL"
    if "warning" in statuses:
        return "WARNING"
    return "PASS"


def _build_vintage_backtest_chart(
    resolution_path: Path,
    performance_path: Path,
    output_path: Path,
) -> Path:
    resolution_rows = _read_csv(resolution_path)
    performance_rows = _read_csv(performance_path)
    resolution_x = list(range(len(resolution_rows)))
    resolution = [float(row["resolution_rate"]) for row in resolution_rows]
    resolution_labels = [row["vintage_quarter"] for row in resolution_rows]
    performance_x = list(range(len(performance_rows)))
    performance_labels = [row["vintage_quarter"] for row in performance_rows]
    observed = [float(row["observed_default_rate"]) for row in performance_rows]
    observed_lower = [
        float(row["observed_default_rate_lower"]) for row in performance_rows
    ]
    observed_upper = [
        float(row["observed_default_rate_upper"]) for row in performance_rows
    ]
    predicted = [float(row["mean_pd"]) for row in performance_rows]

    figure, (resolution_axis, performance_axis) = plt.subplots(
        2,
        1,
        figsize=(9.2, 7.0),
        dpi=160,
        gridspec_kw={"height_ratios": [1, 1.35]},
    )
    figure.suptitle(
        "Public LendingClub vintage maturity and OOT backtest",
        x=0.08,
        ha="left",
        fontsize=15,
        color=TEXT,
    )
    figure.text(
        0.08,
        0.925,
        "Resolution denominator includes unresolved raw statuses; default-rate intervals are Wilson 95% CIs",
        color=MUTED,
        fontsize=9,
    )

    resolution_axis.plot(
        resolution_x,
        resolution,
        color=TEAL,
        linewidth=2.2,
        marker="o",
        markersize=3.5,
    )
    resolution_axis.fill_between(resolution_x, 0, resolution, color=TEAL, alpha=0.08)
    resolution_axis.set_title("Raw-loan outcome resolution by issue quarter", loc="left", fontsize=11)
    resolution_axis.set_ylabel("Resolved share")
    resolution_axis.set_ylim(0, 1.05)
    resolution_axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    _set_quarter_ticks(resolution_axis, resolution_labels)
    _style_time_axis(resolution_axis)

    lower_errors = [value - lower for value, lower in zip(observed, observed_lower, strict=True)]
    upper_errors = [upper - value for value, upper in zip(observed, observed_upper, strict=True)]
    performance_axis.errorbar(
        performance_x,
        observed,
        yerr=[lower_errors, upper_errors],
        color=BLUE,
        linewidth=2.0,
        marker="s",
        markersize=4.5,
        capsize=3,
        label="Observed default rate (95% CI)",
    )
    performance_axis.plot(
        performance_x,
        predicted,
        color=AMBER,
        linewidth=2.2,
        marker="o",
        markersize=4.5,
        label="Mean recalibrated PD",
    )
    performance_axis.fill_between(
        performance_x,
        observed,
        predicted,
        color=RED,
        alpha=0.08,
        label="Calibration gap",
    )
    performance_axis.set_title(
        "Frozen-score out-of-time performance by issue quarter",
        loc="left",
        fontsize=11,
    )
    performance_axis.set_ylabel("Rate")
    performance_axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    performance_axis.set_ylim(
        0,
        max([*predicted, *observed_upper]) * 1.18,
    )
    _set_quarter_ticks(performance_axis, performance_labels, maximum_ticks=8)
    _style_time_axis(performance_axis)
    performance_axis.legend(frameon=False, ncol=3, loc="upper left", fontsize=8.5)

    figure.subplots_adjust(left=0.08, right=0.98, top=0.86, bottom=0.09, hspace=0.47)
    _save(figure, output_path)
    return output_path


def _set_quarter_ticks(axis: plt.Axes, labels: list[str], *, maximum_ticks: int = 12) -> None:
    if not labels:
        return
    stride = max(1, (len(labels) + maximum_ticks - 1) // maximum_ticks)
    positions = list(range(0, len(labels), stride))
    if positions[-1] != len(labels) - 1:
        positions.append(len(labels) - 1)
    axis.set_xticks(positions, [labels[position] for position in positions], rotation=35)


def _style_time_axis(axis: plt.Axes) -> None:
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Showcase input not found: {path}")
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def _save(figure: plt.Figure, output_path: Path) -> None:
    figure.savefig(
        output_path,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "risk-analytics-portfolio"},
    )
    plt.close(figure)


if __name__ == "__main__":
    main()
