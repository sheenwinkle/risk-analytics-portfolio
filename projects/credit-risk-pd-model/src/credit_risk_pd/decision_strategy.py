from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DecisionStrategyResult:
    strategy_selection_audit: pd.DataFrame
    strategy_oot_comparison: pd.DataFrame
    strategy_incremental_impact: pd.DataFrame
    strategy_acceptance_checks: pd.DataFrame
    strategy_governance_decision: pd.DataFrame


@dataclass(frozen=True)
class _StrategySample:
    pd_scores: np.ndarray
    target: np.ndarray
    exposure: np.ndarray
    interest_rate: np.ndarray


def run_decision_strategy_backtest(
    *,
    calibration_pd,
    calibration_target,
    calibration_exposure,
    calibration_interest_rate,
    oot_pd,
    oot_target,
    oot_exposure,
    oot_interest_rate,
    candidate_cutoffs: Iterable[float],
    incumbent_cutoff: float = 0.15,
    max_bad_rate: float = 0.13,
    max_expected_loss_rate: float = 0.06,
    max_cutoff_increase: float = 0.05,
    max_bad_rate_increase: float = 0.03,
    lgd: float = 0.45,
    bootstrap_repetitions: int = 2_000,
    confidence_level: float = 0.95,
    random_state: int = 42,
) -> DecisionStrategyResult:
    """Select a growth challenger pre-OOT and evaluate it on untouched OOT outcomes."""
    cutoffs = _validated_cutoffs(candidate_cutoffs)
    incumbent = _validated_rate(incumbent_cutoff, "incumbent_cutoff", inclusive=False)
    if incumbent not in cutoffs:
        raise ValueError("incumbent cutoff must be included in candidate_cutoffs")
    bad_rate_limit = _validated_rate(max_bad_rate, "max_bad_rate")
    expected_loss_limit = _validated_rate(
        max_expected_loss_rate,
        "max_expected_loss_rate",
    )
    cutoff_increase_limit = _validated_rate(
        max_cutoff_increase,
        "max_cutoff_increase",
    )
    bad_rate_increase_limit = _validated_rate(
        max_bad_rate_increase,
        "max_bad_rate_increase",
    )
    lgd_value = _validated_rate(lgd, "lgd")
    repetitions = _validated_repetitions(bootstrap_repetitions)
    confidence = _validated_confidence_level(confidence_level)
    calibration = _validated_sample(
        calibration_pd,
        calibration_target,
        calibration_exposure,
        calibration_interest_rate,
        "calibration",
    )
    oot = _validated_sample(
        oot_pd,
        oot_target,
        oot_exposure,
        oot_interest_rate,
        "OOT",
    )

    selection_audit, challenger, challenger_found = _select_growth_challenger(
        calibration,
        cutoffs=cutoffs,
        incumbent_cutoff=incumbent,
        max_bad_rate=bad_rate_limit,
        max_expected_loss_rate=expected_loss_limit,
        max_cutoff_increase=cutoff_increase_limit,
        lgd=lgd_value,
    )
    comparison = _build_oot_comparison(
        oot,
        incumbent_cutoff=incumbent,
        challenger_cutoff=challenger,
        lgd=lgd_value,
    )
    impact = _build_incremental_impact(
        oot,
        incumbent_cutoff=incumbent,
        challenger_cutoff=challenger,
        lgd=lgd_value,
        bootstrap_repetitions=repetitions,
        confidence_level=confidence,
        random_state=random_state,
    )
    checks = _build_acceptance_checks(
        comparison,
        impact,
        challenger_found=challenger_found,
        max_bad_rate_increase=bad_rate_increase_limit,
    )
    decision = _build_governance_decision(
        checks,
        incumbent_cutoff=incumbent,
        challenger_cutoff=challenger,
    )
    return DecisionStrategyResult(
        strategy_selection_audit=selection_audit,
        strategy_oot_comparison=comparison,
        strategy_incremental_impact=impact,
        strategy_acceptance_checks=checks,
        strategy_governance_decision=decision,
    )


def _select_growth_challenger(
    sample: _StrategySample,
    *,
    cutoffs: tuple[float, ...],
    incumbent_cutoff: float,
    max_bad_rate: float,
    max_expected_loss_rate: float,
    max_cutoff_increase: float,
    lgd: float,
) -> tuple[pd.DataFrame, float, bool]:
    rows = []
    for cutoff in cutoffs:
        metrics = _policy_metrics(sample, cutoff, lgd)
        growth_candidate = cutoff > incumbent_cutoff
        within_cutoff_change_limit = (
            cutoff - incumbent_cutoff <= max_cutoff_increase + 1e-12
        )
        meets_bad_rate = metrics["approved_default_rate"] <= max_bad_rate
        meets_expected_loss_rate = metrics["expected_loss_rate"] <= max_expected_loss_rate
        rows.append(
            {
                "selection_sample": "pre_oot_calibration_holdout",
                "max_pd_cutoff": cutoff,
                "incumbent_policy": cutoff == incumbent_cutoff,
                "growth_candidate": growth_candidate,
                "within_cutoff_change_limit": within_cutoff_change_limit,
                **metrics,
                "max_bad_rate_constraint": max_bad_rate,
                "max_expected_loss_rate_constraint": max_expected_loss_rate,
                "max_cutoff_increase_constraint": max_cutoff_increase,
                "meets_bad_rate_constraint": meets_bad_rate,
                "meets_expected_loss_rate_constraint": meets_expected_loss_rate,
                "eligible_growth_challenger": (
                    growth_candidate
                    and within_cutoff_change_limit
                    and meets_bad_rate
                    and meets_expected_loss_rate
                ),
                "selected_challenger": False,
            }
        )
    audit = pd.DataFrame(rows)
    eligible = audit[audit["eligible_growth_challenger"]]
    if eligible.empty:
        return audit, incumbent_cutoff, False

    selected_index = eligible.sort_values(
        ["approval_rate", "max_pd_cutoff"],
        ascending=[False, True],
    ).index[0]
    audit.loc[selected_index, "selected_challenger"] = True
    return audit, float(audit.loc[selected_index, "max_pd_cutoff"]), True


def _build_oot_comparison(
    sample: _StrategySample,
    *,
    incumbent_cutoff: float,
    challenger_cutoff: float,
    lgd: float,
) -> pd.DataFrame:
    rows = []
    for policy, cutoff in (
        ("incumbent", incumbent_cutoff),
        ("challenger", challenger_cutoff),
    ):
        rows.append(
            {
                "evaluation_sample": "out_of_time",
                "policy": policy,
                "max_pd_cutoff": cutoff,
                **_policy_metrics(sample, cutoff, lgd),
            }
        )
    return pd.DataFrame(rows)


def _policy_metrics(sample: _StrategySample, cutoff: float, lgd: float) -> dict[str, float | int]:
    approved = sample.pd_scores <= cutoff
    rejected = ~approved
    approved_accounts = int(approved.sum())
    approved_exposure = float(sample.exposure[approved].sum())
    approved_defaults = int(sample.target[approved].sum())
    total_defaults = int(sample.target.sum())
    expected_loss = float(
        (sample.pd_scores[approved] * lgd * sample.exposure[approved]).sum()
    )
    realized_loss = float((sample.target[approved] * lgd * sample.exposure[approved]).sum())
    gross_interest = float(
        (sample.interest_rate[approved] * sample.exposure[approved]).sum()
    )
    return {
        "lgd": lgd,
        "approved_accounts": approved_accounts,
        "rejected_accounts": int(rejected.sum()),
        "approval_rate": _safe_rate(approved_accounts, len(sample.pd_scores)),
        "approved_observed_defaults": approved_defaults,
        "approved_default_rate": _safe_rate(approved_defaults, approved_accounts),
        "approved_exposure": approved_exposure,
        "expected_loss": expected_loss,
        "expected_loss_rate": _safe_rate(expected_loss, approved_exposure),
        "realized_loss_proxy": realized_loss,
        "realized_loss_rate_proxy": _safe_rate(realized_loss, approved_exposure),
        "gross_interest_income_proxy": gross_interest,
        "expected_credit_contribution_proxy": gross_interest - expected_loss,
        "realized_credit_contribution_proxy": gross_interest - realized_loss,
        "rejected_default_capture_rate": _safe_rate(
            int(sample.target[rejected].sum()),
            total_defaults,
        ),
    }


def _build_incremental_impact(
    sample: _StrategySample,
    *,
    incumbent_cutoff: float,
    challenger_cutoff: float,
    lgd: float,
    bootstrap_repetitions: int,
    confidence_level: float,
    random_state: int,
) -> pd.DataFrame:
    incumbent_approved = sample.pd_scores <= incumbent_cutoff
    challenger_approved = sample.pd_scores <= challenger_cutoff
    decision_delta = challenger_approved.astype(int) - incumbent_approved.astype(int)
    marginal = decision_delta != 0
    per_account_expected_contribution = sample.exposure * (
        sample.interest_rate - sample.pd_scores * lgd
    )
    per_account_realized_contribution = sample.exposure * (
        sample.interest_rate - sample.target * lgd
    )
    signed_realized_contribution = (
        per_account_realized_contribution[marginal] * decision_delta[marginal]
    )
    ci_lower, ci_upper = _bootstrap_sum_interval(
        signed_realized_contribution,
        repetitions=bootstrap_repetitions,
        confidence_level=confidence_level,
        random_state=random_state,
    )

    incumbent_metrics = _policy_metrics(sample, incumbent_cutoff, lgd)
    challenger_metrics = _policy_metrics(sample, challenger_cutoff, lgd)
    return pd.DataFrame(
        [
            {
                "evaluation_sample": "out_of_time",
                "incumbent_cutoff": incumbent_cutoff,
                "challenger_cutoff": challenger_cutoff,
                "incremental_approved_accounts": int(decision_delta.sum()),
                "incremental_approval_rate": (
                    challenger_metrics["approval_rate"] - incumbent_metrics["approval_rate"]
                ),
                "incremental_approved_exposure": float(
                    (sample.exposure * decision_delta).sum()
                ),
                "incremental_expected_loss": (
                    challenger_metrics["expected_loss"] - incumbent_metrics["expected_loss"]
                ),
                "incremental_realized_loss_proxy": (
                    challenger_metrics["realized_loss_proxy"]
                    - incumbent_metrics["realized_loss_proxy"]
                ),
                "incremental_expected_credit_contribution_proxy": float(
                    (per_account_expected_contribution * decision_delta).sum()
                ),
                "incremental_realized_credit_contribution_proxy": float(
                    (per_account_realized_contribution * decision_delta).sum()
                ),
                "marginal_accounts": int(marginal.sum()),
                "marginal_mean_pd": _safe_mean(sample.pd_scores[marginal]),
                "marginal_observed_default_rate": _safe_mean(sample.target[marginal]),
                "realized_contribution_ci_lower": ci_lower,
                "realized_contribution_ci_upper": ci_upper,
                "confidence_level": confidence_level,
                "bootstrap_repetitions": bootstrap_repetitions,
                "interval_method": "paired_marginal_cohort_bootstrap_percentile",
            }
        ]
    )


def _build_acceptance_checks(
    comparison: pd.DataFrame,
    impact: pd.DataFrame,
    *,
    challenger_found: bool,
    max_bad_rate_increase: float,
) -> pd.DataFrame:
    incumbent = comparison[comparison["policy"].eq("incumbent")].iloc[0]
    challenger = comparison[comparison["policy"].eq("challenger")].iloc[0]
    incremental = impact.iloc[0]
    bad_rate_increase = float(
        challenger["approved_default_rate"] - incumbent["approved_default_rate"]
    )
    realized_lower = float(incremental["realized_contribution_ci_lower"])
    realized_upper = float(incremental["realized_contribution_ci_upper"])
    if realized_lower > 0:
        realized_status = "pass"
    elif realized_upper < 0:
        realized_status = "fail"
    else:
        realized_status = "warning"

    return pd.DataFrame(
        [
            {
                "check": "pre_oot_selection_constraints",
                "metric_value": int(challenger_found),
                "threshold": 1.0,
                "direction": "must_equal",
                "confidence_lower": math.nan,
                "confidence_upper": math.nan,
                "status": "pass" if challenger_found else "fail",
                "detail": "Growth challenger met both pre-OOT risk constraints.",
            },
            {
                "check": "oot_approval_uplift",
                "metric_value": float(incremental["incremental_approval_rate"]),
                "threshold": 0.0,
                "direction": "higher_is_better",
                "confidence_lower": math.nan,
                "confidence_upper": math.nan,
                "status": (
                    "pass" if incremental["incremental_approval_rate"] > 0 else "fail"
                ),
                "detail": "Challenger must approve a larger share of the OOT cohort.",
            },
            {
                "check": "oot_expected_credit_contribution",
                "metric_value": float(
                    incremental["incremental_expected_credit_contribution_proxy"]
                ),
                "threshold": 0.0,
                "direction": "higher_is_better",
                "confidence_lower": math.nan,
                "confidence_upper": math.nan,
                "status": (
                    "pass"
                    if incremental["incremental_expected_credit_contribution_proxy"] > 0
                    else "fail"
                ),
                "detail": "Simplified expected interest less ECL must increase.",
            },
            {
                "check": "oot_bad_rate_increase",
                "metric_value": bad_rate_increase,
                "threshold": max_bad_rate_increase,
                "direction": "lower_is_better",
                "confidence_lower": math.nan,
                "confidence_upper": math.nan,
                "status": "pass" if bad_rate_increase <= max_bad_rate_increase else "fail",
                "detail": "Approved bad-rate deterioration must remain within risk appetite.",
            },
            {
                "check": "oot_realized_credit_contribution",
                "metric_value": float(
                    incremental["incremental_realized_credit_contribution_proxy"]
                ),
                "threshold": 0.0,
                "direction": "higher_is_better",
                "confidence_lower": realized_lower,
                "confidence_upper": realized_upper,
                "status": realized_status,
                "detail": (
                    "Paired marginal-cohort bootstrap interval must be entirely above zero."
                ),
            },
        ]
    )


def _build_governance_decision(
    checks: pd.DataFrame,
    *,
    incumbent_cutoff: float,
    challenger_cutoff: float,
) -> pd.DataFrame:
    statuses = set(checks["status"])
    if "fail" in statuses:
        overall_status = "fail"
        decision = "retain_incumbent"
    elif "warning" in statuses:
        overall_status = "warning"
        decision = "controlled_live_experiment"
    else:
        overall_status = "pass"
        decision = "advance_challenger"
    exceptions = checks.loc[checks["status"].ne("pass"), "check"].tolist()
    rationale = (
        "All acceptance checks passed."
        if not exceptions
        else "Acceptance exceptions: " + ", ".join(exceptions) + "."
    )
    return pd.DataFrame(
        [
            {
                "incumbent_cutoff": incumbent_cutoff,
                "challenger_cutoff": challenger_cutoff,
                "selection_sample": "pre_oot_calibration_holdout",
                "evaluation_sample": "out_of_time",
                "overall_status": overall_status,
                "decision": decision,
                "rationale": rationale,
                "evidence_type": "retrospective_paired_champion_challenger_backtest",
                "causal_claim": "not_randomized_not_causal",
            }
        ]
    )


def _bootstrap_sum_interval(
    values: np.ndarray,
    *,
    repetitions: int,
    confidence_level: float,
    random_state: int,
) -> tuple[float, float]:
    if values.size == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(random_state)
    estimates = np.empty(repetitions, dtype=float)
    maximum_batch_elements = 1_000_000
    batch_size = max(1, min(100, maximum_batch_elements // len(values)))
    for start in range(0, repetitions, batch_size):
        stop = min(start + batch_size, repetitions)
        indices = rng.integers(0, len(values), size=(stop - start, len(values)))
        estimates[start:stop] = values[indices].sum(axis=1)
    alpha = 1 - confidence_level
    lower, upper = np.quantile(estimates, [alpha / 2, 1 - alpha / 2])
    return float(lower), float(upper)


def _validated_sample(
    pd_scores,
    target,
    exposure,
    interest_rate,
    label: str,
) -> _StrategySample:
    probabilities = np.asarray(pd_scores, dtype=float)
    outcomes = np.asarray(target)
    exposures = np.asarray(exposure, dtype=float)
    interest_rates = np.asarray(interest_rate, dtype=float)
    arrays = (probabilities, outcomes, exposures, interest_rates)
    if any(values.ndim != 1 for values in arrays):
        raise ValueError(f"{label} strategy inputs must be one-dimensional")
    if len(probabilities) == 0:
        raise ValueError(f"{label} strategy inputs must contain at least one row")
    if any(len(values) != len(probabilities) for values in arrays[1:]):
        raise ValueError(f"{label} strategy inputs must have the same length")
    if not np.isfinite(probabilities).all() or (
        (probabilities < 0) | (probabilities > 1)
    ).any():
        raise ValueError(f"{label} PD scores must be finite values between 0 and 1")
    if not np.isfinite(outcomes.astype(float)).all() or not set(np.unique(outcomes)).issubset(
        {0, 1}
    ):
        raise ValueError(f"{label} targets must contain binary 0/1 outcomes")
    if set(np.unique(outcomes)) != {0, 1}:
        raise ValueError(f"{label} targets must contain both binary classes")
    if not np.isfinite(exposures).all() or (exposures < 0).any() or exposures.sum() <= 0:
        raise ValueError(f"{label} exposures must be finite, nonnegative, and have positive total")
    if not np.isfinite(interest_rates).all() or (
        (interest_rates < 0) | (interest_rates > 1)
    ).any():
        raise ValueError(f"{label} interest rates must be finite values between 0 and 1")
    return _StrategySample(
        pd_scores=probabilities,
        target=outcomes.astype(int),
        exposure=exposures,
        interest_rate=interest_rates,
    )


def _validated_cutoffs(values: Iterable[float]) -> tuple[float, ...]:
    cutoffs = tuple(float(value) for value in values)
    if not cutoffs:
        raise ValueError("candidate_cutoffs must contain at least one value")
    if len(set(cutoffs)) != len(cutoffs):
        raise ValueError("candidate_cutoffs must not contain duplicate values")
    if not np.isfinite(cutoffs).all() or any(value <= 0 or value >= 1 for value in cutoffs):
        raise ValueError("candidate_cutoffs must contain finite values between 0 and 1")
    return tuple(sorted(cutoffs))


def _validated_rate(value: float, label: str, *, inclusive: bool = True) -> float:
    converted = float(value)
    lower_valid = converted >= 0 if inclusive else converted > 0
    upper_valid = converted <= 1 if inclusive else converted < 1
    if not math.isfinite(converted) or not lower_valid or not upper_valid:
        bounds = "between 0 and 1" if inclusive else "greater than 0 and less than 1"
        raise ValueError(f"{label} must be a finite value {bounds}")
    return converted


def _validated_repetitions(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
        raise ValueError("bootstrap_repetitions must be a positive integer")
    return int(value)


def _validated_confidence_level(value: float) -> float:
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0 or converted >= 1:
        raise ValueError("confidence_level must be greater than 0 and less than 1")
    return converted


def _safe_rate(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else float(numerator / denominator)


def _safe_mean(values: np.ndarray) -> float:
    return math.nan if values.size == 0 else float(values.mean())
