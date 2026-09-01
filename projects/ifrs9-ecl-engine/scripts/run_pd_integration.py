from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ifrs9_ecl_engine.pd_integration import run_pd_integration_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connect Project 1 recalibrated PD outputs to Project 2 ECL reports."
    )
    parser.add_argument(
        "--prediction-path",
        type=Path,
        default=REPO_ROOT
        / "projects"
        / "credit-risk-pd-model"
        / "reports"
        / "oot_predictions.csv",
        help="Path to Project 1 oot_predictions.csv.",
    )
    parser.add_argument(
        "--reporting-date",
        default=None,
        help="Optional YYYY-MM-DD observation_date cohort. Defaults to latest available.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=8,
        help="Number of evenly spaced accounts to sample from the selected PD cohort.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "reports" / "pd_integration",
        help="Directory where PD integration report artefacts are written.",
    )
    args = parser.parse_args()

    try:
        output = run_pd_integration_pipeline(
            prediction_path=args.prediction_path,
            reporting_date=args.reporting_date,
            sample_size=args.sample_size,
            output_dir=args.output_dir,
        )
    except (FileNotFoundError, TypeError, ValueError) as error:
        raise SystemExit(f"PD integration failed: {error}") from error

    print(
        "Wrote "
        f"{len(output.report_paths)} PD integration report files to "
        f"{Path(args.output_dir).resolve()}"
    )


if __name__ == "__main__":
    main()
