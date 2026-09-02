from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from model_validation.benchmarking import build_benchmark_comparison
from model_validation.calibration import build_calibration_by_decile, build_monthly_performance
from model_validation.metrics import PD_SCORE_COLUMNS, RAW_SCORE_COLUMNS, build_model_metrics
from model_validation.policy import ValidationPolicy
from model_validation.reporting import (
    build_model_limitations,
    build_validation_findings,
    build_validation_summary,
    write_validation_reports,
)
from model_validation.stability import build_stability_tables

REQUIRED_COLUMNS = {
    "customer_id",
    "observation_date",
    "actual_default",
    "selected_model",
    "selected_model_raw_pd",
    "logistic_regression_pd",
    "recalibrated_pd",
    "random_forest_pd",
}
AUDIT_CHECK_ORDER = (
    "row_count",
    "required_columns",
    "customer_id",
    "observation_date",
    "actual_default",
    "selected_model",
    "selected_model_raw_pd",
    "logistic_regression_pd",
    "recalibrated_pd",
    "random_forest_pd",
)
NORMALIZED_COLUMN_ORDER = (
    "customer_id",
    "observation_date",
    "actual_default",
    "selected_model",
    "selected_model_raw_pd",
    "logistic_regression_pd",
    "recalibrated_pd",
    "random_forest_pd",
)


@dataclass(frozen=True)
class ValidationResult:
    input_audit: pd.DataFrame
    model_metrics: pd.DataFrame
    calibration_by_decile: pd.DataFrame
    monthly_performance: pd.DataFrame
    stability_summary: pd.DataFrame
    stability_bins: pd.DataFrame
    benchmark_comparison: pd.DataFrame
    validation_summary: pd.DataFrame
    validation_findings: pd.DataFrame
    model_limitations: pd.DataFrame
    report_paths: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Project1OOTPredictionAdapter:
    prediction_path: str | Path
    data_context: str = "synthetic"

    def __post_init__(self) -> None:
        supported_contexts = {"synthetic", "public_lendingclub"}
        if self.data_context not in supported_contexts:
            supported = ", ".join(sorted(supported_contexts))
            raise ValueError(f"data_context must be one of: {supported}")

    def load(self) -> pd.DataFrame:
        path = Path(self.prediction_path)
        if not path.is_file():
            raise FileNotFoundError(f"Project 1 OOT prediction file not found: {path}")
        return pd.read_csv(path, dtype={"customer_id": "string"})


def run_validation(
    adapter: Project1OOTPredictionAdapter,
    *,
    policy: ValidationPolicy | None = None,
) -> ValidationResult:
    active_policy = policy or ValidationPolicy()
    normalized = load_validated_predictions(adapter)
    selected_model = str(normalized["selected_model"].iloc[0])

    input_audit = _build_input_audit(normalized)
    model_metrics = build_model_metrics(normalized, selected_model=selected_model)
    calibration_by_decile = build_calibration_by_decile(
        normalized,
        selected_model=selected_model,
        score_column="recalibrated_pd",
    )
    monthly_performance = build_monthly_performance(
        normalized,
        selected_model=selected_model,
        score_column="recalibrated_pd",
    )
    stability_summary, stability_bins = build_stability_tables(
        normalized,
        selected_model=selected_model,
        score_column="recalibrated_pd",
    )
    benchmark_comparison = build_benchmark_comparison(
        model_metrics,
        selected_model=selected_model,
    )
    validation_summary = build_validation_summary(
        model_metrics=model_metrics,
        stability_summary=stability_summary,
        benchmark_comparison=benchmark_comparison,
        selected_model=selected_model,
        policy=active_policy,
    )
    validation_findings = build_validation_findings(validation_summary)
    model_limitations = build_model_limitations(
        data_context=adapter.data_context,
        observation_start=normalized["observation_date"].min(),
        observation_end=normalized["observation_date"].max(),
    )

    return ValidationResult(
        input_audit=input_audit,
        model_metrics=model_metrics,
        calibration_by_decile=calibration_by_decile,
        monthly_performance=monthly_performance,
        stability_summary=stability_summary,
        stability_bins=stability_bins,
        benchmark_comparison=benchmark_comparison,
        validation_summary=validation_summary,
        validation_findings=validation_findings,
        model_limitations=model_limitations,
    )


def load_validated_predictions(adapter: Project1OOTPredictionAdapter) -> pd.DataFrame:
    """Load and validate the frozen Project 1 score contract."""
    return _validate_predictions(adapter.load())


def run_validation_pipeline(
    adapter: Project1OOTPredictionAdapter,
    output_dir: str | Path,
    *,
    policy: ValidationPolicy | None = None,
) -> ValidationResult:
    result = run_validation(adapter, policy=policy)
    report_paths = write_validation_reports(result, Path(output_dir))
    return replace(result, report_paths=report_paths)


def _validate_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty:
        raise ValueError("Project 1 OOT predictions must contain at least one row")

    missing_columns = sorted(REQUIRED_COLUMNS - set(predictions.columns))
    if missing_columns:
        raise ValueError(
            "Project 1 OOT predictions missing required columns: "
            + ", ".join(missing_columns)
        )

    normalized = predictions.loc[:, NORMALIZED_COLUMN_ORDER].copy()
    _validate_customer_id(normalized["customer_id"])
    normalized["observation_date"] = _validated_observation_date(normalized["observation_date"])
    normalized["actual_default"] = _validated_actual_default(normalized["actual_default"])
    normalized["selected_model"] = _validated_selected_model(normalized["selected_model"])

    for column in ["selected_model_raw_pd", *PD_SCORE_COLUMNS]:
        normalized[column] = _validated_pd_column(normalized[column], column)

    selected_model = str(normalized["selected_model"].iloc[0])
    selected_raw_column = RAW_SCORE_COLUMNS[selected_model]
    if not np.allclose(
        normalized["selected_model_raw_pd"].to_numpy(dtype=float),
        normalized[selected_raw_column].to_numpy(dtype=float),
        rtol=1e-10,
        atol=1e-10,
    ):
        raise ValueError(f"selected_model_raw_pd must match {selected_raw_column}")

    return normalized


def _validate_customer_id(customer_id: pd.Series) -> None:
    if (
        customer_id.isna().any()
        or not customer_id.map(lambda value: isinstance(value, str)).all()
        or customer_id.astype(str).str.strip().eq("").any()
    ):
        raise ValueError("customer_id must contain non-empty string values")
    if customer_id.duplicated().any():
        duplicate_ids = _duplicates(customer_id)
        raise ValueError("customer_id must be unique; duplicates: " + ", ".join(duplicate_ids))


def _validated_observation_date(observation_date: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(observation_date, errors="coerce", format="mixed")
    if parsed.isna().any():
        raise ValueError("observation_date must contain parseable dates")
    normalized = parsed.dt.normalize()
    if normalized.nunique() < 2:
        raise ValueError("observation_date must contain at least two distinct dates")
    return normalized


def _validated_actual_default(actual_default: pd.Series) -> pd.Series:
    parsed = pd.to_numeric(actual_default, errors="coerce")
    if parsed.isna().any() or (~parsed.isin([0, 1])).any():
        raise ValueError("actual_default must contain only binary 0/1 values")
    values = parsed.astype(int)
    if set(values.tolist()) != {0, 1}:
        raise ValueError("actual_default must contain both default classes")
    return values


def _validated_selected_model(selected_model: pd.Series) -> pd.Series:
    if selected_model.isna().any():
        raise ValueError("selected_model must contain exactly one supported model")
    normalized = selected_model.astype(str).str.strip()
    unique_models = sorted(normalized.unique().tolist())
    if len(unique_models) != 1 or unique_models[0] not in RAW_SCORE_COLUMNS:
        supported = ", ".join(sorted(RAW_SCORE_COLUMNS))
        raise ValueError(
            "selected_model must contain exactly one supported model "
            f"({supported})"
        )
    return normalized


def _validated_pd_column(values: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_numeric(values, errors="coerce")
    if not parsed.map(math.isfinite).all():
        raise ValueError(f"{column} must contain finite numeric values")
    if ((parsed < 0) | (parsed > 1)).any():
        raise ValueError(f"{column} must contain PD values between 0 and 1")
    return parsed.astype(float)


def _build_input_audit(predictions: pd.DataFrame) -> pd.DataFrame:
    details = {
        "row_count": f"{len(predictions)} rows loaded",
        "required_columns": ", ".join(NORMALIZED_COLUMN_ORDER),
        "customer_id": "unique non-empty customer IDs",
        "observation_date": (
            f"{predictions['observation_date'].min().date()} to "
            f"{predictions['observation_date'].max().date()}"
        ),
        "actual_default": "binary observed default flag with both classes present",
        "selected_model": (
            "one supported selected model: " f"{predictions['selected_model'].iloc[0]}"
        ),
        "selected_model_raw_pd": "matches selected model raw PD row-by-row",
        "logistic_regression_pd": "finite PD values in [0, 1]",
        "recalibrated_pd": "finite PD values in [0, 1]",
        "random_forest_pd": "finite PD values in [0, 1]",
    }
    return pd.DataFrame(
        [
            {
                "check": check,
                "status": "pass",
                "detail": details[check],
            }
            for check in AUDIT_CHECK_ORDER
        ]
    )


def _duplicates(values: pd.Series) -> list[str]:
    duplicate_values = values[values.duplicated()].drop_duplicates().astype(str)
    return sorted(duplicate_values.tolist())
