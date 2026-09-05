from __future__ import annotations

import argparse
from pathlib import Path

from credit_risk_pd.publication import publish_public_lendingclub_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish aggregate LendingClub evidence without borrower-level predictions."
    )
    parser.add_argument("--source-reports", type=Path, required=True)
    parser.add_argument("--ingestion-audit", type=Path, required=True)
    parser.add_argument("--vintage-resolution", type=Path, required=True)
    parser.add_argument("--raw-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    publication = publish_public_lendingclub_run(
        source_report_dir=args.source_reports,
        ingestion_audit_path=args.ingestion_audit,
        vintage_resolution_path=args.vintage_resolution,
        raw_input_path=args.raw_input,
        output_dir=args.output_dir,
    )
    print(
        f"Published {len(publication.published_paths)} aggregate evidence files to "
        f"{publication.output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
