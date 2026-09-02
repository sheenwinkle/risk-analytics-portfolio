from __future__ import annotations

import argparse
from pathlib import Path

from credit_risk_pd.lendingclub import prepare_lendingclub_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare LendingClub accepted-loans CSV or CSV.GZ for the PD pipeline."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Raw accepted-loans CSV or CSV.GZ.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Canonical processed CSV path.")
    parser.add_argument(
        "--audit",
        type=Path,
        required=True,
        help="One-row ingestion audit CSV path.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row limit for smoke tests.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = prepare_lendingclub_data(
        input_path=args.input,
        output_path=args.output,
        audit_path=args.audit,
        max_rows=args.max_rows,
    )
    print(f"output: {result.output_path}")
    print(f"audit: {result.audit_path}")


if __name__ == "__main__":
    main()
