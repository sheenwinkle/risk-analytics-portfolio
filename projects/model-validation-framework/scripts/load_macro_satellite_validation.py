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

from model_validation.macro_remediation_demo import run_macro_remediation_validation
from model_validation.macro_satellite_demo import run_macro_satellite_validation
from model_validation.postgres import (
    MacroRemediationRunMetadata,
    MacroSatelliteRunMetadata,
    persist_macro_remediation_result,
    persist_macro_satellite_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and persist Australian macro-satellite governance evidence."
    )
    parser.add_argument(
        "--dsn",
        default=os.getenv("MODEL_VALIDATION_DATABASE_URL"),
        help="PostgreSQL DSN; defaults to MODEL_VALIDATION_DATABASE_URL.",
    )
    parser.add_argument(
        "--developer-report-dir",
        type=Path,
        default=(
            PROJECT_DIR.parent
            / "ifrs9-ecl-engine"
            / "reports"
            / "macro_satellite"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "reports" / "macro_satellite",
    )
    parser.add_argument(
        "--source-report-path",
        default=(
            "projects/ifrs9-ecl-engine/reports/macro_satellite/"
            "backtest_predictions.csv"
        ),
    )
    parser.add_argument("--source-commit-sha", default=None)
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Apply sql/schema.sql before loading the validation result.",
    )
    parser.add_argument(
        "--persist-remediation",
        action="store_true",
        help="Persist the controlled macro remediation review after the initial run.",
    )
    parser.add_argument(
        "--developer-remediation-dir",
        type=Path,
        default=(
            PROJECT_DIR.parent
            / "ifrs9-ecl-engine"
            / "reports"
            / "macro_remediation"
        ),
    )
    parser.add_argument(
        "--remediation-output-dir",
        type=Path,
        default=PROJECT_DIR / "reports" / "macro_remediation",
    )
    parser.add_argument(
        "--remediation-source-report-path",
        default=(
            "projects/model-validation-framework/reports/macro_remediation/"
            "macro_remediation_validation_report.md"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dsn:
        raise SystemExit(
            "A PostgreSQL DSN is required via --dsn or MODEL_VALIDATION_DATABASE_URL"
        )

    validation = run_macro_satellite_validation(
        args.developer_report_dir,
        args.output_dir,
    )
    remediation = None
    if args.persist_remediation:
        remediation = run_macro_remediation_validation(
            args.developer_remediation_dir,
            args.developer_report_dir,
            args.output_dir,
            args.remediation_output_dir,
        )
    metadata = MacroSatelliteRunMetadata(
        source_report_path=args.source_report_path,
        source_commit_sha=args.source_commit_sha,
    )
    with psycopg.connect(args.dsn) as connection:
        if args.apply_schema:
            schema = (PROJECT_DIR / "sql" / "schema.sql").read_text(encoding="utf-8")
            connection.execute(schema)
        macro_validation_run_id = persist_macro_satellite_result(
            connection,
            validation.result,
            metadata,
        )
        macro_remediation_run_id = None
        if remediation is not None:
            macro_remediation_run_id = persist_macro_remediation_result(
                connection,
                macro_validation_run_id,
                remediation.result,
                MacroRemediationRunMetadata(
                    source_report_path=args.remediation_source_report_path,
                    source_commit_sha=args.source_commit_sha,
                ),
            )
    print(f"Persisted macro_validation_run_id={macro_validation_run_id}")
    if macro_remediation_run_id is not None:
        print(f"Persisted macro_remediation_run_id={macro_remediation_run_id}")


if __name__ == "__main__":
    main()
