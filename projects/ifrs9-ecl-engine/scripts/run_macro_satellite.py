from __future__ import annotations

import argparse
from pathlib import Path

from ifrs9_ecl_engine.macro_satellite_demo import run_macro_satellite_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the public Australian macro satellite and ECL A/B comparison."
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "public" / "australia_macro_credit.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "macro_satellite",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = run_macro_satellite_pipeline(args.data_path, args.output_dir)
    print(f"Selected alpha: {output.satellite.selected_alpha:.2f}")
    for name, path in output.report_paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
