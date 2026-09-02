from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model_validation import Project1OOTPredictionAdapter, run_validation
from model_validation.postgres import (
    ValidationRunMetadata,
    persist_remediation_result,
    persist_validation_result,
)
from model_validation.remediation import run_calibration_remediation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Project 3 validation and persist governance evidence to PostgreSQL."
    )
    parser.add_argument(
        "--dsn",
        default=os.getenv("MODEL_VALIDATION_DATABASE_URL"),
        help="PostgreSQL DSN; defaults to MODEL_VALIDATION_DATABASE_URL.",
    )
    parser.add_argument(
        "--prediction-path",
        type=Path,
        default=PROJECT_DIR.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv",
    )
    parser.add_argument(
        "--source-report-path",
        default="projects/credit-risk-pd-model/reports/oot_predictions.csv",
        help="Repository-relative lineage path stored with the validation run.",
    )
    parser.add_argument("--source-commit-sha", default=None)
    parser.add_argument(
        "--data-context",
        choices=("synthetic", "public_lendingclub"),
        default="synthetic",
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Apply sql/schema.sql before loading the validation result.",
    )
    parser.add_argument(
        "--persist-remediation",
        action="store_true",
        help="Persist the rolling calibration retest and finding lifecycle events.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dsn:
        raise SystemExit("A PostgreSQL DSN is required via --dsn or MODEL_VALIDATION_DATABASE_URL")

    result = run_validation(
        Project1OOTPredictionAdapter(args.prediction_path, data_context=args.data_context)
    )
    metadata = ValidationRunMetadata(
        source_report_path=args.source_report_path,
        source_commit_sha=args.source_commit_sha,
    )
    with psycopg.connect(args.dsn) as connection:
        if args.apply_schema:
            schema = (PROJECT_DIR / "sql" / "schema.sql").read_text(encoding="utf-8")
            connection.execute(schema)
        validation_run_id = persist_validation_result(connection, result, metadata)
        finding_id = None
        if args.persist_remediation:
            remediation = run_calibration_remediation(
                Project1OOTPredictionAdapter(
                    args.prediction_path,
                    data_context=args.data_context,
                )
            )
            finding_id = persist_remediation_result(
                connection,
                validation_run_id,
                remediation,
            )
    print(f"Persisted validation_run_id={validation_run_id}")
    if finding_id is not None:
        print(f"Persisted remediation finding_id={finding_id}")


if __name__ == "__main__":
    main()
