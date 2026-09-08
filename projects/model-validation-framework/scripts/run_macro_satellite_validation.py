from __future__ import annotations

import argparse
from pathlib import Path

from model_validation.macro_satellite_demo import run_macro_satellite_validation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently validate the Australian macro satellite evidence."
    )
    parser.add_argument(
        "--developer-report-dir",
        type=Path,
        default=(
            REPO_ROOT
            / "projects"
            / "ifrs9-ecl-engine"
            / "reports"
            / "macro_satellite"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "macro_satellite",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = run_macro_satellite_validation(
        args.developer_report_dir,
        args.output_dir,
    )
    print(f"Opinion: {output.result.overall_opinion.upper()}")
    for name, path in output.report_paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
