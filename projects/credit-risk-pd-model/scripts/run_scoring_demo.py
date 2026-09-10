from __future__ import annotations

import argparse
from pathlib import Path

from credit_risk_pd.scoring_demo import SCORING_DATA_CONTEXTS, run_scoring_service_demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay frozen OOT applications through the governed PD scoring service."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("models/deployment_manifest.json"),
        help="Deployment manifest; its sibling model artifact is loaded and verified.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("reports/oot_predictions.csv"),
        help="Frozen OOT prediction file containing the scoring inputs and offline PD.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/scoring"),
        help="Directory for aggregate-only scoring evidence.",
    )
    parser.add_argument(
        "--data-context",
        choices=sorted(SCORING_DATA_CONTEXTS),
        default="synthetic_demo",
        help="Dataset context recorded in the reconciliation evidence.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = run_scoring_service_demo(
        manifest_path=args.manifest,
        prediction_path=args.predictions,
        output_dir=args.output_dir,
        data_context=args.data_context,
    )
    reconciliation = output.reconciliation.iloc[0]
    print(
        "Scoring replay complete: "
        f"{int(reconciliation['records_replayed'])} records across "
        f"{int(reconciliation['batches_scored'])} batches; "
        f"max PD delta={reconciliation['maximum_absolute_pd_delta']:.2e}; "
        f"reports={Path(args.output_dir).resolve()}"
    )


if __name__ == "__main__":
    main()
