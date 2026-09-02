from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model_validation import Project1OOTPredictionAdapter
from model_validation.remediation import (
    RemediationPolicy,
    run_calibration_remediation_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run no-look-ahead rolling calibration remediation and finding review."
    )
    parser.add_argument(
        "--prediction-path",
        type=Path,
        default=PROJECT_DIR.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv",
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "reports" / "remediation")
    parser.add_argument("--lookback-months", type=int, default=3)
    parser.add_argument("--initial-calibration-months", type=int, default=6)
    args = parser.parse_args()

    result = run_calibration_remediation_pipeline(
        Project1OOTPredictionAdapter(args.prediction_path),
        args.output_dir,
        remediation_policy=RemediationPolicy(
            lookback_months=args.lookback_months,
            initial_calibration_months=args.initial_calibration_months,
        ),
    )
    print(
        f"Wrote {len(result.report_paths)} remediation files to "
        f"{Path(args.output_dir).resolve()}"
    )


if __name__ == "__main__":
    main()
