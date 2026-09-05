from __future__ import annotations

import argparse
from pathlib import Path

import kagglehub

DATASET_HANDLE = "wordsforthewise/lending-club"
ACCEPTED_LOANS_FILE = "accepted_2007_to_2018Q4.csv.gz"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the public LendingClub accepted-loans file from Kaggle."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Git-ignored raw-data directory.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output_path = args.output_dir / ACCEPTED_LOANS_FILE
    if output_path.is_file() and not args.force:
        print(f"Using existing file: {output_path.resolve()}")
        return

    downloaded = kagglehub.dataset_download(
        DATASET_HANDLE,
        path=ACCEPTED_LOANS_FILE,
        output_dir=str(args.output_dir),
        force_download=args.force,
    )
    print(f"Downloaded: {Path(downloaded).resolve()}")


if __name__ == "__main__":
    main()
