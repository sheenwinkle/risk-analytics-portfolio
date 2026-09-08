from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

PREDICTION_COLUMNS = {
    "quarter",
    "split",
    "actual_npl_ratio",
    "model_prediction",
    "persistence_prediction",
    "model_residual",
}
COEFFICIENT_COLUMNS = {
    "feature",
    "feature_role",
    "standardized_coefficient",
    "constraint",
}
TUNING_COLUMNS = {"alpha", "validation_mae", "validation_observations"}
SCENARIO_COLUMNS = {"scenario", "npl_multiplier", "evidence_use"}
EXPECTED_OOT_QUARTERS = pd.date_range("2019-03-31", "2021-12-31", freq="QE")


@dataclass(frozen=True)
class MacroSatelliteValidationResult:
    overall_opinion: str
    validation_summary: pd.DataFrame
    findings: pd.DataFrame
    replicated_performance: pd.DataFrame


def validate_macro_satellite(
    predictions: pd.DataFrame,
    coefficients: pd.DataFrame,
    tuning: pd.DataFrame,
    scenarios: pd.DataFrame,
    developer_performance: pd.DataFrame | None = None,
    *,
    real_time_vintage_evidenced: bool = False,
) -> MacroSatelliteValidationResult:
    """Independently recalculate satellite evidence and issue a use opinion."""
    if not isinstance(real_time_vintage_evidenced, bool):
        raise TypeError("real_time_vintage_evidenced must be boolean")
    normalized_predictions = _validate_predictions(predictions)
    normalized_coefficients = _validate_coefficients(coefficients)
    normalized_tuning = _validate_tuning(tuning)
    normalized_scenarios = _validate_scenarios(scenarios)
    replicated = _replicate_oot_performance(normalized_predictions)
    metrics = replicated.iloc[0]

    checks = [
        _check(
            "oot_observations",
            float(metrics["observations"]),
            12.0,
            "greater_than_or_equal",
            "pass" if metrics["observations"] >= 12 else "warning",
            "Frozen OOT sample should cover at least three years of quarters.",
        ),
        _check(
            "oot_mae_vs_persistence",
            float(metrics["mae_improvement_vs_persistence"]),
            0.0,
            "greater_than_or_equal",
            "pass" if metrics["mae_improvement_vs_persistence"] >= 0 else "fail",
            "A point-forecast challenger should not underperform a persistence benchmark.",
        ),
        _check(
            "oot_rmse_vs_persistence",
            float(metrics["rmse_improvement_vs_persistence"]),
            0.0,
            "greater_than_or_equal",
            "pass" if metrics["rmse_improvement_vs_persistence"] >= 0 else "fail",
            "The benchmark comparison is repeated with an error metric sensitive to misses.",
        ),
    ]

    scenario_index = normalized_scenarios.set_index("scenario")
    ordering_margin = min(
        float(scenario_index.loc["base", "npl_multiplier"])
        - float(scenario_index.loc["upside", "npl_multiplier"]),
        float(scenario_index.loc["downside", "npl_multiplier"])
        - float(scenario_index.loc["base", "npl_multiplier"]),
    )
    checks.append(
        _check(
            "scenario_directionality",
            ordering_margin,
            0.0,
            "greater_than",
            "pass" if ordering_margin > 0 else "fail",
            "Upside, base, and downside multipliers must increase with scenario severity.",
        )
    )

    minimum_coefficient = float(
        normalized_coefficients["standardized_coefficient"].min()
    )
    checks.append(
        _check(
            "coefficient_constraints",
            minimum_coefficient,
            0.0,
            "greater_than_or_equal",
            "pass" if minimum_coefficient >= -1e-12 else "fail",
            "The implemented coefficient signs must match the documented constraints.",
        )
    )
    macro_coefficients = normalized_coefficients[
        normalized_coefficients["feature_role"] == "macro_stress"
    ]
    active_macro_drivers = int(
        (macro_coefficients["standardized_coefficient"].abs() > 1e-12).sum()
    )
    active_status = "pass" if active_macro_drivers >= 2 else (
        "warning" if active_macro_drivers == 1 else "fail"
    )
    checks.append(
        _check(
            "active_macro_drivers",
            float(active_macro_drivers),
            2.0,
            "greater_than_or_equal",
            active_status,
            "Both pre-specified macro factors should retain incremental sensitivity.",
        )
    )

    selected_row = normalized_tuning.sort_values(["validation_mae", "alpha"]).iloc[0]
    alpha_at_boundary = math.isclose(
        float(selected_row["alpha"]),
        float(normalized_tuning["alpha"].min()),
    )
    checks.append(
        _check(
            "alpha_search_interior",
            0.0 if alpha_at_boundary else 1.0,
            1.0,
            "equal",
            "warning" if alpha_at_boundary else "pass",
            "An interior optimum provides stronger evidence that regularisation was bracketed.",
        )
    )
    checks.append(
        _check(
            "real_time_data_vintage",
            1.0 if real_time_vintage_evidenced else 0.0,
            1.0,
            "equal",
            "pass" if real_time_vintage_evidenced else "warning",
            (
                "Operational forecasting requires release-lag and historical-revision "
                "evidence for contemporaneous macro factors."
            ),
        )
    )

    reconciliation_failed = False
    if developer_performance is not None:
        reconciliation_gap = _developer_reconciliation_gap(
            developer_performance,
            replicated,
        )
        reconciliation_failed = reconciliation_gap > 1e-8
        checks.append(
            _check(
                "developer_metric_reconciliation",
                reconciliation_gap,
                1e-8,
                "less_than_or_equal",
                "fail" if reconciliation_failed else "pass",
                "Independent metrics must reconcile to the developer report.",
            )
        )

    summary = pd.DataFrame(checks)
    findings = _build_findings(
        benchmark_failed=(
            metrics["mae_improvement_vs_persistence"] < 0
            or metrics["rmse_improvement_vs_persistence"] < 0
        ),
        active_macro_drivers=active_macro_drivers,
        real_time_vintage_evidenced=real_time_vintage_evidenced,
        reconciliation_failed=reconciliation_failed,
    )
    overall_opinion = _overall_opinion(summary)
    return MacroSatelliteValidationResult(
        overall_opinion=overall_opinion,
        validation_summary=summary,
        findings=findings,
        replicated_performance=replicated,
    )


def _validate_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, PREDICTION_COLUMNS, "predictions")
    normalized = frame.copy()
    normalized["quarter"] = pd.to_datetime(normalized["quarter"], errors="coerce")
    if normalized["quarter"].isna().any() or normalized["quarter"].duplicated().any():
        raise ValueError("Prediction quarters must be valid and unique")
    oot = normalized[normalized["split"] == "oot"].sort_values("quarter").copy()
    if oot.empty:
        raise ValueError("Predictions must contain an oot split")
    if list(oot["quarter"]) != list(EXPECTED_OOT_QUARTERS):
        raise ValueError("Predictions must preserve the frozen 2019-2021 OOT window")
    if (oot["quarter"] >= "2022-03-31").any():
        raise ValueError("OOT predictions cross the APS 220 reporting break")
    numeric_columns = [
        "actual_npl_ratio",
        "model_prediction",
        "persistence_prediction",
        "model_residual",
    ]
    for column in numeric_columns:
        oot[column] = pd.to_numeric(oot[column], errors="coerce")
        if not np.isfinite(oot[column].to_numpy()).all():
            raise ValueError(f"predictions.{column} must be finite")
    expected_residual = oot["actual_npl_ratio"] - oot["model_prediction"]
    if not np.allclose(oot["model_residual"], expected_residual, atol=1e-8, rtol=0.0):
        raise ValueError("model_residual does not reconcile to actual minus prediction")
    return normalized


def _validate_coefficients(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, COEFFICIENT_COLUMNS, "coefficients")
    normalized = frame.copy()
    normalized["standardized_coefficient"] = pd.to_numeric(
        normalized["standardized_coefficient"],
        errors="coerce",
    )
    if not np.isfinite(normalized["standardized_coefficient"].to_numpy()).all():
        raise ValueError("Coefficient values must be finite")
    if normalized["feature"].duplicated().any():
        raise ValueError("Coefficient features must be unique")
    return normalized


def _validate_tuning(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, TUNING_COLUMNS, "tuning")
    normalized = frame.copy()
    for column in ["alpha", "validation_mae", "validation_observations"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column].to_numpy()).all():
            raise ValueError(f"tuning.{column} must be finite")
    if (normalized["alpha"] <= 0).any() or normalized["alpha"].duplicated().any():
        raise ValueError("Tuning alpha values must be positive and unique")
    return normalized


def _validate_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, SCENARIO_COLUMNS, "scenarios")
    normalized = frame.copy()
    if len(normalized) != 3 or normalized["scenario"].duplicated().any():
        raise ValueError("Scenarios must contain upside, base, and downside exactly once")
    if set(normalized["scenario"]) != {"upside", "base", "downside"}:
        raise ValueError("Scenarios must contain upside, base, and downside exactly once")
    normalized["npl_multiplier"] = pd.to_numeric(
        normalized["npl_multiplier"],
        errors="coerce",
    )
    if not np.isfinite(normalized["npl_multiplier"].to_numpy()).all():
        raise ValueError("Scenario multipliers must be finite")
    base = float(
        normalized.loc[normalized["scenario"] == "base", "npl_multiplier"].iloc[0]
    )
    if not math.isclose(base, 1.0, abs_tol=1e-8):
        raise ValueError("Base scenario multiplier must equal 1")
    if set(normalized["evidence_use"]) != {"sensitivity_only"}:
        raise ValueError("Scenario evidence must be restricted to sensitivity_only")
    return normalized


def _replicate_oot_performance(predictions: pd.DataFrame) -> pd.DataFrame:
    oot = predictions[predictions["split"] == "oot"].sort_values("quarter")
    actual = oot["actual_npl_ratio"].to_numpy(dtype=float)
    model = oot["model_prediction"].to_numpy(dtype=float)
    persistence = oot["persistence_prediction"].to_numpy(dtype=float)
    model_mae = _mae(actual, model)
    persistence_mae = _mae(actual, persistence)
    model_rmse = _rmse(actual, model)
    persistence_rmse = _rmse(actual, persistence)
    return pd.DataFrame(
        [
            {
                "split": "oot",
                "observations": len(oot),
                "period_start": oot["quarter"].min(),
                "period_end": oot["quarter"].max(),
                "model_mae": model_mae,
                "persistence_mae": persistence_mae,
                "mae_improvement_vs_persistence": _improvement(
                    model_mae,
                    persistence_mae,
                ),
                "model_rmse": model_rmse,
                "persistence_rmse": persistence_rmse,
                "rmse_improvement_vs_persistence": _improvement(
                    model_rmse,
                    persistence_rmse,
                ),
                "residual_lag1_autocorrelation": float(
                    oot["model_residual"].autocorr(lag=1)
                ),
            }
        ]
    )


def _developer_reconciliation_gap(
    developer_performance: pd.DataFrame,
    replicated: pd.DataFrame,
) -> float:
    required = {
        "split",
        "model_mae",
        "persistence_mae",
        "model_rmse",
        "persistence_rmse",
    }
    _require_columns(developer_performance, required, "developer_performance")
    oot = developer_performance[developer_performance["split"] == "oot"]
    if len(oot) != 1:
        raise ValueError("Developer performance must contain exactly one oot row")
    developer = oot.iloc[0]
    independent = replicated.iloc[0]
    return max(
        abs(float(developer[column]) - float(independent[column]))
        for column in ["model_mae", "persistence_mae", "model_rmse", "persistence_rmse"]
    )


def _build_findings(
    *,
    benchmark_failed: bool,
    active_macro_drivers: int,
    real_time_vintage_evidenced: bool,
    reconciliation_failed: bool,
) -> pd.DataFrame:
    rows = []
    if benchmark_failed:
        rows.append(
            {
                "finding_id": "MSV-001",
                "severity": "high",
                "title": "Satellite underperforms persistence benchmark",
                "status": "open",
                "use_restriction": "sensitivity_only",
                "required_action": (
                    "Test alternative horizons, targets, and dynamic specifications; "
                    "repeat frozen OOT validation before point-forecast use."
                ),
            }
        )
    if active_macro_drivers < 2:
        rows.append(
            {
                "finding_id": "MSV-002",
                "severity": "moderate",
                "title": "Pre-specified unemployment factor is inactive",
                "status": "open",
                "use_restriction": "sensitivity_only",
                "required_action": (
                    "Investigate factor form, lags, collinearity, and segment-level targets "
                    "without forcing a non-zero coefficient."
                ),
            }
        )
    if not real_time_vintage_evidenced:
        rows.append(
            {
                "finding_id": "MSV-003",
                "severity": "moderate",
                "title": "Real-time macro data availability is not evidenced",
                "status": "open",
                "use_restriction": "sensitivity_only",
                "required_action": (
                    "Reconstruct release-date vintages or lag macro factors; test data "
                    "revision sensitivity before operational forecasting."
                ),
            }
        )
    if reconciliation_failed:
        rows.append(
            {
                "finding_id": "MSV-004",
                "severity": "high",
                "title": "Developer metrics do not independently reconcile",
                "status": "open",
                "use_restriction": "blocked",
                "required_action": "Resolve the evidence mismatch and rerun independent validation.",
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "finding_id",
            "severity",
            "title",
            "status",
            "use_restriction",
            "required_action",
        ],
    )


def _overall_opinion(summary: pd.DataFrame) -> str:
    statuses = set(summary["status"])
    if "fail" in statuses:
        return "restricted"
    if "warning" in statuses:
        return "conditional"
    return "acceptable"


def _check(
    check: str,
    metric_value: float,
    threshold: float,
    direction: str,
    status: str,
    rationale: str,
) -> dict[str, object]:
    return {
        "check": check,
        "metric_value": metric_value,
        "threshold": threshold,
        "direction": direction,
        "status": status,
        "rationale": rationale,
    }


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing required columns: " + ", ".join(sorted(missing)))


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(actual - predicted))))


def _improvement(model_error: float, benchmark_error: float) -> float:
    if benchmark_error == 0:
        return 0.0
    return (benchmark_error - model_error) / benchmark_error
