from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

KAGGLE_DATASET_URL = "https://www.kaggle.com/datasets/wordsforthewise/lending-club"
SAFE_AGGREGATE_REPORTS = (
    "approval_strategy.csv",
    "calibration_table.csv",
    "feature_importance.csv",
    "model_metrics.csv",
    "model_report.md",
    "model_selection_audit.csv",
    "psi_report.csv",
    "recalibration_summary.csv",
    "woe_bins.csv",
    "woe_summary.csv",
)
EXCLUDED_BORROWER_LEVEL_REPORTS = ("oot_predictions.csv",)


@dataclass(frozen=True)
class PublicRunPublication:
    output_dir: Path
    published_paths: tuple[Path, ...]
    manifest_path: Path


def publish_public_lendingclub_run(
    source_report_dir: str | Path,
    ingestion_audit_path: str | Path,
    raw_input_path: str | Path,
    output_dir: str | Path,
) -> PublicRunPublication:
    """Publish aggregate LendingClub evidence without borrower-level predictions."""
    source_report_dir = Path(source_report_dir)
    ingestion_audit_path = Path(ingestion_audit_path)
    raw_input_path = Path(raw_input_path)
    output_dir = Path(output_dir)

    if not raw_input_path.is_file():
        raise FileNotFoundError(f"Raw LendingClub input not found: {raw_input_path}")
    if not ingestion_audit_path.is_file():
        raise FileNotFoundError(f"LendingClub ingestion audit not found: {ingestion_audit_path}")

    missing_reports = [
        filename
        for filename in SAFE_AGGREGATE_REPORTS
        if not (source_report_dir / filename).is_file()
    ]
    if missing_reports:
        raise FileNotFoundError(
            "Public LendingClub publication is missing aggregate reports: "
            + ", ".join(missing_reports)
        )

    _validate_aggregate_reports(source_report_dir)
    audit = _load_single_row_audit(ingestion_audit_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in EXCLUDED_BORROWER_LEVEL_REPORTS:
        (output_dir / filename).unlink(missing_ok=True)
    published_paths = []
    for filename in SAFE_AGGREGATE_REPORTS:
        destination = output_dir / filename
        shutil.copyfile(source_report_dir / filename, destination)
        published_paths.append(destination)

    published_audit = audit.copy()
    published_audit.loc[0, "input_path"] = f"data/raw/{raw_input_path.name}"
    published_audit_path = output_dir / "ingestion_audit.csv"
    published_audit.to_csv(published_audit_path, index=False, lineterminator="\n")
    published_paths.append(published_audit_path)

    manifest = {
        "dataset": "All Lending Club loan data - accepted loans",
        "dataset_url": KAGGLE_DATASET_URL,
        "dataset_license": "CC0: Public Domain",
        "raw_file": raw_input_path.name,
        "raw_file_sha256": _sha256(raw_input_path),
        "input_rows": int(audit.loc[0, "input_rows"]),
        "resolved_output_rows": int(audit.loc[0, "output_rows"]),
        "observation_date_min": str(audit.loc[0, "observation_date_min"]),
        "observation_date_max": str(audit.loc[0, "observation_date_max"]),
        "published_aggregate_reports": [
            *SAFE_AGGREGATE_REPORTS,
            published_audit_path.name,
        ],
        "excluded_borrower_level_reports": list(EXCLUDED_BORROWER_LEVEL_REPORTS),
    }
    manifest_path = output_dir / "data_lineage.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    published_paths.append(manifest_path)

    return PublicRunPublication(
        output_dir=output_dir,
        published_paths=tuple(published_paths),
        manifest_path=manifest_path,
    )


def _validate_aggregate_reports(source_report_dir: Path) -> None:
    for filename in SAFE_AGGREGATE_REPORTS:
        path = source_report_dir / filename
        if path.suffix == ".csv":
            columns = pd.read_csv(path, nrows=0).columns
            if "customer_id" in columns:
                raise ValueError(f"Aggregate publication cannot include customer_id: {filename}")


def _load_single_row_audit(path: Path) -> pd.DataFrame:
    audit = pd.read_csv(path, dtype={"input_path": "string"})
    required_columns = {
        "input_path",
        "input_rows",
        "output_rows",
        "observation_date_min",
        "observation_date_max",
    }
    missing_columns = sorted(required_columns - set(audit.columns))
    if missing_columns:
        raise ValueError("Ingestion audit missing columns: " + ", ".join(missing_columns))
    if len(audit) != 1:
        raise ValueError("Ingestion audit must contain exactly one row")
    return audit


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
