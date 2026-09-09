from __future__ import annotations

import argparse
from pathlib import Path

from model_validation.macro_remediation_demo import run_macro_remediation_validation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]
IFRS9_REPORTS = REPO_ROOT / "projects" / "ifrs9-ecl-engine" / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently validate Australian macro satellite remediation."
    )
    parser.add_argument(
        "--developer-remediation-dir",
        type=Path,
        default=IFRS9_REPORTS / "macro_remediation",
    )
    parser.add_argument(
        "--incumbent-report-dir",
        type=Path,
        default=IFRS9_REPORTS / "macro_satellite",
    )
    parser.add_argument(
        "--initial-validation-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "macro_satellite",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "macro_remediation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = run_macro_remediation_validation(
        args.developer_remediation_dir,
        args.incumbent_report_dir,
        args.initial_validation_dir,
        args.output_dir,
    )
    closed = int(output.result.finding_lifecycle["closure_status"].eq("closed").sum())
    print(f"Opinion: {output.result.overall_opinion.upper()}")
    print(f"Closed findings: {closed}")
    for file_name, path in output.report_paths.items():
        print(f"{file_name}: {path}")


if __name__ == "__main__":
    main()
