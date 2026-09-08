from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

EXPECTED_REPORTING_BASIS = "pre_aps_220_impaired_plus_past_due"
FEATURES = ("lag_logit_npl", "unemployment_rate_pct", "gdp_stress_pct")
REQUIRED_COLUMNS = {
    "quarter",
    "npl_proxy_ratio",
    "unemployment_rate_pct",
    "real_gdp_yoy_pct",
    "apra_reporting_basis",
}


@dataclass(frozen=True)
class MacroSatelliteResult:
    selected_alpha: float
    coefficients: pd.DataFrame
    tuning: pd.DataFrame
    predictions: pd.DataFrame
    performance: pd.DataFrame
    scenario_response: pd.DataFrame


def run_macro_satellite(
    data: pd.DataFrame,
    *,
    development_end: str | pd.Timestamp = "2015-12-31",
    validation_end: str | pd.Timestamp = "2018-12-31",
    oot_end: str | pd.Timestamp = "2021-12-31",
    alpha_grid: Sequence[float] = (0.01, 0.1, 1.0, 10.0, 100.0),
) -> MacroSatelliteResult:
    """Fit a directionally constrained quarterly NPL satellite with frozen OOT data."""
    development_cutoff, validation_cutoff, oot_cutoff = _validate_cutoffs(
        development_end,
        validation_end,
        oot_end,
    )
    frame = _prepare_data(data, oot_cutoff)
    sample = _build_features(frame)
    split = _split_sample(
        sample,
        development_cutoff,
        validation_cutoff,
        oot_cutoff,
    )
    alphas = _validate_alpha_grid(alpha_grid)

    tuning_rows = []
    fitted_candidates = []
    for alpha in alphas:
        candidate = _fit_model(split["development"], alpha)
        validation_prediction = _predict_ratio(candidate, split["validation"])
        validation_mae = _mae(
            split["validation"]["npl_proxy_ratio"].to_numpy(),
            validation_prediction,
        )
        tuning_rows.append(
            {
                "alpha": alpha,
                "validation_mae": validation_mae,
                "validation_observations": len(split["validation"]),
            }
        )
        fitted_candidates.append((validation_mae, alpha, candidate))
    _, selected_alpha, development_model = min(
        fitted_candidates,
        key=lambda row: (row[0], row[1]),
    )

    fit_sample = pd.concat([split["development"], split["validation"]])
    frozen_model = _fit_model(fit_sample, selected_alpha)
    predictions = _build_predictions(split, development_model, frozen_model)
    scenario_response = _build_scenario_response(
        frozen_model,
        frame.loc[frame["quarter"] == validation_cutoff].iloc[0],
    )
    return MacroSatelliteResult(
        selected_alpha=selected_alpha,
        coefficients=_coefficient_frame(frozen_model),
        tuning=pd.DataFrame(tuning_rows),
        predictions=predictions,
        performance=_performance_frame(predictions),
        scenario_response=scenario_response,
    )


@dataclass(frozen=True)
class _FittedSatellite:
    scaler: StandardScaler
    model: Ridge


def _prepare_data(data: pd.DataFrame, oot_end: pd.Timestamp) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError("Macro data missing required columns: " + ", ".join(sorted(missing)))
    if data.empty:
        raise ValueError("Macro data must contain observations")

    frame = data.loc[:, sorted(REQUIRED_COLUMNS)].copy()
    frame["quarter"] = pd.to_datetime(frame["quarter"], errors="coerce")
    if frame["quarter"].isna().any():
        raise ValueError("quarter must contain valid dates")
    if frame["quarter"].duplicated().any():
        raise ValueError("quarter must be unique")

    bases = set(frame["apra_reporting_basis"].astype(str))
    if bases != {EXPECTED_REPORTING_BASIS}:
        raise ValueError(
            "APS 220 reporting break cannot be combined with the pre-2022 NPL proxy"
        )
    if (frame["quarter"] > pd.Timestamp("2021-12-31")).any():
        raise ValueError(
            "APS 220 reporting break cannot be combined with the pre-2022 NPL proxy"
        )
    if (frame["quarter"] > oot_end).any():
        raise ValueError("Macro data contains observations after oot_end")

    frame = frame.sort_values("quarter").reset_index(drop=True)
    if not frame["quarter"].dt.is_quarter_end.all():
        raise ValueError("quarter must contain quarter-end dates")
    expected_quarters = pd.date_range(
        frame["quarter"].iloc[0],
        frame["quarter"].iloc[-1],
        freq="QE",
    )
    if not frame["quarter"].equals(pd.Series(expected_quarters, name="quarter")):
        raise ValueError("Macro data must contain contiguous quarter ends")

    for column in ["npl_proxy_ratio", "unemployment_rate_pct", "real_gdp_yoy_pct"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(frame[column].to_numpy()).all():
            raise ValueError(f"{column} must contain finite numeric values")
    if not frame["npl_proxy_ratio"].between(0.0, 1.0, inclusive="neither").all():
        raise ValueError("npl_proxy_ratio must be strictly between 0 and 1")
    return frame


def _build_features(frame: pd.DataFrame) -> pd.DataFrame:
    sample = frame.copy()
    sample["logit_npl"] = np.log(
        sample["npl_proxy_ratio"] / (1.0 - sample["npl_proxy_ratio"])
    )
    sample["lag_logit_npl"] = sample["logit_npl"].shift(1)
    sample["gdp_stress_pct"] = -sample["real_gdp_yoy_pct"]
    sample["persistence_prediction"] = sample["npl_proxy_ratio"].shift(1)
    return sample.dropna(subset=[*FEATURES, "persistence_prediction"]).reset_index(drop=True)


def _split_sample(
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
    for name, frame in split.items():
        if len(frame) < minimums[name]:
            raise ValueError(
                f"{name} split requires at least {minimums[name]} quarterly observations"
            )
    return split


def _fit_model(sample: pd.DataFrame, alpha: float) -> _FittedSatellite:
    scaler = StandardScaler().fit(sample.loc[:, FEATURES])
    model = Ridge(alpha=alpha, positive=True)
    model.fit(scaler.transform(sample.loc[:, FEATURES]), sample["logit_npl"])
    return _FittedSatellite(scaler=scaler, model=model)


def _predict_ratio(model: _FittedSatellite, sample: pd.DataFrame) -> np.ndarray:
    logit_prediction = model.model.predict(model.scaler.transform(sample.loc[:, FEATURES]))
    return 1.0 / (1.0 + np.exp(-logit_prediction))


def _build_predictions(
    split: dict[str, pd.DataFrame],
    development_model: _FittedSatellite,
    frozen_model: _FittedSatellite,
) -> pd.DataFrame:
    rows = []
    for split_name, sample in split.items():
        fitted = development_model if split_name != "oot" else frozen_model
        model_prediction = _predict_ratio(fitted, sample)
        for position, (_, row) in enumerate(sample.iterrows()):
            actual = float(row["npl_proxy_ratio"])
            prediction = float(model_prediction[position])
            rows.append(
                {
                    "quarter": row["quarter"],
                    "split": split_name,
                    "actual_npl_ratio": actual,
                    "model_prediction": prediction,
                    "persistence_prediction": float(row["persistence_prediction"]),
                    "model_residual": actual - prediction,
                    "unemployment_rate_pct": float(row["unemployment_rate_pct"]),
                    "real_gdp_yoy_pct": float(row["real_gdp_yoy_pct"]),
                }
            )
    return pd.DataFrame(rows)


def _performance_frame(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for split_name, sample in predictions.groupby("split", sort=False):
        actual = sample["actual_npl_ratio"].to_numpy()
        model_prediction = sample["model_prediction"].to_numpy()
        benchmark_prediction = sample["persistence_prediction"].to_numpy()
        model_mae = _mae(actual, model_prediction)
        benchmark_mae = _mae(actual, benchmark_prediction)
        model_rmse = _rmse(actual, model_prediction)
        benchmark_rmse = _rmse(actual, benchmark_prediction)
        rows.append(
            {
                "split": split_name,
                "observations": len(sample),
                "model_mae": model_mae,
                "persistence_mae": benchmark_mae,
                "mae_improvement_vs_persistence": _relative_improvement(
                    model_mae,
                    benchmark_mae,
                ),
                "model_rmse": model_rmse,
                "persistence_rmse": benchmark_rmse,
                "rmse_improvement_vs_persistence": _relative_improvement(
                    model_rmse,
                    benchmark_rmse,
                ),
            }
        )
    return pd.DataFrame(rows)


def _coefficient_frame(fitted: _FittedSatellite) -> pd.DataFrame:
    standardized = fitted.model.coef_
    raw = standardized / fitted.scaler.scale_
    roles = {
        "lag_logit_npl": "autoregressive",
        "unemployment_rate_pct": "macro_stress",
        "gdp_stress_pct": "macro_stress",
    }
    return pd.DataFrame(
        {
            "feature": FEATURES,
            "feature_role": [roles[feature] for feature in FEATURES],
            "standardized_coefficient": standardized,
            "raw_coefficient": raw,
            "constraint": "nonnegative",
        }
    )


def _build_scenario_response(
    fitted: _FittedSatellite,
    anchor: pd.Series,
) -> pd.DataFrame:
    shocks = (
        ("upside", -0.5, 2.0),
        ("base", 0.0, 0.0),
        ("downside", 3.0, -6.0),
    )
    lag_logit = math.log(
        float(anchor["npl_proxy_ratio"]) / (1.0 - float(anchor["npl_proxy_ratio"]))
    )
    scenario_frame = pd.DataFrame(
        [
            {
                "scenario": scenario,
                "anchor_quarter": anchor["quarter"],
                "unemployment_shock_pp": unemployment_shock,
                "real_gdp_growth_shock_pp": gdp_shock,
                "lag_logit_npl": lag_logit,
                "unemployment_rate_pct": (
                    float(anchor["unemployment_rate_pct"]) + unemployment_shock
                ),
                "real_gdp_yoy_pct": float(anchor["real_gdp_yoy_pct"]) + gdp_shock,
            }
            for scenario, unemployment_shock, gdp_shock in shocks
        ]
    )
    scenario_frame["gdp_stress_pct"] = -scenario_frame["real_gdp_yoy_pct"]
    scenario_frame["predicted_npl_ratio"] = _predict_ratio(fitted, scenario_frame)
    base_prediction = float(
        scenario_frame.loc[
            scenario_frame["scenario"] == "base",
            "predicted_npl_ratio",
        ].iloc[0]
    )
    scenario_frame["npl_multiplier"] = (
        scenario_frame["predicted_npl_ratio"] / base_prediction
    )
    scenario_frame["evidence_use"] = "sensitivity_only"
    return scenario_frame.drop(columns=["lag_logit_npl", "gdp_stress_pct"])


def _validate_cutoffs(
    development_end: str | pd.Timestamp,
    validation_end: str | pd.Timestamp,
    oot_end: str | pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    cutoffs = tuple(pd.Timestamp(value) for value in (development_end, validation_end, oot_end))
    if not cutoffs[0] < cutoffs[1] < cutoffs[2]:
        raise ValueError("development_end, validation_end, and oot_end must be increasing")
    if not all(cutoff.is_quarter_end for cutoff in cutoffs):
        raise ValueError("Model cutoffs must be quarter-end dates")
    return cutoffs


def _validate_alpha_grid(alpha_grid: Sequence[float]) -> tuple[float, ...]:
    if not alpha_grid:
        raise ValueError("alpha_grid must contain at least one value")
    values = tuple(float(value) for value in alpha_grid)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("alpha_grid values must be finite and positive")
    if len(values) != len(set(values)):
        raise ValueError("alpha_grid values must be unique")
    return tuple(sorted(values))


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(actual - predicted))))


def _relative_improvement(model_error: float, benchmark_error: float) -> float:
    if benchmark_error == 0:
        return 0.0
    return (benchmark_error - model_error) / benchmark_error
