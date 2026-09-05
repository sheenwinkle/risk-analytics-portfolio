from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from model_validation.metrics import roc_auc_score
from model_validation.policy import ValidationPolicy
from model_validation.validation import (
    Project1OOTPredictionAdapter,
    load_validated_predictions,
    run_validation,
)


@dataclass(frozen=True)
class RemediationPolicy:
    lookback_months: int = 3
    initial_calibration_months: int = 6
    max_iterations: int = 100
    tolerance: float = 1e-10
    closure_requires_fresh_oot: bool = True

    def __post_init__(self) -> None:
        if self.lookback_months < 2:
            raise ValueError("lookback_months must be at least 2")
        if self.initial_calibration_months < self.lookback_months:
            raise ValueError("initial_calibration_months must be at least lookback_months")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if not np.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("tolerance must be a positive finite number")


@dataclass(frozen=True)
class RemediationResult:
    remediation_summary: pd.DataFrame
    monthly_recalibration: pd.DataFrame
    finding_lifecycle: pd.DataFrame
    report_paths: dict[str, str] = field(default_factory=dict)


def run_calibration_remediation(
    adapter: Project1OOTPredictionAdapter,
    *,
    remediation_policy: RemediationPolicy | None = None,
    validation_policy: ValidationPolicy | None = None,
) -> RemediationResult:
    active_remediation_policy = remediation_policy or RemediationPolicy()
    active_validation_policy = validation_policy or ValidationPolicy()
    predictions = load_validated_predictions(adapter)
    original_validation = run_validation(adapter, policy=active_validation_policy)
    original_check = original_validation.validation_summary.loc[
        original_validation.validation_summary["check"].eq("absolute_calibration_gap")
    ].iloc[0]

    scored = predictions.sort_values(
        ["observation_date", "customer_id"],
        kind="mergesort",
    ).copy()
    scored["period"] = scored["observation_date"].dt.to_period("M").dt.to_timestamp()
    periods = sorted(scored["period"].unique())
    if len(periods) <= active_remediation_policy.initial_calibration_months:
        raise ValueError(
            "Remediation requires periods after the initial calibration window"
        )

    monthly_rows = []
    validation_actual = []
    incumbent_scores = []
    remediated_scores = []
    for validation_index in range(
        active_remediation_policy.initial_calibration_months,
        len(periods),
    ):
        validation_period = periods[validation_index]
        calibration_periods = periods[
            validation_index - active_remediation_policy.lookback_months : validation_index
        ]
        calibration = scored.loc[scored["period"].isin(calibration_periods)]
        validation = scored.loc[scored["period"].eq(validation_period)]
        intercept, slope = _fit_logistic_recalibration(
            calibration["recalibrated_pd"].to_numpy(dtype=float),
            calibration["actual_default"].to_numpy(dtype=int),
            policy=active_remediation_policy,
        )
        remediated = _apply_logistic_recalibration(
            validation["recalibrated_pd"].to_numpy(dtype=float),
            intercept,
            slope,
        )
        actual = validation["actual_default"].to_numpy(dtype=int)
        incumbent = validation["recalibrated_pd"].to_numpy(dtype=float)
        validation_actual.extend(actual.tolist())
        incumbent_scores.extend(incumbent.tolist())
        remediated_scores.extend(remediated.tolist())

        observed_rate = float(actual.mean())
        incumbent_mean = float(incumbent.mean())
        remediated_mean = float(remediated.mean())
        monthly_rows.append(
            {
                "calibration_start": pd.Timestamp(calibration_periods[0]).date(),
                "calibration_end": pd.Timestamp(calibration_periods[-1]).date(),
                "validation_period": pd.Timestamp(validation_period).date(),
                "lookback_months": active_remediation_policy.lookback_months,
                "observations": len(validation),
                "defaults": int(actual.sum()),
                "observed_default_rate": observed_rate,
                "incumbent_mean_pd": incumbent_mean,
                "remediated_mean_pd": remediated_mean,
                "incumbent_absolute_calibration_gap": abs(
                    incumbent_mean - observed_rate
                ),
                "remediated_absolute_calibration_gap": abs(
                    remediated_mean - observed_rate
                ),
                "fitted_intercept": intercept,
                "fitted_slope": slope,
            }
        )

    actual_array = np.asarray(validation_actual, dtype=int)
    incumbent_array = np.asarray(incumbent_scores, dtype=float)
    remediated_array = np.asarray(remediated_scores, dtype=float)
    observed_rate = float(actual_array.mean())
    incumbent_gap = abs(float(incumbent_array.mean()) - observed_rate)
    remediated_gap = abs(float(remediated_array.mean()) - observed_rate)
    incumbent_status = _lower_is_better_status(
        incumbent_gap,
        active_validation_policy.absolute_calibration_gap_green_max,
        active_validation_policy.absolute_calibration_gap_warning_max,
    )
    remediation_status = _lower_is_better_status(
        remediated_gap,
        active_validation_policy.absolute_calibration_gap_green_max,
        active_validation_policy.absolute_calibration_gap_warning_max,
    )
    closure_status = _closure_status(remediation_status, active_remediation_policy)

    monthly_recalibration = pd.DataFrame(monthly_rows)
    remediation_summary = pd.DataFrame(
        [
            {
                "selected_model": str(predictions["selected_model"].iloc[0]),
                "incumbent_score_version": "recalibrated",
                "remediation_method": "rolling_logistic_recalibration",
                "lookback_months": active_remediation_policy.lookback_months,
                "validation_start": monthly_recalibration["validation_period"].min(),
                "validation_end": monthly_recalibration["validation_period"].max(),
                "observations": len(actual_array),
                "defaults": int(actual_array.sum()),
                "observed_default_rate": observed_rate,
                "incumbent_mean_pd": float(incumbent_array.mean()),
                "remediated_mean_pd": float(remediated_array.mean()),
                "incumbent_absolute_calibration_gap": incumbent_gap,
                "remediated_absolute_calibration_gap": remediated_gap,
                "incumbent_calibration_status": incumbent_status,
                "remediation_retest_status": remediation_status,
                "incumbent_brier_score": float(
                    np.mean((incumbent_array - actual_array) ** 2)
                ),
                "remediated_brier_score": float(
                    np.mean((remediated_array - actual_array) ** 2)
                ),
                "incumbent_roc_auc": roc_auc_score(actual_array, incumbent_array),
                "remediated_roc_auc": roc_auc_score(actual_array, remediated_array),
                "closure_status": closure_status,
            }
        ]
    )
    finding_lifecycle = pd.DataFrame(
        [
            {
                "finding_id": "CAL-001",
                "check": "absolute_calibration_gap",
                "initial_status": str(original_check["status"]),
                "initial_metric_value": float(original_check["metric_value"]),
                "remediation_action": (
                    "Monthly sequential logistic recalibration using only the prior "
                    f"{active_remediation_policy.lookback_months} matured cohorts."
                ),
                "retest_status": remediation_status,
                "retest_metric_value": remediated_gap,
                "closure_status": closure_status,
                "closure_reason": _closure_reason(
                    remediation_status,
                    active_remediation_policy,
                ),
                "evidence_reference": "remediation_summary.csv",
            }
        ]
    )
    return RemediationResult(
        remediation_summary=remediation_summary,
        monthly_recalibration=monthly_recalibration,
        finding_lifecycle=finding_lifecycle,
    )


def run_calibration_remediation_pipeline(
    adapter: Project1OOTPredictionAdapter,
    output_dir: str | Path,
    *,
    remediation_policy: RemediationPolicy | None = None,
    validation_policy: ValidationPolicy | None = None,
) -> RemediationResult:
    result = run_calibration_remediation(
        adapter,
        remediation_policy=remediation_policy,
        validation_policy=validation_policy,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ("remediation_summary", "monthly_recalibration", "finding_lifecycle"):
        path = output_dir / f"{name}.csv"
        getattr(result, name).to_csv(
            path,
            index=False,
            float_format="%.6f",
            lineterminator="\n",
        )
        paths[path.name] = str(path)
    report_path = output_dir / "remediation_report.md"
    report_path.write_text(_build_remediation_report(result), encoding="utf-8", newline="\n")
    paths[report_path.name] = str(report_path)
    return replace(result, report_paths=paths)


def _fit_logistic_recalibration(
    scores: np.ndarray,
    actual: np.ndarray,
    *,
    policy: RemediationPolicy,
) -> tuple[float, float]:
    if set(actual.tolist()) != {0, 1}:
        raise ValueError("Each remediation calibration window must contain both classes")
    clipped = np.clip(scores, 1e-6, 1 - 1e-6)
    design = np.column_stack([np.ones(len(clipped)), np.log(clipped / (1 - clipped))])
    coefficients = np.array([0.0, 1.0])
    for _ in range(policy.max_iterations):
        fitted = _sigmoid(design @ coefficients)
        weights = np.clip(fitted * (1 - fitted), 1e-9, None)
        information = design.T @ (weights[:, None] * design) + np.eye(2) * 1e-9
        step = np.linalg.solve(information, design.T @ (actual - fitted))
        coefficients += step
        if float(np.max(np.abs(step))) < policy.tolerance:
            break
    else:
        raise RuntimeError("Rolling logistic recalibration did not converge")
    return float(coefficients[0]), float(coefficients[1])


def _apply_logistic_recalibration(
    scores: np.ndarray,
    intercept: float,
    slope: float,
) -> np.ndarray:
    clipped = np.clip(scores, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    return _sigmoid(intercept + slope * logits)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(values, -35, 35)))


def _lower_is_better_status(value: float, green: float, warning: float) -> str:
    if value <= green:
        return "pass"
    if value <= warning:
        return "warning"
    return "fail"


def _closure_status(status: str, policy: RemediationPolicy) -> str:
    if status != "pass":
        return "open"
    if policy.closure_requires_fresh_oot:
        return "pending_fresh_oot"
    return "closed"


def _closure_reason(status: str, policy: RemediationPolicy) -> str:
    if status != "pass":
        return "Remediation has not met the pass threshold."
    if policy.closure_requires_fresh_oot:
        return (
            "Sequential retest passed, but closure requires an additional matured OOT horizon."
        )
    return "Remediation met the pass threshold and closure evidence requirements."


def _build_remediation_report(result: RemediationResult) -> str:
    summary = result.remediation_summary.iloc[0]
    lifecycle = result.finding_lifecycle.iloc[0]
    monthly_lines = []
    for _, row in result.monthly_recalibration.iterrows():
        monthly_lines.append(
            "| "
            f"{row['validation_period']} | {int(row['observations'])} | "
            f"{row['observed_default_rate']:.3f} | {row['incumbent_mean_pd']:.3f} | "
            f"{row['remediated_mean_pd']:.3f} |"
        )
    lines = [
        "# Calibration Remediation and Finding Lifecycle",
        "",
        "## Decision",
        "",
        (
            f"- Sequential remediation retest: **{summary['remediation_retest_status']}** "
            f"(absolute calibration gap {summary['remediated_absolute_calibration_gap']:.3f})."
        ),
        f"- Finding closure status: **{summary['closure_status']}**.",
        f"- Closure rationale: {lifecycle['closure_reason']}",
        "",
        "## No-Look-Ahead Design",
        "",
        (
            f"Each validation month uses a logistic recalibrator fitted only on the prior "
            f"{int(summary['lookback_months'])} matured monthly cohorts. No validation-month "
            "outcome is used to fit its own score transformation."
        ),
        "",
        "## Aggregate Reperformance",
        "",
        "| Measure | Incumbent | Remediated |",
        "| --- | ---: | ---: |",
        (
            "| Mean PD | "
            f"{summary['incumbent_mean_pd']:.3f} | {summary['remediated_mean_pd']:.3f} |"
        ),
        (
            "| Absolute calibration gap | "
            f"{summary['incumbent_absolute_calibration_gap']:.3f} | "
            f"{summary['remediated_absolute_calibration_gap']:.3f} |"
        ),
        (
            "| Brier score | "
            f"{summary['incumbent_brier_score']:.3f} | "
            f"{summary['remediated_brier_score']:.3f} |"
        ),
        "",
        f"Observed default rate: {summary['observed_default_rate']:.3f}.",
        "",
        "## Monthly Evidence",
        "",
        "| Validation month | Observations | Observed rate | Incumbent PD | Remediated PD |",
        "| --- | ---: | ---: | ---: | ---: |",
        *monthly_lines,
        "",
        "Educational portfolio case study; not a production model-change approval.",
        "",
    ]
    return "\n".join(lines)
