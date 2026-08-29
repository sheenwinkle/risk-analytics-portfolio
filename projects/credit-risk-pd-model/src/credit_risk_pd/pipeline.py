from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from credit_risk_pd.config import DEFAULT_CONFIG, ModelConfig
from credit_risk_pd.data import generate_synthetic_credit_data, load_credit_data, make_out_of_time_split
from credit_risk_pd.features import NUMERIC_FEATURES, split_features_target
from credit_risk_pd.metrics import calibration_table, classification_metrics
from credit_risk_pd.model import candidate_models
from credit_risk_pd.monitoring import psi_report
from credit_risk_pd.reporting import generate_model_report


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

    train, oot = make_out_of_time_split(data, config.oot_cutoff_date, config.date_col)
    x_train, y_train = split_features_target(train, config)
    x_oot, y_oot = split_features_target(oot, config)

    metric_rows = []
    predictions = pd.DataFrame(
        {
            config.id_col: oot[config.id_col],
            config.date_col: oot[config.date_col],
            "actual_default": y_oot,
        }
    )
    trained_models = {}

    for model_name, estimator in candidate_models(config).items():
        estimator.fit(x_train, y_train)
        scores = estimator.predict_proba(x_oot)[:, 1]
        metrics = classification_metrics(y_oot, scores, threshold=config.test_threshold)
        metric_rows.append({"model": model_name, **metrics})
        predictions[f"{model_name}_pd"] = scores
        trained_models[model_name] = estimator

    metrics_df = pd.DataFrame(metric_rows).sort_values("roc_auc", ascending=False)
    best_model_name = metrics_df.iloc[0]["model"]
    best_scores = predictions[f"{best_model_name}_pd"]

    calibration_df = calibration_table(y_oot, best_scores)
    psi_df = psi_report(x_train, x_oot, NUMERIC_FEATURES)

    metrics_file = output_path / "model_metrics.csv"
    calibration_file = output_path / "calibration_table.csv"
    predictions_file = output_path / "oot_predictions.csv"
    psi_file = output_path / "psi_report.csv"
    model_file = model_path / f"{best_model_name}.joblib"

    metrics_df.to_csv(metrics_file, index=False)
    calibration_df.to_csv(calibration_file, index=False)
    predictions.to_csv(predictions_file, index=False)
    psi_df.to_csv(psi_file, index=False)
    joblib.dump(trained_models[best_model_name], model_file)
    report_file = generate_model_report(output_path)

    return {
        "metrics": metrics_file,
        "calibration": calibration_file,
        "predictions": predictions_file,
        "psi": psi_file,
        "report": report_file,
        "model": model_file,
    }

