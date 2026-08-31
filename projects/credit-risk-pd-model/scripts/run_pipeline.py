from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from credit_risk_pd.config import DEFAULT_CONFIG
from credit_risk_pd.pipeline import run_pd_modelling_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the credit risk PD modelling workflow.")
    parser.add_argument("--input", type=Path, default=None, help="Optional CSV input path.")
    parser.add_argument(
        "--reports",
        type=Path,
        default=Path("reports"),
        help="Report output folder.",
    )
    parser.add_argument("--models", type=Path, default=Path("models"), help="Model output folder.")
    parser.add_argument(
        "--oot-cutoff",
        default=DEFAULT_CONFIG.oot_cutoff_date,
        help="Out-of-time cutoff date. Defaults to the synthetic-data cutoff.",
    )
    parser.add_argument(
        "--calibration-fraction",
        type=float,
        default=DEFAULT_CONFIG.calibration_fraction,
        help="Fraction of pre-OOT rows reserved as the later calibration holdout.",
    )
    parser.add_argument(
        "--lgd",
        type=float,
        default=DEFAULT_CONFIG.lgd,
        help="Loss given default used in approval strategy expected-loss scenarios.",
    )
    parser.add_argument(
        "--approval-thresholds",
        type=float,
        nargs="+",
        default=DEFAULT_CONFIG.approval_thresholds,
        help="Fixed max-PD cutoffs used for approval scenario rows.",
    )
    parser.add_argument(
        "--classification-threshold",
        type=float,
        default=DEFAULT_CONFIG.test_threshold,
        help="Fixed threshold for precision, recall, accuracy, and confusion counts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_pd_modelling_workflow(
        input_path=args.input,
        output_dir=args.reports,
        model_dir=args.models,
        config=replace(
            DEFAULT_CONFIG,
            oot_cutoff_date=args.oot_cutoff,
            calibration_fraction=args.calibration_fraction,
            lgd=args.lgd,
            approval_thresholds=tuple(args.approval_thresholds),
            test_threshold=args.classification_threshold,
        ),
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

