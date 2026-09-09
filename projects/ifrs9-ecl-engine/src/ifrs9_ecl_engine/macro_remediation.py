from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from ifrs9_ecl_engine.macro_satellite import (
    _prepare_data,
    _validate_alpha_grid,
    _validate_cutoffs,
    run_macro_satellite,
)


@dataclass(frozen=True)
class MacroCandidateSpec:
    candidate_id: str
    target_form: str
    forecast_horizon_quarters: int
    features: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class MacroRemediationResult:
    candidate_register: pd.DataFrame
    tuning: pd.DataFrame
    selection: pd.DataFrame
    coefficients: pd.DataFrame
    predictions: pd.DataFrame
    performance: pd.DataFrame
    oot_comparison: pd.DataFrame
    governance_decision: pd.DataFrame


@dataclass(frozen=True)
class _FittedCandidate:
    specification: MacroCandidateSpec
    scaler: StandardScaler
    model: Ridge


DEFAULT_CANDIDATES = (
    MacroCandidateSpec(
        candidate_id="ratio_change_lagged_macro",
        target_form="ratio_change",
        forecast_horizon_quarters=1,
        features=("lag_unemployment_change", "lag_gdp_stress_change"),
        rationale="Model the quarterly NPL-ratio movement from lagged macro movements.",
    ),
    MacroCandidateSpec(
        candidate_id="dynamic_ratio_change_lagged_macro",
        target_form="ratio_change",
        forecast_horizon_quarters=1,
        features=(
            "lag_npl_change",
            "lag_unemployment_change",
            "lag_gdp_stress_change",
        ),
        rationale="Add lagged NPL momentum to the quarterly ratio-change specification.",
    ),
    MacroCandidateSpec(
        candidate_id="logit_change_lagged_macro",
        target_form="logit_change",
        forecast_horizon_quarters=1,
        features=(
            "lag_logit_npl_change",
            "lag_unemployment_change",
            "lag_gdp_stress_change",
        ),
        rationale="Test a bounded logit-change target with lagged dynamic drivers.",
    ),
    MacroCandidateSpec(
        candidate_id="ratio_change_two_quarter",
        target_form="ratio_change",
        forecast_horizon_quarters=2,
        features=(
            "lag_npl_change",
            "lag_unemployment_change",
            "lag_gdp_stress_change",
        ),
        rationale="Test a two-quarter forecast horizon with horizon-matched lagged changes.",
    ),
)


def run_macro_satellite_remediation(
    data: pd.DataFrame,
    *,
    development_end: str | pd.Timestamp = "2015-12-31",
    validation_end: str | pd.Timestamp = "2018-12-31",
    oot_end: str | pd.Timestamp = "2021-12-31",
    alpha_grid: Sequence[float] = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0),
) -> MacroRemediationResult:
    """Select a lag-compatible challenger without using the reused OOT window."""
    development_cutoff, validation_cutoff, oot_cutoff = _validate_cutoffs(
        development_end,
        validation_end,
        oot_end,
    )
    frame = _prepare_data(data, oot_cutoff)
    alphas = _validate_alpha_grid(alpha_grid)
    candidate_register = _candidate_register(DEFAULT_CANDIDATES)

    tuning_rows: list[dict[str, object]] = []
    development_models: dict[tuple[str, float], _FittedCandidate] = {}
    samples: dict[str, dict[str, pd.DataFrame]] = {}
    for specification in DEFAULT_CANDIDATES:
        sample = _build_candidate_sample(frame, specification)
        split = _split_candidate_sample(
            sample,
            development_cutoff,
            validation_cutoff,
            oot_cutoff,
        )
        samples[specification.candidate_id] = split
        for alpha in alphas:
            fitted = _fit_candidate(split["development"], specification, alpha)
            development_models[(specification.candidate_id, alpha)] = fitted
            model_prediction = _predict_ratio(fitted, split["validation"])
            actual = split["validation"]["npl_proxy_ratio"].to_numpy(dtype=float)
            persistence = split["validation"]["persistence_prediction"].to_numpy(
                dtype=float
            )
            model_mae = _mae(actual, model_prediction)
            persistence_mae = _mae(actual, persistence)
            model_rmse = _rmse(actual, model_prediction)
            persistence_rmse = _rmse(actual, persistence)
            tuning_rows.append(
                {
                    "candidate_id": specification.candidate_id,
                    "target_form": specification.target_form,
                    "forecast_horizon_quarters": (
                        specification.forecast_horizon_quarters
                    ),
                    "feature_count": len(specification.features),
                    "alpha": alpha,
                    "validation_observations": len(split["validation"]),
                    "validation_model_mae": model_mae,
                    "validation_persistence_mae": persistence_mae,
                    "validation_mae_ratio": model_mae / persistence_mae,
                    "validation_model_rmse": model_rmse,
                    "validation_persistence_rmse": persistence_rmse,
                    "validation_rmse_ratio": model_rmse / persistence_rmse,
                    "selection_score": 0.5
                    * (
                        model_mae / persistence_mae
                        + model_rmse / persistence_rmse
                    ),
                }
            )

    tuning = pd.DataFrame(tuning_rows)
    selected = tuning.sort_values(
        [
            "selection_score",
            "validation_model_mae",
            "feature_count",
            "forecast_horizon_quarters",
            "candidate_id",
            "alpha",
        ],
        kind="mergesort",
    ).iloc[0]
    selected_specification = next(
        specification
        for specification in DEFAULT_CANDIDATES
        if specification.candidate_id == selected["candidate_id"]
    )
    selected_alpha = float(selected["alpha"])
    tuning["selected"] = (
        tuning["candidate_id"].eq(selected_specification.candidate_id)
        & tuning["alpha"].eq(selected_alpha)
    )
    tuning = tuning.sort_values(
        ["candidate_id", "alpha"],
        kind="mergesort",
    ).reset_index(drop=True)

    selected_split = samples[selected_specification.candidate_id]
    fit_sample = pd.concat(
        [selected_split["development"], selected_split["validation"]],
        ignore_index=True,
    )
    frozen_model = _fit_candidate(
        fit_sample,
        selected_specification,
        selected_alpha,
    )
    development_model = development_models[
        (selected_specification.candidate_id, selected_alpha)
    ]
    predictions = _build_predictions(
        selected_split,
        development_model,
        frozen_model,
    )
    performance = _performance_frame(predictions)
    validation_window = _quarter_window(selected_split["validation"])
    oot_window = _quarter_window(selected_split["oot"])
    incumbent = run_macro_satellite(
        frame,
        development_end=development_cutoff,
        validation_end=validation_cutoff,
        oot_end=oot_cutoff,
    )
    oot_comparison = _build_oot_comparison(
        performance,
        incumbent.performance,
        selected_specification,
        oot_window,
    )
    governance_decision = _build_governance_decision(oot_comparison)
    selection = pd.DataFrame(
        [
            {
                "selected_candidate_id": selected_specification.candidate_id,
                "selected_alpha": selected_alpha,
                "selection_metric": "mean_validation_mae_rmse_ratio",
                "selection_score": float(selected["selection_score"]),
                "selection_window": validation_window,
                "selection_observations": int(selected["validation_observations"]),
                "eligible_candidates": len(DEFAULT_CANDIDATES),
                "hyperparameters_evaluated": len(tuning),
                "oot_used_for_selection": False,
                "oot_evidence_freshness": f"reused_{oot_window.replace('-', '_')}",
            }
        ]
    )
    return MacroRemediationResult(
        candidate_register=candidate_register,
        tuning=tuning,
        selection=selection,
        coefficients=_coefficient_frame(frozen_model),
        predictions=predictions,
        performance=performance,
        oot_comparison=oot_comparison,
        governance_decision=governance_decision,
    )


def _quarter_window(frame: pd.DataFrame) -> str:
    quarters = pd.to_datetime(frame["quarter"])
    return f"{quarters.min().to_period('Q')}-{quarters.max().to_period('Q')}"


def _candidate_register(
    specifications: tuple[MacroCandidateSpec, ...],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": specification.candidate_id,
                "target_form": specification.target_form,
                "forecast_horizon_quarters": (
                    specification.forecast_horizon_quarters
                ),
                "macro_lag_quarters": specification.forecast_horizon_quarters,
                "features": "|".join(specification.features),
                "coefficient_constraint": "nonnegative",
                "release_compatible": True,
                "eligible_for_selection": True,
                "rationale": specification.rationale,
            }
            for specification in specifications
        ]
    )


def _build_candidate_sample(
    frame: pd.DataFrame,
    specification: MacroCandidateSpec,
) -> pd.DataFrame:
    horizon = specification.forecast_horizon_quarters
    sample = frame.copy()
    sample["logit_npl"] = np.log(
        sample["npl_proxy_ratio"] / (1.0 - sample["npl_proxy_ratio"])
    )
    sample["gdp_stress_pct"] = -sample["real_gdp_yoy_pct"]
    sample["known_npl_ratio"] = sample["npl_proxy_ratio"].shift(horizon)
    sample["known_logit_npl"] = sample["logit_npl"].shift(horizon)
    sample["lag_npl_change"] = sample["npl_proxy_ratio"].diff(horizon).shift(
        horizon
    )
    sample["lag_logit_npl_change"] = sample["logit_npl"].diff(horizon).shift(
        horizon
    )
    sample["lag_unemployment_change"] = sample[
        "unemployment_rate_pct"
    ].diff(horizon).shift(horizon)
    sample["lag_gdp_stress_change"] = sample["gdp_stress_pct"].diff(
        horizon
    ).shift(horizon)
    if specification.target_form == "ratio_change":
        sample["model_target"] = (
            sample["npl_proxy_ratio"] - sample["known_npl_ratio"]
        )
    elif specification.target_form == "logit_change":
        sample["model_target"] = sample["logit_npl"] - sample["known_logit_npl"]
    else:
        raise ValueError(f"Unsupported target form: {specification.target_form}")
    sample["persistence_prediction"] = sample["known_npl_ratio"]
    required = [
        *specification.features,
        "known_npl_ratio",
        "known_logit_npl",
        "model_target",
        "persistence_prediction",
    ]
    return sample.dropna(subset=required).reset_index(drop=True)


def _split_candidate_sample(
    sample: pd.DataFrame,
    development_end: pd.Timestamp,
    validation_end: pd.Timestamp,
    oot_end: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    split = {
        "development": sample[sample["quarter"] <= development_end].copy(),
        "validation": sample[
            (sample["quarter"] > development_end)
            & (sample["quarter"] <= validation_end)
        ].copy(),
        "oot": sample[
            (sample["quarter"] > validation_end) & (sample["quarter"] <= oot_end)
        ].copy(),
    }
    minimums = {"development": 12, "validation": 4, "oot": 4}
    for split_name, split_frame in split.items():
        if len(split_frame) < minimums[split_name]:
            raise ValueError(
                f"{split_name} split requires at least "
                f"{minimums[split_name]} quarterly observations"
            )
    return split


def _fit_candidate(
    sample: pd.DataFrame,
    specification: MacroCandidateSpec,
    alpha: float,
) -> _FittedCandidate:
    scaler = StandardScaler().fit(sample.loc[:, specification.features])
    model = Ridge(alpha=alpha, positive=True)
    model.fit(
        scaler.transform(sample.loc[:, specification.features]),
        sample["model_target"],
    )
    return _FittedCandidate(
        specification=specification,
        scaler=scaler,
        model=model,
    )


def _predict_ratio(fitted: _FittedCandidate, sample: pd.DataFrame) -> np.ndarray:
    target_prediction = fitted.model.predict(
        fitted.scaler.transform(sample.loc[:, fitted.specification.features])
    )
    if fitted.specification.target_form == "ratio_change":
        ratio_prediction = sample["known_npl_ratio"].to_numpy() + target_prediction
    else:
        logit_prediction = sample["known_logit_npl"].to_numpy() + target_prediction
        ratio_prediction = 1.0 / (1.0 + np.exp(-logit_prediction))
    return np.clip(ratio_prediction, 1e-9, 1.0 - 1e-9)


def _build_predictions(
    split: dict[str, pd.DataFrame],
    development_model: _FittedCandidate,
    frozen_model: _FittedCandidate,
) -> pd.DataFrame:
    rows = []
    specification = frozen_model.specification
    for split_name, sample in split.items():
        fitted = development_model if split_name != "oot" else frozen_model
        model_prediction = _predict_ratio(fitted, sample)
        for position, (_, row) in enumerate(sample.iterrows()):
            actual = float(row["npl_proxy_ratio"])
            prediction = float(model_prediction[position])
            rows.append(
                {
                    "quarter": row["quarter"],
                    "forecast_origin_quarter": row["quarter"]
                    - pd.offsets.QuarterEnd(specification.forecast_horizon_quarters),
                    "split": split_name,
                    "candidate_id": specification.candidate_id,
                    "target_form": specification.target_form,
                    "forecast_horizon_quarters": (
                        specification.forecast_horizon_quarters
                    ),
                    "actual_npl_ratio": actual,
                    "model_prediction": prediction,
                    "persistence_prediction": float(row["persistence_prediction"]),
                    "model_residual": actual - prediction,
                }
            )
    return pd.DataFrame(rows)


def _coefficient_frame(fitted: _FittedCandidate) -> pd.DataFrame:
    standardized = fitted.model.coef_
    raw = standardized / fitted.scaler.scale_
    roles = {
        "lag_npl_change": "credit_momentum",
        "lag_logit_npl_change": "credit_momentum",
        "lag_unemployment_change": "macro_stress",
        "lag_gdp_stress_change": "macro_stress",
    }
    return pd.DataFrame(
        {
            "candidate_id": fitted.specification.candidate_id,
            "feature": fitted.specification.features,
            "feature_role": [roles[feature] for feature in fitted.specification.features],
            "standardized_coefficient": standardized,
            "raw_coefficient": raw,
            "constraint": "nonnegative",
        }
    )


def _performance_frame(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for split_name, sample in predictions.groupby("split", sort=False):
        actual = sample["actual_npl_ratio"].to_numpy(dtype=float)
        model = sample["model_prediction"].to_numpy(dtype=float)
        persistence = sample["persistence_prediction"].to_numpy(dtype=float)
        model_mae = _mae(actual, model)
        persistence_mae = _mae(actual, persistence)
        model_rmse = _rmse(actual, model)
        persistence_rmse = _rmse(actual, persistence)
        rows.append(
            {
                "split": split_name,
                "observations": len(sample),
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
        )
    return pd.DataFrame(rows)


def _build_oot_comparison(
    selected_performance: pd.DataFrame,
    incumbent_performance: pd.DataFrame,
    specification: MacroCandidateSpec,
    evidence_window: str,
) -> pd.DataFrame:
    selected = selected_performance.set_index("split").loc["oot"]
    incumbent = incumbent_performance.set_index("split").loc["oot"]
    incumbent_mae = float(incumbent["model_mae"])
    incumbent_rmse = float(incumbent["model_rmse"])
    rows = []
    for variant, candidate_id, metrics, horizon in (
        (
            "incumbent_satellite",
            "contemporaneous_logit_level",
            incumbent,
            1,
        ),
        (
            "selected_remediation",
            specification.candidate_id,
            selected,
            specification.forecast_horizon_quarters,
        ),
    ):
        model_mae = float(metrics["model_mae"])
        model_rmse = float(metrics["model_rmse"])
        rows.append(
            {
                "variant": variant,
                "candidate_id": candidate_id,
                "forecast_horizon_quarters": horizon,
                "evidence_window": evidence_window,
                "evidence_freshness": "reused_oot",
                "observations": int(metrics["observations"]),
                "model_mae": model_mae,
                "persistence_mae": float(metrics["persistence_mae"]),
                "mae_improvement_vs_persistence": float(
                    metrics["mae_improvement_vs_persistence"]
                ),
                "model_rmse": model_rmse,
                "persistence_rmse": float(metrics["persistence_rmse"]),
                "rmse_improvement_vs_persistence": float(
                    metrics["rmse_improvement_vs_persistence"]
                ),
                "mae_reduction_vs_incumbent": (
                    incumbent_mae - model_mae
                )
                / incumbent_mae,
                "rmse_reduction_vs_incumbent": (
                    incumbent_rmse - model_rmse
                )
                / incumbent_rmse,
            }
        )
    return pd.DataFrame(rows)


def _build_governance_decision(oot_comparison: pd.DataFrame) -> pd.DataFrame:
    challenger = oot_comparison.set_index("variant").loc["selected_remediation"]
    if (
        challenger["mae_improvement_vs_persistence"] >= 0
        and challenger["rmse_improvement_vs_persistence"] >= 0
    ):
        retest_result = "benchmark_pass_on_reused_oot"
    elif (
        challenger["mae_improvement_vs_persistence"] >= 0
        or challenger["rmse_improvement_vs_persistence"] >= 0
    ):
        retest_result = "mixed_benchmark_evidence"
    else:
        retest_result = "benchmark_fail"
    return pd.DataFrame(
        [
            {
                "finding_id": "MSV-001",
                "retest_result": retest_result,
                "developer_recommendation": "retain_restricted_use",
                "use_restriction": "sensitivity_only",
                "evidence_freshness": "reused_oot",
                "finding_closure_claimed": False,
                "closure_blocker": (
                    "Fresh post-selection OOT outcomes and real-time macro vintages "
                    "are not available."
                ),
            }
        ]
    )


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(actual - predicted))))
