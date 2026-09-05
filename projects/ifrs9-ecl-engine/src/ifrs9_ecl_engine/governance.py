from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pandas as pd

from ifrs9_ecl_engine.engine import ECLResult

SCENARIO_REQUIRED_COLUMNS = {
    "scenario",
    "scenario_weight",
    "scenario_ecl",
    "weighted_scenario_ecl",
}
TRIGGER_OPERATORS = {"greater_than_or_equal", "less_than_or_equal"}
OVERLAP_ASSESSMENTS = {"distinct", "captured_by_model"}
APPROVAL_STATUSES = {"approved", "pending", "rejected"}


@dataclass(frozen=True)
class MacroSensitivityCase:
    case_id: str
    description: str
    scenario_weights: Mapping[str, float]
    scenario_ecl_multipliers: Mapping[str, float] = field(default_factory=dict)
    is_baseline: bool = False


@dataclass(frozen=True)
class ManagementOverlay:
    overlay_id: str
    risk_driver: str
    scope: str
    trigger_metric: str
    trigger_operator: str
    observed_value: float
    trigger_threshold: float
    requested_amount: float
    cap_ratio_of_modelled_ecl: float
    overlap_assessment: str
    modelled_risk_reference: str
    approval_status: str
    approved_by: str | None
    rationale: str


@dataclass(frozen=True)
class MacroSensitivityResult:
    summary: pd.DataFrame
    detail: pd.DataFrame


@dataclass(frozen=True)
class OverlayEvaluationResult:
    overlay_register: pd.DataFrame
    reconciliation: pd.DataFrame


@dataclass(frozen=True)
class MacroOverlayAnalysisResult:
    macro_summary: pd.DataFrame
    macro_detail: pd.DataFrame
    overlay_register: pd.DataFrame
    reconciliation: pd.DataFrame


def analyse_macro_sensitivity(
    scenario_ecl: pd.DataFrame,
    gross_exposure: float,
    cases: Sequence[MacroSensitivityCase],
) -> MacroSensitivityResult:
    """Reweight and stress scenario ECL without changing booked model output."""
    exposure = _validate_nonnegative_number(gross_exposure, "gross_exposure")
    scenario_totals, modelled_weights = _validate_scenario_ecl(scenario_ecl)
    normalized_cases = _validate_sensitivity_cases(cases, modelled_weights)

    scenario_names = sorted(scenario_totals)
    case_values: list[tuple[MacroSensitivityCase, dict[str, float], float]] = []
    baseline_ecl: float | None = None
    for case, weights, multipliers in normalized_cases:
        modelled_ecl = sum(
            scenario_totals[scenario] * weights[scenario] * multipliers[scenario]
            for scenario in scenario_names
        )
        case_values.append((case, multipliers, modelled_ecl))
        if case.is_baseline:
            baseline_ecl = modelled_ecl

    if baseline_ecl is None:  # Guarded by validation; keeps the type invariant explicit.
        raise RuntimeError("A baseline sensitivity case is required")

    summary_rows = []
    detail_rows = []
    for case, multipliers, modelled_ecl in case_values:
        weights = {scenario: float(case.scenario_weights[scenario]) for scenario in scenario_names}
        change = modelled_ecl - baseline_ecl
        summary_rows.append(
            {
                "case_id": case.case_id,
                "description": case.description,
                "is_baseline": case.is_baseline,
                "modelled_ecl": modelled_ecl,
                "change_vs_baseline": change,
                "change_pct_vs_baseline": _ratio(change, baseline_ecl),
                "gross_exposure": exposure,
                "coverage_ratio": _ratio(modelled_ecl, exposure),
            }
        )
        for scenario in scenario_names:
            base_scenario_ecl = scenario_totals[scenario]
            stressed_scenario_ecl = base_scenario_ecl * multipliers[scenario]
            detail_rows.append(
                {
                    "case_id": case.case_id,
                    "is_baseline": case.is_baseline,
                    "scenario": scenario,
                    "scenario_weight": weights[scenario],
                    "scenario_ecl_multiplier": multipliers[scenario],
                    "base_scenario_ecl": base_scenario_ecl,
                    "stressed_scenario_ecl": stressed_scenario_ecl,
                    "weighted_scenario_ecl": stressed_scenario_ecl * weights[scenario],
                }
            )

    return MacroSensitivityResult(
        summary=pd.DataFrame(summary_rows),
        detail=pd.DataFrame(detail_rows),
    )


def evaluate_management_overlays(
    modelled_ecl: float,
    gross_exposure: float,
    overlays: Sequence[ManagementOverlay],
) -> OverlayEvaluationResult:
    """Apply trigger, overlap, approval, and cap controls to overlay requests."""
    baseline_ecl = _validate_nonnegative_number(modelled_ecl, "modelled_ecl")
    exposure = _validate_nonnegative_number(gross_exposure, "gross_exposure")
    _validate_overlay_keys(overlays)

    rows = []
    for overlay in overlays:
        _validate_overlay(overlay)
        observed = _validate_finite_number(overlay.observed_value, "observed_value")
        threshold = _validate_finite_number(overlay.trigger_threshold, "trigger_threshold")
        requested = _validate_nonnegative_number(
            overlay.requested_amount,
            "requested_amount",
        )
        cap_ratio = _validate_nonnegative_number(
            overlay.cap_ratio_of_modelled_ecl,
            "cap_ratio_of_modelled_ecl",
        )
        if cap_ratio > 1:
            raise ValueError("cap_ratio_of_modelled_ecl must be between 0 and 1")

        trigger_met = _trigger_met(
            observed,
            threshold,
            overlay.trigger_operator,
        )
        double_counting_passed = overlay.overlap_assessment == "distinct"
        cap_amount = baseline_ecl * cap_ratio
        capped_amount = min(requested, cap_amount)
        cap_binding = requested > cap_amount and not math.isclose(requested, cap_amount)
        recognition_status, recognized_amount = _recognition_outcome(
            overlay=overlay,
            trigger_met=trigger_met,
            double_counting_passed=double_counting_passed,
            capped_amount=capped_amount,
            cap_binding=cap_binding,
        )
        rows.append(
            {
                "overlay_id": overlay.overlay_id,
                "risk_driver": overlay.risk_driver,
                "scope": overlay.scope,
                "trigger_metric": overlay.trigger_metric,
                "trigger_operator": overlay.trigger_operator,
                "observed_value": observed,
                "trigger_threshold": threshold,
                "trigger_met": trigger_met,
                "requested_amount": requested,
                "cap_ratio_of_modelled_ecl": cap_ratio,
                "cap_amount": cap_amount,
                "cap_binding": cap_binding,
                "overlap_assessment": overlay.overlap_assessment,
                "modelled_risk_reference": overlay.modelled_risk_reference,
                "double_counting_check": "pass" if double_counting_passed else "fail",
                "approval_status": overlay.approval_status,
                "approved_by": overlay.approved_by or "",
                "rationale": overlay.rationale,
                "recognition_status": recognition_status,
                "recognized_amount": recognized_amount,
            }
        )

    register = pd.DataFrame(rows, columns=_overlay_register_columns())
    recognized_overlay = float(register["recognized_amount"].sum()) if len(register) else 0.0
    reported_ecl = baseline_ecl + recognized_overlay
    reconciliation = pd.DataFrame(
        [
            {
                "baseline_modelled_ecl": baseline_ecl,
                "recognized_management_overlay": recognized_overlay,
                "illustrative_reported_ecl": reported_ecl,
                "gross_exposure": exposure,
                "modelled_coverage_ratio": _ratio(baseline_ecl, exposure),
                "illustrative_reported_coverage_ratio": _ratio(reported_ecl, exposure),
                "overlay_share_of_modelled_ecl": _ratio(recognized_overlay, baseline_ecl),
            }
        ]
    )
    return OverlayEvaluationResult(
        overlay_register=register,
        reconciliation=reconciliation,
    )


def run_macro_overlay_analysis(
    ecl_result: ECLResult,
    cases: Sequence[MacroSensitivityCase],
    overlays: Sequence[ManagementOverlay],
) -> MacroOverlayAnalysisResult:
    total_rows = ecl_result.portfolio_summary[
        ecl_result.portfolio_summary["stage"].astype(str) == "Total"
    ]
    if len(total_rows) != 1:
        raise ValueError("portfolio_summary must contain exactly one Total row")
    total = total_rows.iloc[0]
    gross_exposure = _validate_nonnegative_number(total["gross_exposure"], "gross_exposure")
    reported_modelled_ecl = _validate_nonnegative_number(total["weighted_ecl"], "weighted_ecl")

    macro = analyse_macro_sensitivity(ecl_result.scenario_ecl, gross_exposure, cases)
    baseline_row = macro.summary[macro.summary["is_baseline"]].iloc[0]
    baseline_ecl = float(baseline_row["modelled_ecl"])
    if not math.isclose(baseline_ecl, reported_modelled_ecl, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("Baseline sensitivity ECL must reconcile to portfolio modelled ECL")

    overlay = evaluate_management_overlays(baseline_ecl, gross_exposure, overlays)
    highest_case = macro.summary.sort_values(
        ["modelled_ecl", "case_id"],
        ascending=[False, True],
    ).iloc[0]
    reconciliation = overlay.reconciliation.copy()
    reconciliation.insert(1, "highest_sensitivity_case_id", highest_case["case_id"])
    reconciliation.insert(2, "highest_sensitivity_ecl", highest_case["modelled_ecl"])
    reconciliation.insert(
        3,
        "highest_sensitivity_delta_not_booked",
        highest_case["change_vs_baseline"],
    )

    return MacroOverlayAnalysisResult(
        macro_summary=macro.summary,
        macro_detail=macro.detail,
        overlay_register=overlay.overlay_register,
        reconciliation=reconciliation,
    )


def _validate_scenario_ecl(
    scenario_ecl: pd.DataFrame,
) -> tuple[dict[str, float], dict[str, float]]:
    missing = SCENARIO_REQUIRED_COLUMNS - set(scenario_ecl.columns)
    if missing:
        raise ValueError(
            "scenario_ecl missing required columns: " + ", ".join(sorted(missing))
        )
    if scenario_ecl.empty:
        raise ValueError("scenario_ecl must contain at least one row")
    if scenario_ecl["scenario"].isna().any() or (
        scenario_ecl["scenario"].astype(str).str.strip() == ""
    ).any():
        raise ValueError("scenario_ecl.scenario must contain non-empty values")

    normalized = scenario_ecl.copy()
    for column in ["scenario_weight", "scenario_ecl", "weighted_scenario_ecl"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if not normalized[column].map(math.isfinite).all():
            raise ValueError(f"scenario_ecl.{column} must contain finite numeric values")
    if (normalized[["scenario_weight", "scenario_ecl", "weighted_scenario_ecl"]] < 0).any().any():
        raise ValueError("scenario ECL values and weights must be nonnegative")

    weight_counts = normalized.groupby("scenario")["scenario_weight"].nunique()
    if (weight_counts != 1).any():
        raise ValueError("Scenario weights must be consistent within each scenario")
    weights = {
        str(scenario): float(weight)
        for scenario, weight in normalized.groupby("scenario")["scenario_weight"].first().items()
    }
    _validate_weights(weights)

    expected_weighted = normalized["scenario_ecl"] * normalized["scenario_weight"]
    if not all(
        math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-6)
        for actual, expected in zip(
            normalized["weighted_scenario_ecl"],
            expected_weighted,
            strict=True,
        )
    ):
        raise ValueError("weighted_scenario_ecl must equal scenario_ecl times scenario_weight")
    totals = {
        str(scenario): float(value)
        for scenario, value in normalized.groupby("scenario")["scenario_ecl"].sum().items()
    }
    return totals, weights


def _validate_sensitivity_cases(
    cases: Sequence[MacroSensitivityCase],
    modelled_weights: Mapping[str, float],
) -> list[tuple[MacroSensitivityCase, dict[str, float], dict[str, float]]]:
    if not cases:
        raise ValueError("At least one macro sensitivity case is required")
    if any(not isinstance(case.is_baseline, bool) for case in cases):
        raise ValueError("is_baseline must be boolean")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Macro sensitivity case IDs must be unique")
    baseline_cases = [case for case in cases if case.is_baseline]
    if len(baseline_cases) != 1:
        raise ValueError("Exactly one macro sensitivity case must be the baseline")

    scenarios = set(modelled_weights)
    normalized = []
    for case in cases:
        _validate_text(case.case_id, "case_id")
        _validate_text(case.description, "description")
        weights = {}
        for scenario, value in case.scenario_weights.items():
            _validate_text(scenario, "scenario")
            weights[scenario] = _validate_nonnegative_number(
                value,
                f"Scenario weight for {scenario}",
            )
        if set(weights) != scenarios:
            raise ValueError("Sensitivity case weights must cover exactly the modelled scenarios")
        _validate_weights(weights)

        multiplier_keys = set(case.scenario_ecl_multipliers)
        if multiplier_keys - scenarios:
            raise ValueError("Sensitivity multipliers contain scenarios not present in the model")
        multipliers = {scenario: 1.0 for scenario in scenarios}
        for scenario, value in case.scenario_ecl_multipliers.items():
            multiplier = _validate_nonnegative_number(
                value,
                f"scenario_ecl_multiplier for {scenario}",
            )
            multipliers[scenario] = multiplier

        if case.is_baseline:
            if any(
                not math.isclose(weights[scenario], modelled_weights[scenario], abs_tol=1e-9)
                for scenario in scenarios
            ):
                raise ValueError("Baseline case weights must match modelled scenario weights")
            if any(not math.isclose(value, 1.0, abs_tol=1e-9) for value in multipliers.values()):
                raise ValueError("Baseline case ECL multipliers must equal 1")
        normalized.append((case, weights, multipliers))
    return normalized


def _validate_weights(weights: Mapping[str, float]) -> None:
    total = 0.0
    for scenario, weight in weights.items():
        _validate_text(scenario, "scenario")
        value = _validate_nonnegative_number(weight, f"Scenario weight for {scenario}")
        total += value
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Scenario weights must sum to 1")


def _validate_overlay_keys(overlays: Sequence[ManagementOverlay]) -> None:
    overlay_ids = [overlay.overlay_id for overlay in overlays]
    if len(overlay_ids) != len(set(overlay_ids)):
        raise ValueError("Overlay IDs must be unique")
    risk_scopes = [(overlay.risk_driver, overlay.scope) for overlay in overlays]
    if len(risk_scopes) != len(set(risk_scopes)):
        raise ValueError("Overlay risk driver and scope must be unique")


def _validate_overlay(overlay: ManagementOverlay) -> None:
    for field_name in [
        "overlay_id",
        "risk_driver",
        "scope",
        "trigger_metric",
        "modelled_risk_reference",
        "rationale",
    ]:
        _validate_text(getattr(overlay, field_name), field_name)
    if overlay.trigger_operator not in TRIGGER_OPERATORS:
        raise ValueError(
            "trigger_operator must be one of: " + ", ".join(sorted(TRIGGER_OPERATORS))
        )
    if overlay.overlap_assessment not in OVERLAP_ASSESSMENTS:
        raise ValueError(
            "overlap_assessment must be one of: " + ", ".join(sorted(OVERLAP_ASSESSMENTS))
        )
    if overlay.approval_status not in APPROVAL_STATUSES:
        raise ValueError(
            "approval_status must be one of: " + ", ".join(sorted(APPROVAL_STATUSES))
        )
    if overlay.approval_status == "approved" and (
        not isinstance(overlay.approved_by, str) or not overlay.approved_by.strip()
    ):
        raise ValueError("approved_by is required for approved overlays")
    if overlay.approval_status != "approved" and overlay.approved_by is not None:
        _validate_text(overlay.approved_by, "approved_by")


def _trigger_met(observed: float, threshold: float, operator: str) -> bool:
    if operator == "greater_than_or_equal":
        return observed >= threshold
    return observed <= threshold


def _recognition_outcome(
    *,
    overlay: ManagementOverlay,
    trigger_met: bool,
    double_counting_passed: bool,
    capped_amount: float,
    cap_binding: bool,
) -> tuple[str, float]:
    if not trigger_met:
        return "blocked_trigger_not_met", 0.0
    if not double_counting_passed:
        return "blocked_model_overlap", 0.0
    if overlay.approval_status == "pending":
        return "pending_approval", 0.0
    if overlay.approval_status == "rejected":
        return "rejected", 0.0
    return ("recognized_capped" if cap_binding else "recognized"), capped_amount


def _validate_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _validate_finite_number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{label} must be numeric") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _validate_nonnegative_number(value: object, label: str) -> float:
    number = _validate_finite_number(value, label)
    if number < 0:
        raise ValueError(f"{label} must be nonnegative")
    return number


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _overlay_register_columns() -> list[str]:
    return [
        "overlay_id",
        "risk_driver",
        "scope",
        "trigger_metric",
        "trigger_operator",
        "observed_value",
        "trigger_threshold",
        "trigger_met",
        "requested_amount",
        "cap_ratio_of_modelled_ecl",
        "cap_amount",
        "cap_binding",
        "overlap_assessment",
        "modelled_risk_reference",
        "double_counting_check",
        "approval_status",
        "approved_by",
        "rationale",
        "recognition_status",
        "recognized_amount",
    ]
