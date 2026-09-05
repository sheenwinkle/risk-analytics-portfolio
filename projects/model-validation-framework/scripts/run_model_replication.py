from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
PROJECT1_DIR = PROJECT_DIR.parent / "credit-risk-pd-model"
DEFAULT_VALIDATION_INPUTS = PROJECT1_DIR / "models" / "validation_inputs"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model_validation import Project1DevelopmentAdapter, run_model_replication_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently rebuild and reconcile Project 1 model candidates."
    )
    parser.add_argument(
        "--sample-path",
        default=DEFAULT_VALIDATION_INPUTS / "model_development_sample.csv",
        type=Path,
        help="Path to the local governed Project 1 development sample.",
    )
    parser.add_argument(
        "--specification-path",
        default=DEFAULT_VALIDATION_INPUTS / "model_development_spec.json",
        type=Path,
        help="Path to the Project 1 machine-readable model specification.",
    )
    parser.add_argument(
        "--selection-audit-path",
        default=PROJECT1_DIR / "reports" / "model_selection_audit.csv",
        type=Path,
        help="Path to the Project 1 candidate selection audit.",
    )
    parser.add_argument(
        "--parameter-reference-path",
        default=DEFAULT_VALIDATION_INPUTS / "model_parameter_reference.csv",
        type=Path,
        help="Path to the Project 1 fitted parameter reference.",
    )
    parser.add_argument(
        "--output-dir",
        default=PROJECT_DIR / "reports" / "replication",
        type=Path,
        help="Directory where aggregate replication evidence is written.",
    )
    args = parser.parse_args()

    run_model_replication_pipeline(
        Project1DevelopmentAdapter(
            sample_path=args.sample_path,
            specification_path=args.specification_path,
            selection_audit_path=args.selection_audit_path,
            parameter_reference_path=args.parameter_reference_path,
        ),
        args.output_dir,
    )
    print(f"Wrote independent model replication evidence to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
