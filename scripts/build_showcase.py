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

    outputs = (
        _build_calibration_chart(calibration_path, output_dir / "public_pd_calibration.png"),
        _build_ecl_chart(ecl_path, output_dir / "ecl_stage_coverage.png"),
        _build_validation_chart(
            validation_path,
            output_dir / "validation_opinion.png",
            overall_status="FAIL",
            decision=(
                "Discrimination and stability pass; calibration requires remediation"
            ),
        ),
        _build_validation_chart(
            public_validation_path,
            output_dir / "public_validation_opinion.png",
            overall_status="WARNING",
            decision="AUC, KS, and calibration require monitoring; stability checks pass",
        ),
        _build_vintage_backtest_chart(
            vintage_resolution_path,
            vintage_performance_path,
            output_dir / "public_vintage_backtest.png",
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


def _build_validation_chart(
    input_path: Path,
    output_path: Path,
    *,
    overall_status: str,
    decision: str,
) -> Path:
    rows = _read_csv(input_path)
    labels = {
        "auc": "ROC AUC",
        "ks": "KS statistic",
        "absolute_calibration_gap": "Absolute calibration gap",
        "population_stability_index": "Population stability index",
        "challenger_auc_margin": "Challenger AUC margin",
    }
    status_colors = {"pass": TEAL, "warning": AMBER, "fail": RED}

    figure, axis = plt.subplots(figsize=(8.8, 5.1), dpi=160)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, len(rows) + 1.8)
    axis.axis("off")
    axis.text(0, len(rows) + 1.45, "Independent validation opinion", fontsize=15, color=TEXT)
    overall_color = status_colors["fail" if overall_status == "FAIL" else "warning"]
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
