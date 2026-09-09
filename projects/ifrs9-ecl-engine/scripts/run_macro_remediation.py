from __future__ import annotations

import argparse
from pathlib import Path

from ifrs9_ecl_engine.macro_remediation_demo import run_macro_remediation_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run controlled remediation of the Australian macro satellite."
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "public" / "australia_macro_credit.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "macro_remediation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = run_macro_remediation_pipeline(args.data_path, args.output_dir)
    selection = output.remediation.selection.iloc[0]
    decision = output.remediation.governance_decision.iloc[0]
    print(f"Selected candidate: {selection['selected_candidate_id']}")
    print(f"Developer recommendation: {decision['developer_recommendation']}")
    for file_name, path in output.report_paths.items():
        print(f"{file_name}: {path}")


if __name__ == "__main__":
    main()
