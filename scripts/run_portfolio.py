from __future__ import annotations

import argparse
import csv
import io
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT / "projects"


@dataclass(frozen=True)
class PipelineStep:
    name: str
    project_dir: Path
    arguments: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all three risk analytics projects through one reproducible entry point."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".artifacts" / "portfolio-run",
        help="Root directory for generated project evidence.",
    )
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="Run Ruff and Pytest for each project before the pipelines.",
    )
    parser.add_argument(
        "--verify-committed",
        action="store_true",
        help=(
            "Require generated reports to match committed evidence after line-ending "
            "normalisation and machine-precision CSV tolerance."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    if args.with_tests:
        _run_project_checks()

    project1_reports = output_root / "credit-risk-pd-model" / "reports"
    project1_models = output_root / "credit-risk-pd-model" / "models"
    project2_reports = output_root / "ifrs9-ecl-engine" / "reports"
    project2_integration_reports = output_root / "ifrs9-ecl-engine" / "pd_integration"
    project3_reports = output_root / "model-validation-framework" / "reports"
    project3_remediation_reports = (
        output_root / "model-validation-framework" / "remediation"
    )

    steps = (
        PipelineStep(
            "Credit Risk PD modelling",
            PROJECT_ROOT / "credit-risk-pd-model",
            (
                "scripts/run_pipeline.py",
                "--reports",
                str(project1_reports),
                "--models",
                str(project1_models),
            ),
        ),
        PipelineStep(
            "IFRS 9 ECL synthetic demo",
            PROJECT_ROOT / "ifrs9-ecl-engine",
            ("scripts/run_pipeline.py", "--output-dir", str(project2_reports)),
        ),
        PipelineStep(
            "PD to ECL integration",
            PROJECT_ROOT / "ifrs9-ecl-engine",
            (
                "scripts/run_pd_integration.py",
                "--prediction-path",
                str(project1_reports / "oot_predictions.csv"),
                "--output-dir",
                str(project2_integration_reports),
            ),
        ),
        PipelineStep(
            "Independent model validation",
            PROJECT_ROOT / "model-validation-framework",
            (
                "scripts/run_validation.py",
                "--prediction-path",
                str(project1_reports / "oot_predictions.csv"),
                "--output-dir",
                str(project3_reports),
            ),
        ),
        PipelineStep(
            "Calibration remediation and finding lifecycle",
            PROJECT_ROOT / "model-validation-framework",
            (
                "scripts/run_remediation.py",
                "--prediction-path",
                str(project1_reports / "oot_predictions.csv"),
                "--output-dir",
                str(project3_remediation_reports),
            ),
        ),
    )
    for step in steps:
        _run(step.name, step.arguments, cwd=step.project_dir)

    generated_report_dirs = {
        "credit-risk-pd-model": project1_reports,
        "ifrs9-ecl-engine": project2_reports,
        "ifrs9-ecl-integration": project2_integration_reports,
        "model-validation-framework": project3_reports,
        "model-validation-remediation": project3_remediation_reports,
    }
    if args.verify_committed:
        _verify_committed_reports(generated_report_dirs)

    manifest = {
        name: sorted(path.name for path in report_dir.iterdir() if path.is_file())
        for name, report_dir in generated_report_dirs.items()
    }
    manifest_path = output_root / "portfolio_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Portfolio run complete: {manifest_path}")


def _run_project_checks() -> None:
    for project_name in (
        "credit-risk-pd-model",
        "ifrs9-ecl-engine",
        "model-validation-framework",
    ):
        project_dir = PROJECT_ROOT / project_name
        _run(
            f"Ruff: {project_name}",
            ("-m", "ruff", "check", "src", "tests", "scripts"),
            cwd=project_dir,
        )
        _run(
            f"Pytest: {project_name}",
            ("-m", "pytest", "-p", "no:cacheprovider", "-q"),
            cwd=project_dir,
        )


def _verify_committed_reports(generated_report_dirs: dict[str, Path]) -> None:
    committed_report_dirs = {
        "credit-risk-pd-model": PROJECT_ROOT / "credit-risk-pd-model" / "reports",
        "ifrs9-ecl-engine": PROJECT_ROOT / "ifrs9-ecl-engine" / "reports",
        "ifrs9-ecl-integration": (
            PROJECT_ROOT / "ifrs9-ecl-engine" / "reports" / "pd_integration"
        ),
        "model-validation-framework": PROJECT_ROOT / "model-validation-framework" / "reports",
        "model-validation-remediation": (
            PROJECT_ROOT / "model-validation-framework" / "reports" / "remediation"
        ),
    }
    mismatches = []
    for name, generated_dir in generated_report_dirs.items():
        committed_dir = committed_report_dirs[name]
        generated_files = {
            path.name: path for path in generated_dir.iterdir() if path.is_file()
        }
        committed_files = {
            path.name: path
            for path in committed_dir.iterdir()
            if path.is_file() and path.name in generated_files
        }
        if set(generated_files) != set(committed_files):
            mismatches.append(f"{name}: report file set differs")
            continue
        for filename, generated_path in generated_files.items():
            if not _reports_match(generated_path, committed_files[filename]):
                mismatches.append(f"{name}: {filename}")
    if mismatches:
        raise RuntimeError("Committed report drift detected: " + "; ".join(mismatches))
    print("Committed demo reports match regenerated evidence semantically.")


def _reports_match(generated_path: Path, committed_path: Path) -> bool:
    generated_text = _normalised_text(generated_path)
    committed_text = _normalised_text(committed_path)
    if generated_text == committed_text:
        return True
    if generated_path.suffix != ".csv":
        return False

    generated_rows = list(csv.reader(io.StringIO(generated_text)))
    committed_rows = list(csv.reader(io.StringIO(committed_text)))
    if len(generated_rows) != len(committed_rows):
        return False
    return all(
        len(generated_row) == len(committed_row)
        and all(
            _cells_match(generated_cell, committed_cell)
            for generated_cell, committed_cell in zip(generated_row, committed_row, strict=True)
        )
        for generated_row, committed_row in zip(generated_rows, committed_rows, strict=True)
    )


def _normalised_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _cells_match(generated: str, committed: str) -> bool:
    if generated == committed:
        return True
    try:
        generated_number = float(generated)
        committed_number = float(committed)
    except ValueError:
        return False
    if math.isnan(generated_number) and math.isnan(committed_number):
        return True
    return math.isclose(
        generated_number,
        committed_number,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def _run(name: str, arguments: tuple[str, ...], *, cwd: Path) -> None:
    print(f"\n[{name}]")
    subprocess.run([sys.executable, *arguments], cwd=cwd, check=True)


if __name__ == "__main__":
    main()
