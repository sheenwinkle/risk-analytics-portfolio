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

from model_validation.macro_satellite_demo import run_macro_satellite_validation
from model_validation.postgres import (
    MacroSatelliteRunMetadata,
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
    print(f"Persisted macro_validation_run_id={macro_validation_run_id}")


if __name__ == "__main__":
    main()
