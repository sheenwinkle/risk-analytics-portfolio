from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

EXPECTED_OOT_QUARTERS = pd.date_range("2019-03-31", "2021-12-31", freq="QE")
METRIC_RECONCILIATION_TOLERANCE = 1e-7


@dataclass(frozen=True)
class MacroRemediationValidationResult:
    overall_opinion: str
    validation_summary: pd.DataFrame
    selection_reperformance: pd.DataFrame
    replicated_performance: pd.DataFrame
    finding_lifecycle: pd.DataFrame


def validate_macro_remediation(
    candidate_register: pd.DataFrame,
    tuning: pd.DataFrame,
    selected_model: dict[str, Any],
    coefficients: pd.DataFrame,
    predictions: pd.DataFrame,
    developer_comparison: pd.DataFrame,
    developer_governance: pd.DataFrame,
    incumbent_predictions: pd.DataFrame,
    initial_findings: pd.DataFrame,
    *,
    real_time_vintage_evidenced: bool = False,
) -> MacroRemediationValidationResult:
    """Reperform macro remediation evidence without calling developer model code."""
    if not isinstance(real_time_vintage_evidenced, bool):
        raise TypeError("real_time_vintage_evidenced must be boolean")
    candidates = _validate_candidates(candidate_register)
    normalized_tuning = _validate_tuning(tuning, candidates)
    model = _validate_selected_model(selected_model)
    normalized_coefficients = _validate_coefficients(coefficients, model)
    normalized_predictions = _validate_predictions(predictions, model)
    normalized_incumbent = _validate_incumbent_predictions(incumbent_predictions)
    normalized_comparison = _validate_developer_comparison(developer_comparison)
    normalized_governance = _validate_developer_governance(developer_governance)
    findings = _validate_initial_findings(initial_findings)

    selection_reperformance = _reperform_selection(normalized_tuning, model)
    replicated_performance = pd.concat(
        [
            _replicate_performance(normalized_incumbent, "incumbent_satellite"),
            _replicate_performance(normalized_predictions, "selected_remediation"),
        ],
        ignore_index=True,
    )
    challenger = replicated_performance.set_index("variant").loc[
        "selected_remediation"
    ]
    comparison_gap = _comparison_reconciliation_gap(
        normalized_comparison,
        replicated_performance,
    )

    lag_violations = int(
        (
            candidates["macro_lag_quarters"]
            < candidates["forecast_horizon_quarters"]
        ).sum()
        + (~candidates["release_compatible"]).sum()
    )
    coefficient_minimum = float(
        normalized_coefficients["standardized_coefficient"].min()
    )
    active_macro_drivers = int(
        (
            normalized_coefficients.loc[
                normalized_coefficients["feature_role"].eq("macro_stress"),
                "standardized_coefficient",
            ].abs()
            > 1e-12
        ).sum()
    )
    selection_row = selection_reperformance.iloc[0]
    timing_violations = _prediction_timing_violations(normalized_predictions)
    oot_excluded = (
        not model["oot_used_for_selection"]
        and model["selection_window"] == "2016Q1-2018Q4"
        and model["oot_evidence_freshness"] == "reused_2019Q1_2021Q4"
    )
    closure_controlled = (
        not bool(normalized_governance.loc[0, "finding_closure_claimed"])
        and normalized_governance.loc[0, "developer_recommendation"]
        == "retain_restricted_use"
        and normalized_governance.loc[0, "use_restriction"] == "sensitivity_only"
    )
    registration_reconciled = (
        len(candidates) == model["eligible_candidates"]
        and candidates["candidate_id"].nunique() == len(candidates)
        and candidates["eligible_for_selection"].all()
    )

    checks = [
        _check(
            "candidate_registration",
            float(len(candidates)),
            float(model["eligible_candidates"]),
            "equal",
            "pass" if registration_reconciled else "fail",
            "The independent review must receive the complete pre-registered candidate set.",
        ),
        _check(
            "release_lag_compatibility",
            float(lag_violations),
            0.0,
            "equal",
            "pass" if lag_violations == 0 else "fail",
            "Every eligible macro input must be available by its forecast origin.",
        ),
        _check(
            "selection_reperformance",
            1.0 if bool(selection_row["selection_reconciled"]) else 0.0,
            1.0,
            "equal",
            "pass" if bool(selection_row["selection_reconciled"]) else "fail",
            "Independent sorting and score arithmetic must reproduce the selected row.",
        ),
        _check(
            "oot_selection_exclusion",
            1.0 if oot_excluded else 0.0,
            1.0,
            "equal",
            "pass" if oot_excluded else "fail",
            "The reused OOT period must not determine the candidate or alpha.",
        ),
        _check(
            "prediction_timing",
            float(timing_violations),
            0.0,
            "equal",
            "pass" if timing_violations == 0 else "fail",
            "Each prediction must preserve its declared forecast horizon.",
        ),
        _check(
            "coefficient_constraints",
            coefficient_minimum,
            0.0,
            "greater_than_or_equal",
            "pass" if coefficient_minimum >= -1e-12 else "fail",
            "Selected challenger coefficients must retain the declared nonnegative signs.",
        ),
        _check(
            "active_macro_drivers",
            float(active_macro_drivers),
            2.0,
            "greater_than_or_equal",
            "pass" if active_macro_drivers >= 2 else "warning",
            "Both macro drivers should retain incremental sensitivity after remediation.",
        ),
        _check(
            "developer_metric_reconciliation",
            comparison_gap,
            METRIC_RECONCILIATION_TOLERANCE,
            "less_than_or_equal",
            (
                "pass"
                if comparison_gap <= METRIC_RECONCILIATION_TOLERANCE
                else "fail"
            ),
            "Developer OOT claims must reconcile to independently recalculated errors.",
        ),
        _check(
            "oot_mae_vs_persistence",
            float(challenger["mae_improvement_vs_persistence"]),
            0.0,
            "greater_than_or_equal",
            (
                "pass"
                if challenger["mae_improvement_vs_persistence"] >= 0
                else "fail"
            ),
            "The remediated point forecast should not underperform persistence on MAE.",
        ),
        _check(
            "oot_rmse_vs_persistence",
            float(challenger["rmse_improvement_vs_persistence"]),
            0.0,
            "greater_than_or_equal",
            (
                "pass"
                if challenger["rmse_improvement_vs_persistence"] >= 0
                else "fail"
            ),
            "The remediated point forecast should not underperform persistence on RMSE.",
        ),
        _check(
            "fresh_oot_closure_evidence",
            0.0,
            1.0,
            "equal",
            "fail",
            "The 2019-2021 outcomes were already observed and cannot close a finding.",
        ),
        _check(
            "developer_closure_control",
            1.0 if closure_controlled else 0.0,
            1.0,
            "equal",
            "pass" if closure_controlled else "fail",
            "Developer evidence must retain restricted use and make no closure claim.",
        ),
        _check(
            "real_time_data_vintage",
            1.0 if real_time_vintage_evidenced else 0.0,
            1.0,
            "equal",
            "pass" if real_time_vintage_evidenced else "warning",
            "Lagging addresses availability, but historical revision sensitivity remains.",
        ),
    ]
    validation_summary = pd.DataFrame(checks)
    finding_lifecycle = _build_finding_lifecycle(
        findings,
        challenger,
        active_macro_drivers,
        lag_violations,
        real_time_vintage_evidenced,
    )
    return MacroRemediationValidationResult(
        overall_opinion=_overall_opinion(validation_summary, finding_lifecycle),
        validation_summary=validation_summary,
        selection_reperformance=selection_reperformance,
        replicated_performance=replicated_performance,
        finding_lifecycle=finding_lifecycle,
    )


def _validate_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "candidate_id",
        "forecast_horizon_quarters",
        "macro_lag_quarters",
        "release_compatible",
        "eligible_for_selection",
    }
    _require_columns(frame, required, "candidate_register")
    normalized = frame.copy()
    if normalized.empty or normalized["candidate_id"].duplicated().any():
        raise ValueError("Candidate IDs must be non-empty and unique")
    for column in ["forecast_horizon_quarters", "macro_lag_quarters"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column].to_numpy()).all():
            raise ValueError(f"candidate_register.{column} must be finite")
    for column in ["release_compatible", "eligible_for_selection"]:
        normalized[column] = normalized[column].map(_to_bool)
    return normalized


def _validate_tuning(
    frame: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "candidate_id",
        "forecast_horizon_quarters",
        "feature_count",
        "alpha",
        "validation_observations",
        "validation_model_mae",
        "validation_persistence_mae",
        "validation_mae_ratio",
        "validation_model_rmse",
        "validation_persistence_rmse",
        "validation_rmse_ratio",
        "selection_score",
        "selected",
    }
    _require_columns(frame, required, "candidate_tuning")
    normalized = frame.copy()
    numeric = required - {"candidate_id", "selected"}
    for column in numeric:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column].to_numpy()).all():
            raise ValueError(f"candidate_tuning.{column} must be finite")
    normalized["selected"] = normalized["selected"].map(_to_bool)
    if not set(normalized["candidate_id"]).issubset(set(candidates["candidate_id"])):
        raise ValueError("Tuning contains a candidate outside the registered set")
    if normalized.duplicated(["candidate_id", "alpha"]).any():
        raise ValueError("Candidate-alpha tuning rows must be unique")
    if (normalized["alpha"] <= 0).any() or normalized["selected"].sum() != 1:
        raise ValueError("Tuning must contain one selected positive-alpha row")
    return normalized


def _validate_selected_model(model: dict[str, Any]) -> dict[str, Any]:
    required = {
        "candidate_id",
        "eligible_candidates",
        "oot_evidence_freshness",
        "oot_used_for_selection",
        "selected_alpha",
        "selection_window",
    }
    missing = required - set(model)
    if missing:
        raise ValueError("selected_model missing fields: " + ", ".join(sorted(missing)))
    normalized = dict(model)
    normalized["oot_used_for_selection"] = _to_bool(
        normalized["oot_used_for_selection"]
    )
    normalized["eligible_candidates"] = int(normalized["eligible_candidates"])
    normalized["selected_alpha"] = float(normalized["selected_alpha"])
    return normalized


def _validate_coefficients(
    frame: pd.DataFrame,
    selected_model: dict[str, Any],
) -> pd.DataFrame:
    required = {
        "candidate_id",
        "feature",
        "feature_role",
        "standardized_coefficient",
        "constraint",
    }
    _require_columns(frame, required, "selected_coefficients")
    normalized = frame.copy()
    if set(normalized["candidate_id"]) != {selected_model["candidate_id"]}:
        raise ValueError("Coefficients do not belong to the selected candidate")
    if normalized["feature"].duplicated().any():
        raise ValueError("Coefficient features must be unique")
    normalized["standardized_coefficient"] = pd.to_numeric(
        normalized["standardized_coefficient"], errors="coerce"
    )
    if not np.isfinite(normalized["standardized_coefficient"].to_numpy()).all():
        raise ValueError("Coefficient values must be finite")
    return normalized


def _validate_predictions(
    frame: pd.DataFrame,
    selected_model: dict[str, Any],
) -> pd.DataFrame:
    required = {
        "quarter",
        "forecast_origin_quarter",
        "split",
        "candidate_id",
        "forecast_horizon_quarters",
        "actual_npl_ratio",
        "model_prediction",
        "persistence_prediction",
        "model_residual",
    }
    _require_columns(frame, required, "frozen_predictions")
    normalized = frame.copy()
    for column in ["quarter", "forecast_origin_quarter"]:
        normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
        if normalized[column].isna().any():
            raise ValueError(f"frozen_predictions.{column} must contain valid dates")
    if normalized["quarter"].duplicated().any():
        raise ValueError("Prediction quarters must be unique")
    if set(normalized["candidate_id"]) != {selected_model["candidate_id"]}:
        raise ValueError("Predictions do not belong to the selected candidate")
    for column in [
        "forecast_horizon_quarters",
        "actual_npl_ratio",
        "model_prediction",
        "persistence_prediction",
        "model_residual",
    ]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column].to_numpy()).all():
            raise ValueError(f"frozen_predictions.{column} must be finite")
    residual = normalized["actual_npl_ratio"] - normalized["model_prediction"]
    if not np.allclose(normalized["model_residual"], residual, atol=1e-8, rtol=0.0):
        raise ValueError("Remediation residuals do not reconcile")
    _validate_oot_window(normalized, "Remediation predictions")
    return normalized


def _validate_incumbent_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "quarter",
        "split",
        "actual_npl_ratio",
        "model_prediction",
        "persistence_prediction",
    }
    _require_columns(frame, required, "incumbent_predictions")
    normalized = frame.copy()
    normalized["quarter"] = pd.to_datetime(normalized["quarter"], errors="coerce")
    if normalized["quarter"].isna().any():
        raise ValueError("Incumbent prediction quarters must be valid")
    for column in [
        "actual_npl_ratio",
        "model_prediction",
        "persistence_prediction",
    ]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column].to_numpy()).all():
            raise ValueError(f"incumbent_predictions.{column} must be finite")
    _validate_oot_window(normalized, "Incumbent predictions")
    return normalized


def _validate_developer_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "variant",
        "model_mae",
        "persistence_mae",
        "mae_improvement_vs_persistence",
        "model_rmse",
        "persistence_rmse",
        "rmse_improvement_vs_persistence",
    }
    _require_columns(frame, required, "oot_comparison")
    normalized = frame.copy()
    if set(normalized["variant"]) != {
        "incumbent_satellite",
        "selected_remediation",
    }:
        raise ValueError("OOT comparison must contain incumbent and remediation rows")
    for column in required - {"variant"}:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not np.isfinite(normalized[column].to_numpy()).all():
            raise ValueError(f"oot_comparison.{column} must be finite")
    return normalized


def _validate_developer_governance(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "developer_recommendation",
        "use_restriction",
        "evidence_freshness",
        "finding_closure_claimed",
    }
    _require_columns(frame, required, "governance_decision")
    if len(frame) != 1:
        raise ValueError("Developer governance decision must contain exactly one row")
    normalized = frame.copy()
    normalized["finding_closure_claimed"] = normalized[
        "finding_closure_claimed"
    ].map(_to_bool)
    return normalized


def _validate_initial_findings(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"finding_id", "severity", "title", "status", "required_action"}
    _require_columns(frame, required, "initial_findings")
    normalized = frame.copy()
    required_ids = {"MSV-001", "MSV-002", "MSV-003"}
    if not required_ids.issubset(set(normalized["finding_id"])):
        raise ValueError("Initial macro findings must include MSV-001 through MSV-003")
    if normalized["finding_id"].duplicated().any():
        raise ValueError("Initial macro finding IDs must be unique")
    return normalized[normalized["finding_id"].isin(required_ids)].copy()


def _reperform_selection(
    tuning: pd.DataFrame,
    selected_model: dict[str, Any],
) -> pd.DataFrame:
    recalculated_mae_ratio = (
        tuning["validation_model_mae"] / tuning["validation_persistence_mae"]
    )
    recalculated_rmse_ratio = (
        tuning["validation_model_rmse"] / tuning["validation_persistence_rmse"]
    )
    recalculated_score = 0.5 * (
        recalculated_mae_ratio + recalculated_rmse_ratio
    )
    arithmetic_gap = float(
        np.max(
            np.abs(tuning["validation_mae_ratio"] - recalculated_mae_ratio)
            .to_numpy()
            .tolist()
            + np.abs(tuning["validation_rmse_ratio"] - recalculated_rmse_ratio)
            .to_numpy()
            .tolist()
            + np.abs(tuning["selection_score"] - recalculated_score)
            .to_numpy()
            .tolist()
        )
    )
    ranked = tuning.assign(selection_score=recalculated_score).sort_values(
        [
            "selection_score",
            "validation_model_mae",
            "feature_count",
            "forecast_horizon_quarters",
            "candidate_id",
            "alpha",
        ],
        kind="mergesort",
    )
    reperformed = ranked.iloc[0]
    developer_selected = tuning.loc[tuning["selected"]].iloc[0]
    reconciled = (
        arithmetic_gap <= 1e-8
        and reperformed["candidate_id"] == selected_model["candidate_id"]
        and math.isclose(
            float(reperformed["alpha"]),
            float(selected_model["selected_alpha"]),
        )
        and developer_selected["candidate_id"] == reperformed["candidate_id"]
        and math.isclose(
            float(developer_selected["alpha"]),
            float(reperformed["alpha"]),
        )
    )
    return pd.DataFrame(
        [
            {
                "developer_candidate_id": str(selected_model["candidate_id"]),
                "developer_alpha": float(selected_model["selected_alpha"]),
                "reperformed_candidate_id": str(reperformed["candidate_id"]),
                "reperformed_alpha": float(reperformed["alpha"]),
                "reperformed_selection_score": float(reperformed["selection_score"]),
                "maximum_arithmetic_gap": arithmetic_gap,
                "selection_reconciled": bool(reconciled),
            }
        ]
    )


def _replicate_performance(frame: pd.DataFrame, variant: str) -> pd.DataFrame:
    oot = frame[frame["split"] == "oot"].sort_values("quarter")
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
                "variant": variant,
                "observations": len(oot),
                "period_start": oot["quarter"].min(),
                "period_end": oot["quarter"].max(),
                "model_mae": model_mae,
                "persistence_mae": persistence_mae,
                "mae_improvement_vs_persistence": (
                    persistence_mae - model_mae
                )
                / persistence_mae,
                "model_rmse": model_rmse,
                "persistence_rmse": persistence_rmse,
                "rmse_improvement_vs_persistence": (
                    persistence_rmse - model_rmse
                )
                / persistence_rmse,
            }
        ]
    )


def _comparison_reconciliation_gap(
    developer: pd.DataFrame,
    independent: pd.DataFrame,
) -> float:
    columns = [
        "model_mae",
        "persistence_mae",
        "mae_improvement_vs_persistence",
        "model_rmse",
        "persistence_rmse",
        "rmse_improvement_vs_persistence",
    ]
    developer_index = developer.set_index("variant")
    independent_index = independent.set_index("variant")
    return max(
        abs(float(developer_index.loc[variant, column]) - float(row[column]))
        for variant, row in independent_index.iterrows()
        for column in columns
    )


def _prediction_timing_violations(predictions: pd.DataFrame) -> int:
    target_quarters = predictions["quarter"].dt.to_period("Q").astype("int64")
    origin_quarters = predictions["forecast_origin_quarter"].dt.to_period("Q").astype(
        "int64"
    )
    actual_horizon = target_quarters - origin_quarters
    return int((actual_horizon != predictions["forecast_horizon_quarters"]).sum())


def _build_finding_lifecycle(
    initial_findings: pd.DataFrame,
    challenger: pd.Series,
    active_macro_drivers: int,
    lag_violations: int,
    real_time_vintage_evidenced: bool,
) -> pd.DataFrame:
    initial = initial_findings.set_index("finding_id")
    mae_pass = challenger["mae_improvement_vs_persistence"] >= 0
    rmse_pass = challenger["rmse_improvement_vs_persistence"] >= 0
    if mae_pass and rmse_pass:
        benchmark_retest = "pass"
        benchmark_closure = "pending_fresh_oot"
        benchmark_reason = (
            "Both reused-OOT benchmarks passed, but fresh post-selection OOT is required."
        )
    elif mae_pass or rmse_pass:
        benchmark_retest = "partial"
        benchmark_closure = "open"
        benchmark_reason = (
            "Only one reused-OOT error benchmark passed and the evidence is not fresh."
        )
    else:
        benchmark_retest = "fail"
        benchmark_closure = "open"
        benchmark_reason = "Both reused-OOT error benchmarks remain below requirement."

    factor_pass = active_macro_drivers >= 2
    vintage_pass = lag_violations == 0 and real_time_vintage_evidenced
    lifecycle = [
        {
            "finding_id": "MSV-001",
            "remediation_action": (
                "Test pre-registered change targets, dynamics, lags, horizons, and Ridge "
                "penalties using validation evidence only."
            ),
            "retest_status": benchmark_retest,
            "retest_metric": float(challenger["mae_improvement_vs_persistence"]),
            "closure_status": benchmark_closure,
            "closure_reason": benchmark_reason,
        },
        {
            "finding_id": "MSV-002",
            "remediation_action": (
                "Replace contemporaneous levels with lagged macro changes and independently "
                "check retained factor sensitivity."
            ),
            "retest_status": "pass" if factor_pass else "fail",
            "retest_metric": float(active_macro_drivers),
            "closure_status": "pending_fresh_oot" if factor_pass else "open",
            "closure_reason": (
                "Both macro factors are active, but stability requires fresh OOT evidence."
                if factor_pass
                else "The remediated fit does not retain both macro factors."
            ),
        },
        {
            "finding_id": "MSV-003",
            "remediation_action": (
                "Lag every macro input to the forecast origin and retain the requirement "
                "for release-vintage and revision testing."
            ),
            "retest_status": "pass" if vintage_pass else "partial",
            "retest_metric": 1.0 if vintage_pass else 0.0,
            "closure_status": "pending_fresh_oot" if vintage_pass else "open",
            "closure_reason": (
                "Timing and real-time vintage evidence passed; fresh OOT remains required."
                if vintage_pass
                else "Lags address timing, but real-time data revisions remain unevidenced."
            ),
        },
    ]
    frame = pd.DataFrame(lifecycle)
    frame.insert(1, "severity", frame["finding_id"].map(initial["severity"]))
    frame.insert(2, "title", frame["finding_id"].map(initial["title"]))
    frame.insert(3, "initial_status", frame["finding_id"].map(initial["status"]))
    frame["evidence_freshness"] = "reused_oot"
    frame["independent_use_restriction"] = "sensitivity_only"
    return frame


def _overall_opinion(
    summary: pd.DataFrame,
    lifecycle: pd.DataFrame,
) -> str:
    if "fail" in set(summary["status"]) or "open" in set(lifecycle["closure_status"]):
        return "restricted"
    if "warning" in set(summary["status"]):
        return "conditional"
    return "acceptable"


def _validate_oot_window(frame: pd.DataFrame, label: str) -> None:
    oot = frame[frame["split"] == "oot"].sort_values("quarter")
    if list(oot["quarter"]) != list(EXPECTED_OOT_QUARTERS):
        raise ValueError(f"{label} must preserve the frozen 2019-2021 OOT window")


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing columns: " + ", ".join(sorted(missing)))


def _to_bool(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"Expected boolean value, received {value!r}")


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


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(actual - predicted))))
