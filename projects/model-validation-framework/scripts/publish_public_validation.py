from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model_validation.publication import publish_public_validation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish aggregate LendingClub validation evidence."
    )
    parser.add_argument("--source-reports", type=Path, required=True)
    parser.add_argument("--project1-lineage", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    publication = publish_public_validation(
        args.source_reports,
        args.project1_lineage,
        args.output_dir,
    )
    print(
        f"Published {len(publication.published_paths)} validation files to "
        f"{publication.output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
