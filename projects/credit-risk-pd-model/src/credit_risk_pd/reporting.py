from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


MetricFormatter = Callable[[object], str]


def generate_model_report(reports_dir: str | Path = "reports") -> Path:
    """Generate a recruiter-readable markdown summary from model report CSVs."""
    reports_path = Path(reports_dir)
    metrics = _read_csv(
        reports_path / "model_metrics.csv",
        [
            "model",
            "roc_auc",
            "gini",
            "ks",
            "brier_score",
            "precision",
            "recall",
        ],
    )
    calibration = _read_csv(
        reports_path / "calibration_table.csv",
        [
            "bucket",
            "accounts",
            "predicted_pd",
            "observed_default_rate",
            "defaults",
            "calibration_gap",
        ],
    )
    psi = _read_csv(reports_path / "psi_report.csv", ["feature", "psi", "status"])

    metrics = metrics.sort_values("roc_auc", ascending=False).reset_index(drop=True)
    best_model = metrics.iloc[0]
    material_shift_count = int(psi["status"].eq("material_shift").sum())
    moderate_shift_count = int(psi["status"].eq("moderate_shift").sum())
    top_drift_feature = psi.sort_values("psi", ascending=False).iloc[0]
    largest_gap = calibration.iloc[calibration["calibration_gap"].abs().idxmax()]

    report = "\n".join(
        [
            "# Credit Risk PD Model Report",
            "",
            "## Executive Summary",
            "",
            f"- Best model by out-of-time ROC-AUC: `{best_model['model']}`.",
            (
                "- Discrimination: "
                f"ROC-AUC {_format_decimal(best_model['roc_auc'])}, "
                f"Gini {_format_decimal(best_model['gini'])}, "
                f"KS {_format_decimal(best_model['ks'])}."
            ),
            (
                "- Calibration: "
                f"Brier score {_format_decimal(best_model['brier_score'])}; "
                f"largest absolute decile gap {_format_percent(largest_gap['calibration_gap'])}."
            ),
            (
                "- Stability: "
                f"{material_shift_count} material shift feature(s), "
                f"{moderate_shift_count} moderate shift feature(s); "
                f"top PSI feature `{top_drift_feature['feature']}` "
                f"({_format_decimal(top_drift_feature['psi'])})."
            ),
            "",
            "## Model Performance",
            "",
            _markdown_table(
                metrics,
                [
                    ("model", "Model", str),
                    ("roc_auc", "ROC-AUC", _format_decimal),
                    ("gini", "Gini", _format_decimal),
                    ("ks", "KS", _format_decimal),
                    ("brier_score", "Brier", _format_decimal),
                    ("precision", "Precision", _format_percent),
                    ("recall", "Recall", _format_percent),
                ],
            ),
            "",
            "## Calibration Review",
            "",
            (
                "Decile calibration compares average predicted PD with observed default rate. "
                "Positive gaps indicate predicted PD is above the realised default rate."
            ),
            "",
            _markdown_table(
                calibration,
                [
                    ("bucket", "PD Bucket", str),
                    ("accounts", "Accounts", _format_integer),
                    ("predicted_pd", "Predicted PD", _format_percent),
                    ("observed_default_rate", "Observed Default Rate", _format_percent),
                    ("defaults", "Defaults", _format_integer),
                    ("calibration_gap", "Gap", _format_percent),
                ],
            ),
            "",
            "## Population Stability",
            "",
            (
                "PSI highlights feature drift between the development and out-of-time samples, "
                "supporting model monitoring and validation review."
            ),
            "",
            _markdown_table(
                psi.sort_values("psi", ascending=False),
                [
                    ("feature", "Feature", str),
                    ("psi", "PSI", _format_decimal),
                    ("status", "Status", str),
                ],
            ),
            "",
        ]
    )

    report_path = reports_path / "model_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def _read_csv(path: Path, required_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing report input: {path}")

    frame = pd.read_csv(path)
    missing = sorted(set(required_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required column(s): {', '.join(missing)}")
    if frame.empty:
        raise ValueError(f"{path} must contain at least one row")
    return frame


def _markdown_table(
    frame: pd.DataFrame,
    columns: list[tuple[str, str, MetricFormatter]],
) -> str:
    header = "| " + " | ".join(label for _, label, _ in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| "
        + " | ".join(formatter(row[column]) for column, _, formatter in columns)
        + " |"
        for _, row in frame.iterrows()
    ]
    return "\n".join([header, separator, *rows])


def _format_decimal(value: object) -> str:
    return f"{float(value):.3f}"


def _format_percent(value: object) -> str:
    return f"{float(value):.1%}"


def _format_integer(value: object) -> str:
    return f"{float(value):.0f}"
