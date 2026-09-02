from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PUBLIC_VALIDATION_FILES = (
    "benchmark_comparison.csv",
    "calibration_by_decile.csv",
    "input_audit.csv",
    "model_limitations.csv",
    "model_metrics.csv",
    "monthly_performance.csv",
    "stability_bins.csv",
    "stability_summary.csv",
    "validation_findings.csv",
    "validation_report.md",
    "validation_summary.csv",
)
EXCLUDED_BORROWER_LEVEL_FILES = ("oot_predictions.csv",)


@dataclass(frozen=True)
class PublicValidationPublication:
    output_dir: Path
    published_paths: tuple[Path, ...]


def publish_public_validation(
    source_report_dir: str | Path,
    project1_lineage_path: str | Path,
    output_dir: str | Path,
) -> PublicValidationPublication:
    """Publish aggregate public-data validation evidence with source lineage."""
    source_report_dir = Path(source_report_dir)
    project1_lineage_path = Path(project1_lineage_path)
    output_dir = Path(output_dir)
    if not project1_lineage_path.is_file():
        raise FileNotFoundError(f"Project 1 public lineage not found: {project1_lineage_path}")

    missing = [
        filename
        for filename in PUBLIC_VALIDATION_FILES
        if not (source_report_dir / filename).is_file()
    ]
    if missing:
        raise FileNotFoundError("Public validation reports missing: " + ", ".join(missing))

    for filename in PUBLIC_VALIDATION_FILES:
        path = source_report_dir / filename
        if path.suffix == ".csv" and "customer_id" in pd.read_csv(path, nrows=0).columns:
            raise ValueError(f"Public validation report cannot include customer_id: {filename}")

    source_lineage = json.loads(project1_lineage_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in EXCLUDED_BORROWER_LEVEL_FILES:
        (output_dir / filename).unlink(missing_ok=True)
    published_paths = []
    for filename in PUBLIC_VALIDATION_FILES:
        destination = output_dir / filename
        shutil.copyfile(source_report_dir / filename, destination)
        published_paths.append(destination)

    lineage = {
        "data_context": "public_lendingclub",
        "source_model_evidence": (
            "projects/credit-risk-pd-model/reports/public_lendingclub"
        ),
        "source_raw_file": source_lineage["raw_file"],
        "source_raw_file_sha256": source_lineage["raw_file_sha256"],
        "published_aggregate_reports": list(PUBLIC_VALIDATION_FILES),
        "excluded_borrower_level_input": "oot_predictions.csv",
    }
    lineage_path = output_dir / "data_lineage.json"
    lineage_path.write_text(
        json.dumps(lineage, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    published_paths.append(lineage_path)
    return PublicValidationPublication(output_dir, tuple(published_paths))
