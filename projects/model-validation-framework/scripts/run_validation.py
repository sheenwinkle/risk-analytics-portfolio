from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model_validation import Project1OOTPredictionAdapter, run_validation_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run independent validation metrics for Project 1 OOT PD predictions."
    )
    parser.add_argument(
        "--prediction-path",
        default=PROJECT_DIR.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv",
        type=Path,
        help="Path to Project 1 reports/oot_predictions.csv.",
    )
    parser.add_argument(
        "--output-dir",
        default=PROJECT_DIR / "reports",
        type=Path,
        help="Directory where validation report CSVs are written.",
    )
    parser.add_argument(
        "--data-context",
        choices=("synthetic", "public_lendingclub"),
        default="synthetic",
        help="Controls source-appropriate model limitations in the validation opinion.",
    )
    args = parser.parse_args()

    run_validation_pipeline(
        Project1OOTPredictionAdapter(args.prediction_path, data_context=args.data_context),
        args.output_dir,
    )
    print(f"Wrote validation reports to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
