from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ifrs9_ecl_engine.governance_demo import run_macro_overlay_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ECL macro sensitivity and management-overlay demo."
    )
    parser.add_argument(
        "--output-dir",
        default=PROJECT_DIR / "reports" / "macro_overlay",
        type=Path,
        help="Directory where governance report artefacts are written.",
    )
    args = parser.parse_args()
    output = run_macro_overlay_pipeline(args.output_dir)
    print(f"Wrote {len(output.report_paths)} report files to {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
