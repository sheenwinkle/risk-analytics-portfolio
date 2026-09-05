from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import sklearn

from credit_risk_pd.config import ModelConfig
from credit_risk_pd.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

CONTRACT_VERSION = "1.0"
SAMPLE_ROLES = ("model_development", "calibration_holdout")
PARAMETER_COLUMNS = (
    "model",
    "feature_name",
    "parameter_type",
    "reference_value",
)


def write_model_validation_bundle(
    *,
    model_development: pd.DataFrame,
    calibration_holdout: pd.DataFrame,
    x_model_development: pd.DataFrame,
    y_model_development: pd.Series,
    x_calibration: pd.DataFrame,
    y_calibration: pd.Series,
    trained_models: dict[str, object],
    config: ModelConfig,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Export local development evidence for independent model replication."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    sample = pd.concat(
        [
            _contract_sample(
                model_development,
                x_model_development,
                y_model_development,
                role=SAMPLE_ROLES[0],
                config=config,
            ),
            _contract_sample(
                calibration_holdout,
                x_calibration,
                y_calibration,
                role=SAMPLE_ROLES[1],
                config=config,
            ),
        ],
        ignore_index=True,
    )
    parameters = build_model_parameter_reference(trained_models)
    specification = build_model_development_spec(config)

    sample_path = destination / "model_development_sample.csv"
    specification_path = destination / "model_development_spec.json"
    parameter_path = destination / "model_parameter_reference.csv"
    sample.to_csv(sample_path, index=False, lineterminator="\n")
    specification_path.write_text(
        json.dumps(specification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    parameters.to_csv(
        parameter_path,
        index=False,
        float_format="%.17g",
        lineterminator="\n",
    )
    return {
        "model_development_sample": sample_path,
        "model_development_spec": specification_path,
        "model_parameter_reference": parameter_path,
    }


def build_model_development_spec(config: ModelConfig) -> dict[str, object]:
    return {
        "candidate_models": {
            "logistic_regression": {
                "estimator": "sklearn.linear_model.LogisticRegression",
                "parameters": {
                    "class_weight": "balanced",
                    "max_iter": 1_000,
                    "random_state": config.random_state,
                },
            },
            "random_forest": {
                "estimator": "sklearn.ensemble.RandomForestClassifier",
                "parameters": {
                    "class_weight": "balanced_subsample",
                    "min_samples_leaf": 40,
                    "n_estimators": 180,
                    "n_jobs": -1,
                    "random_state": config.random_state,
                },
            },
        },
        "categorical_features": CATEGORICAL_FEATURES,
        "contract_version": CONTRACT_VERSION,
        "date_column": config.date_col,
        "derived_features": {
            "loan_to_income": "loan_amount / max(annual_income, 1)",
        },
        "id_column": config.id_col,
        "implementation": {
            "library": "scikit-learn",
            "version": sklearn.__version__,
        },
        "numeric_features": NUMERIC_FEATURES,
        "preprocessing": {
            "categorical": ["most_frequent_imputation", "one_hot_ignore_unknown"],
            "numeric": ["median_imputation", "standard_scaling"],
        },
        "roles": list(SAMPLE_ROLES),
        "sample_role_column": "sample_role",
        "selection_metric": "roc_auc",
        "selection_tie_break": "model_name_ascending",
        "target_column": "actual_default",
    }


def build_model_parameter_reference(trained_models: dict[str, object]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model_name, estimator in trained_models.items():
        named_steps = getattr(estimator, "named_steps", {})
        preprocessor = named_steps.get("preprocessor")
        classifier = named_steps.get("classifier")
        if preprocessor is None or classifier is None:
            continue

        feature_names = [
            str(value).split("__", maxsplit=1)[-1]
            for value in preprocessor.get_feature_names_out()
        ]
        if hasattr(classifier, "coef_"):
            parameter_type = "standardized_coefficient"
            values = classifier.coef_[0]
        elif hasattr(classifier, "feature_importances_"):
            parameter_type = "impurity_importance"
            values = classifier.feature_importances_
        else:
            continue

        rows.extend(
            {
                "model": model_name,
                "feature_name": feature_name,
                "parameter_type": parameter_type,
                "reference_value": float(value),
            }
            for feature_name, value in zip(feature_names, values, strict=True)
        )
    return pd.DataFrame(rows, columns=PARAMETER_COLUMNS)


def _contract_sample(
    source: pd.DataFrame,
    features: pd.DataFrame,
    target: pd.Series,
    *,
    role: str,
    config: ModelConfig,
) -> pd.DataFrame:
    sample = pd.DataFrame(
        {
            config.id_col: source[config.id_col].astype("string").to_numpy(),
            config.date_col: pd.to_datetime(source[config.date_col])
            .dt.strftime("%Y-%m-%d")
            .to_numpy(),
            "sample_role": role,
        }
    )
    for feature in [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]:
        sample[feature] = features[feature].to_numpy()
    sample["actual_default"] = target.astype(int).to_numpy()
    return sample
