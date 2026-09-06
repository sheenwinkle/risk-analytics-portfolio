from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ifrs9_ecl_engine.sicr_demo import run_sicr_rebuttal_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SICR rebuttal governance demo.")
    parser.add_argument(
        "--output-dir",
        default=PROJECT_DIR / "reports" / "sicr_rebuttal",
        type=Path,
        help="Directory where SICR rebuttal evidence is written.",
    )
    args = parser.parse_args()
    output = run_sicr_rebuttal_pipeline(args.output_dir)
    print(f"Wrote {len(output.report_paths)} report files to {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
