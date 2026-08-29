from __future__ import annotations

import argparse
from pathlib import Path

from credit_risk_pd.pipeline import run_pd_modelling_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the credit risk PD modelling workflow.")
    parser.add_argument("--input", type=Path, default=None, help="Optional CSV input path.")
    parser.add_argument("--reports", type=Path, default=Path("reports"), help="Report output folder.")
    parser.add_argument("--models", type=Path, default=Path("models"), help="Model output folder.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_pd_modelling_workflow(
        input_path=args.input,
        output_dir=args.reports,
        model_dir=args.models,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

