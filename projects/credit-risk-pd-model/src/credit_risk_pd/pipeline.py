from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from credit_risk_pd.calibration import (
    LogisticPDRecalibrator,
    RecalibratedPDModel,
    calibration_diagnostics,
)
from credit_risk_pd.config import DEFAULT_CONFIG, ModelConfig
from credit_risk_pd.data import (
    generate_synthetic_credit_data,
    load_credit_data,
    make_out_of_time_split,
    make_temporal_calibration_split,
)
from credit_risk_pd.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    split_features_target,
)
from credit_risk_pd.metrics import (
    calibration_table,
    classification_metrics,
    permutation_feature_importance,
)
from credit_risk_pd.model import candidate_models
from credit_risk_pd.monitoring import psi_report
from credit_risk_pd.reporting import generate_model_report
from credit_risk_pd.strategy import approval_strategy_table
from credit_risk_pd.woe import calculate_woe_iv


def run_pd_modelling_workflow(
    input_path: str | Path | None = None,
    output_dir: str | Path = "reports",
    model_dir: str | Path = "models",
    config: ModelConfig = DEFAULT_CONFIG,
) -> dict[str, Path]:
    """Run the end-to-end PD modelling workflow and export portfolio-ready artefacts."""
    output_path = Path(output_dir)
    model_path = Path(model_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model_path.mkdir(parents=True, exist_ok=True)

    if input_path:
        data = load_credit_data(input_path, config)
    else:
        data = generate_synthetic_credit_data(random_state=config.random_state)

    development, oot = make_out_of_time_split(data, config.oot_cutoff_date, config.date_col)
    model_development, calibration_holdout = make_temporal_calibration_split(
        development,
        config.calibration_fraction,
        config.date_col,
    )
    x_model_development, y_model_development = split_features_target(model_development, config)
    x_calibration, y_calibration = split_features_target(calibration_holdout, config)
    x_oot, y_oot = split_features_target(oot, config)
    _require_binary_sample(y_model_development, "Model-development")
    _require_binary_sample(y_calibration, "Calibration holdout")
    _require_binary_sample(y_oot, "Out-of-time")

    metric_rows = []
    selection_rows = []
    predictions = pd.DataFrame(
        {
            config.id_col: oot[config.id_col],
            config.date_col: oot[config.date_col],
            "home_ownership": oot["home_ownership"].fillna("other").astype(str),
            "purpose": oot["purpose"].fillna("other").astype(str),
            **{feature: x_oot[feature] for feature in NUMERIC_FEATURES},
            "actual_default": y_oot,
        }
    )
    trained_models = {}

    for model_name, estimator in candidate_models(config).items():
        estimator.fit(x_model_development, y_model_development)
        calibration_scores = estimator.predict_proba(x_calibration)[:, 1]
        calibration_metrics = classification_metrics(
            y_calibration,
            calibration_scores,
            threshold=config.test_threshold,
        )
        selection_rows.append(
            {
                "model": model_name,
                "model_development_accounts": len(model_development),
                "calibration_holdout_accounts": len(calibration_holdout),
                "model_development_start": _date_min(model_development, config.date_col),
                "model_development_end": _date_max(model_development, config.date_col),
                "calibration_holdout_start": _date_min(calibration_holdout, config.date_col),
                "calibration_holdout_end": _date_max(calibration_holdout, config.date_col),
                "calibration_holdout_roc_auc": calibration_metrics["roc_auc"],
                "selected_model": False,
            }
        )

        scores = estimator.predict_proba(x_oot)[:, 1]
        metrics = classification_metrics(y_oot, scores, threshold=config.test_threshold)
        metric_rows.append(
            {
                "model": model_name,
                "score_type": "raw",
                "classification_threshold": config.test_threshold,
                **metrics,
            }
        )
        predictions[f"{model_name}_pd"] = scores
        trained_models[model_name] = estimator

    selection_df = pd.DataFrame(selection_rows)
    best_model_name = selection_df.sort_values(
        ["calibration_holdout_roc_auc", "model"],
        ascending=[False, True],
    ).iloc[0]["model"]
    selection_df.loc[selection_df["model"].eq(best_model_name), "selected_model"] = True

    best_raw_scores = pd.Series(
        trained_models[best_model_name].predict_proba(x_oot)[:, 1],
        index=oot.index,
        name="selected_model_raw_pd",
    )
    calibration_raw_scores = trained_models[best_model_name].predict_proba(x_calibration)[:, 1]
    recalibrator = LogisticPDRecalibrator().fit(calibration_raw_scores, y_calibration)
    recalibrated_scores = recalibrator.transform(best_raw_scores)
    predictions["selected_model"] = best_model_name
    predictions["selected_model_raw_pd"] = best_raw_scores.to_numpy()
    predictions["recalibrated_pd"] = recalibrated_scores.to_numpy()

    recalibrated_metrics = classification_metrics(
        y_oot,
        recalibrated_scores,
        threshold=config.test_threshold,
    )
    metric_rows.append(
        {
            "model": best_model_name,
            "score_type": "recalibrated",
            "classification_threshold": config.test_threshold,
            **recalibrated_metrics,
        }
    )
    metrics_df = pd.DataFrame(metric_rows)

    raw_diagnostics = calibration_diagnostics(y_oot, best_raw_scores)
    recalibrated_diagnostics = calibration_diagnostics(y_oot, recalibrated_scores)
    recalibration_df = pd.DataFrame(
        [
            _calibration_summary_row(
                best_model_name,
                "raw",
                raw_diagnostics,
                recalibrator,
            ),
            _calibration_summary_row(
                best_model_name,
                "recalibrated",
                recalibrated_diagnostics,
                recalibrator,
            ),
        ]
    )

    calibration_df = calibration_table(y_oot, recalibrated_scores)
    strategy_df = approval_strategy_table(
        recalibrated_scores,
        y_oot,
        oot["loan_amount"],
        thresholds=config.approval_thresholds,
        lgd=config.lgd,
    )
    psi_df = psi_report(x_model_development, x_oot, NUMERIC_FEATURES)
    woe_bins_df, woe_summary_df = calculate_woe_iv(
        x_model_development,
        y_model_development,
        NUMERIC_FEATURES,
        CATEGORICAL_FEATURES,
    )
    feature_importance_df = permutation_feature_importance(
        trained_models[best_model_name],
        x_oot,
        y_oot,
        random_state=config.random_state,
    )

    metrics_file = output_path / "model_metrics.csv"
    calibration_file = output_path / "calibration_table.csv"
    recalibration_file = output_path / "recalibration_summary.csv"
    strategy_file = output_path / "approval_strategy.csv"
    selection_file = output_path / "model_selection_audit.csv"
    predictions_file = output_path / "oot_predictions.csv"
    psi_file = output_path / "psi_report.csv"
    woe_bins_file = output_path / "woe_bins.csv"
    woe_summary_file = output_path / "woe_summary.csv"
    feature_importance_file = output_path / "feature_importance.csv"
    model_file = model_path / f"{best_model_name}_recalibrated.joblib"

    metrics_df.to_csv(metrics_file, index=False)
    calibration_df.to_csv(calibration_file, index=False)
    recalibration_df.to_csv(recalibration_file, index=False)
    strategy_df.to_csv(strategy_file, index=False)
    selection_df.to_csv(selection_file, index=False)
    predictions.to_csv(predictions_file, index=False)
    psi_df.to_csv(psi_file, index=False)
    woe_bins_df.to_csv(woe_bins_file, index=False)
    woe_summary_df.to_csv(woe_summary_file, index=False)
    feature_importance_df.to_csv(feature_importance_file, index=False)
    joblib.dump(
        RecalibratedPDModel(
            selected_model_name=best_model_name,
            base_estimator=trained_models[best_model_name],
            recalibrator=recalibrator,
        ),
        model_file,
    )
    report_file = generate_model_report(output_path)

    return {
        "metrics": metrics_file,
        "calibration": calibration_file,
        "recalibration_summary": recalibration_file,
        "approval_strategy": strategy_file,
        "model_selection_audit": selection_file,
        "predictions": predictions_file,
        "psi": psi_file,
        "woe_bins": woe_bins_file,
        "woe_summary": woe_summary_file,
        "feature_importance": feature_importance_file,
        "report": report_file,
        "model": model_file,
    }


def _date_min(data: pd.DataFrame, date_col: str) -> str:
    return pd.to_datetime(data[date_col]).min().date().isoformat()


def _date_max(data: pd.DataFrame, date_col: str) -> str:
    return pd.to_datetime(data[date_col]).max().date().isoformat()


def _calibration_summary_row(
    model_name: str,
    score_type: str,
    diagnostics: dict[str, float],
    recalibrator: LogisticPDRecalibrator,
) -> dict[str, float | str]:
    return {
        "model": model_name,
        "score_type": score_type,
        "evaluation_sample": "out_of_time",
        "recalibration_fit_sample": "pre_oot_calibration_holdout",
        "recalibration_fit_intercept": float(recalibrator.intercept_),
        "recalibration_fit_slope": float(recalibrator.slope_),
        "calibration_intercept": diagnostics["calibration_intercept"],
        "calibration_slope": diagnostics["calibration_slope"],
        "brier_score": diagnostics["brier_score"],
        "log_loss": diagnostics["log_loss"],
        "mean_pd": diagnostics["mean_pd"],
        "observed_default_rate": diagnostics["observed_default_rate"],
    }


def _require_binary_sample(target: pd.Series, sample_name: str) -> None:
    if target.isna().any():
        raise ValueError(f"{sample_name} target must not contain missing values.")
    unique_values = set(target.unique().tolist())
    if not unique_values.issubset({0, 1}):
        raise ValueError(f"{sample_name} target must contain only binary 0/1 outcomes.")
    if len(unique_values) < 2:
        raise ValueError(
            f"{sample_name} sample must contain both default and non-default observations."
        )
