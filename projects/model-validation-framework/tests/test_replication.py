from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from model_validation import (
    Project1DevelopmentAdapter,
    run_model_replication,
    run_model_replication_pipeline,
)

NUMERIC_FEATURES = [
    "age",
    "annual_income",
    "debt_to_income",
    "credit_utilisation",
    "delinquencies_2y",
    "loan_amount",
    "interest_rate",
    "employment_length",
    "loan_to_income",
]
CATEGORICAL_FEATURES = ["home_ownership", "purpose"]
EXPECTED_REPORT_FILES = {
    "replication_input_audit.csv",
    "model_replication_summary.csv",
    "parameter_stability_summary.csv",
    "parameter_stability_detail.csv",
    "model_replication_report.md",
}


def test_independent_replication_matches_reference_selection_auc_and_parameters(tmp_path) -> None:
    adapter = _write_reference_bundle(tmp_path)

    result = run_model_replication(adapter)

    assert result.replication_input_audit["status"].eq("pass").all()
    assert result.model_replication_summary["status"].eq("pass").all()
    assert result.model_replication_summary["selection_matches"].all()
    assert result.model_replication_summary["auc_absolute_delta"].max() <= 1e-10
    assert result.parameter_stability_summary["status"].eq("pass").all()
    assert result.parameter_stability_summary["max_absolute_delta"].max() <= 1e-10
    assert set(result.parameter_stability_detail["parameter_type"]) == {
        "standardized_coefficient",
        "impurity_importance",
    }


def test_replication_pipeline_writes_only_deterministic_aggregate_evidence(tmp_path) -> None:
    adapter = _write_reference_bundle(tmp_path / "inputs")
    output_a = tmp_path / "reports_a"
    output_b = tmp_path / "reports_b"

    result_a = run_model_replication_pipeline(adapter, output_a)
    result_b = run_model_replication_pipeline(adapter, output_b)

    assert set(result_a.report_paths) == EXPECTED_REPORT_FILES
    assert set(result_b.report_paths) == EXPECTED_REPORT_FILES
    assert {path.name for path in output_a.iterdir()} == EXPECTED_REPORT_FILES
    for filename in EXPECTED_REPORT_FILES:
        content_a = (output_a / filename).read_bytes()
        content_b = (output_b / filename).read_bytes()
        assert content_a == content_b
        assert b"\r\n" not in content_a
        assert b"C000001" not in content_a


def test_replication_detects_changed_development_feature_values(tmp_path) -> None:
    adapter = _write_reference_bundle(tmp_path)
    sample = pd.read_csv(adapter.sample_path)
    development = sample["sample_role"].eq("model_development")
    sample.loc[development, "credit_utilisation"] = (
        1.20 - sample.loc[development, "credit_utilisation"]
    )
    sample.to_csv(adapter.sample_path, index=False)

    result = run_model_replication(adapter)

    assert "fail" in set(result.parameter_stability_summary["status"])


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda frame: frame.assign(customer_id="duplicate"),
            "customer_id must be unique",
        ),
        (
            lambda frame: frame.assign(sample_role="model_development"),
            "sample_role must contain exactly",
        ),
        (
            lambda frame: frame.assign(loan_to_income=frame["loan_to_income"] + 0.01),
            "loan_to_income must match",
        ),
        (
            lambda frame: frame.assign(actual_default=0),
            "must contain both default classes",
        ),
    ],
)
def test_replication_rejects_invalid_development_contract(tmp_path, mutate, message) -> None:
    adapter = _write_reference_bundle(tmp_path)
    sample = pd.read_csv(adapter.sample_path)
    mutate(sample).to_csv(adapter.sample_path, index=False)

    with pytest.raises(ValueError, match=message):
        run_model_replication(adapter)


def _write_reference_bundle(directory: Path) -> Project1DevelopmentAdapter:
    directory.mkdir(parents=True, exist_ok=True)
    sample = _development_sample()
    specification = _specification()
    selection, parameters = _reference_evidence(sample)
    sample_path = directory / "model_development_sample.csv"
    specification_path = directory / "model_development_spec.json"
    selection_path = directory / "model_selection_audit.csv"
    parameter_path = directory / "model_parameter_reference.csv"
    sample.to_csv(sample_path, index=False)
    specification_path.write_text(
        json.dumps(specification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    selection.to_csv(selection_path, index=False)
    parameters.to_csv(parameter_path, index=False)
    return Project1DevelopmentAdapter(
        sample_path=sample_path,
        specification_path=specification_path,
        selection_audit_path=selection_path,
        parameter_reference_path=parameter_path,
    )


def _development_sample() -> pd.DataFrame:
    rows = []
    for index in range(240):
        development = index < 160
        role_index = index if development else index - 160
        month = (
            1 + role_index // 40
            if development
            else 7 + role_index // 20
        )
        observation_date = f"2020-{month:02d}-{1 + role_index % 20:02d}"
        annual_income = 38_000.0 + (index % 37) * 1_350.0
        loan_amount = 4_000.0 + (index % 29) * 420.0
        utilisation = 0.08 + (index % 17) * 0.052
        default = int(utilisation > 0.62 or index % 13 == 0)
        rows.append(
            {
                "customer_id": f"C{index + 1:06d}",
                "observation_date": observation_date,
                "sample_role": (
                    "model_development" if development else "calibration_holdout"
                ),
                "age": float(22 + index % 45),
                "annual_income": annual_income,
                "debt_to_income": 0.08 + (index % 21) * 0.018,
                "credit_utilisation": utilisation,
                "delinquencies_2y": float(index % 4),
                "loan_amount": loan_amount,
                "interest_rate": 0.06 + (index % 19) * 0.009,
                "employment_length": float(index % 11),
                "loan_to_income": loan_amount / annual_income,
                "home_ownership": "rent" if index % 3 else "mortgage",
                "purpose": "small_business" if index % 4 else "debt_consolidation",
                "actual_default": default,
            }
        )
    return pd.DataFrame(rows)


def _specification() -> dict[str, object]:
    return {
        "candidate_models": {
            "logistic_regression": {
                "estimator": "sklearn.linear_model.LogisticRegression",
                "parameters": {
                    "class_weight": "balanced",
                    "max_iter": 1000,
                    "random_state": 42,
                },
            },
            "random_forest": {
                "estimator": "sklearn.ensemble.RandomForestClassifier",
                "parameters": {
                    "class_weight": "balanced_subsample",
                    "min_samples_leaf": 40,
                    "n_estimators": 180,
                    "n_jobs": -1,
                    "random_state": 42,
                },
            },
        },
        "categorical_features": CATEGORICAL_FEATURES,
        "contract_version": "1.0",
        "date_column": "observation_date",
        "derived_features": {
            "loan_to_income": "loan_amount / max(annual_income, 1)",
        },
        "id_column": "customer_id",
        "numeric_features": NUMERIC_FEATURES,
        "preprocessing": {
            "categorical": ["most_frequent_imputation", "one_hot_ignore_unknown"],
            "numeric": ["median_imputation", "standard_scaling"],
        },
        "roles": ["model_development", "calibration_holdout"],
        "sample_role_column": "sample_role",
        "selection_metric": "roc_auc",
        "selection_tie_break": "model_name_ascending",
        "target_column": "actual_default",
    }


def _reference_evidence(sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]
    development = sample[sample["sample_role"].eq("model_development")]
    holdout = sample[sample["sample_role"].eq("calibration_holdout")]
    fitted = {}
    selection_rows = []
    for model_name, model in _reference_models().items():
        model.fit(development[features], development["actual_default"])
        auc = roc_auc_score(
            holdout["actual_default"],
            model.predict_proba(holdout[features])[:, 1],
        )
        fitted[model_name] = model
        selection_rows.append(
            {
                "model": model_name,
                "model_development_accounts": len(development),
                "calibration_holdout_accounts": len(holdout),
                "model_development_start": development["observation_date"].min(),
                "model_development_end": development["observation_date"].max(),
                "calibration_holdout_start": holdout["observation_date"].min(),
                "calibration_holdout_end": holdout["observation_date"].max(),
                "calibration_holdout_roc_auc": auc,
                "selected_model": False,
            }
        )
    selection = pd.DataFrame(selection_rows)
    selected = selection.sort_values(
        ["calibration_holdout_roc_auc", "model"],
        ascending=[False, True],
    ).iloc[0]["model"]
    selection.loc[selection["model"].eq(selected), "selected_model"] = True
    parameter_rows = []
    for model_name, model in fitted.items():
        feature_names = _clean_feature_names(
            model.named_steps["preprocessor"].get_feature_names_out()
        )
        classifier = model.named_steps["classifier"]
        if model_name == "logistic_regression":
            parameter_type = "standardized_coefficient"
            values = classifier.coef_[0]
        else:
            parameter_type = "impurity_importance"
            values = classifier.feature_importances_
        parameter_rows.extend(
            {
                "model": model_name,
                "feature_name": feature_name,
                "parameter_type": parameter_type,
                "reference_value": float(value),
            }
            for feature_name, value in zip(feature_names, values, strict=True)
        )
    return selection, pd.DataFrame(parameter_rows)


def _reference_models() -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            [
                ("preprocessor", _preprocessor()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocessor", _preprocessor()),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=180,
                        min_samples_leaf=40,
                        class_weight="balanced_subsample",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(strategy="median", keep_empty_features=True),
                        ),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUMERIC_FEATURES,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )


def _clean_feature_names(values: np.ndarray) -> list[str]:
    return [str(value).split("__", maxsplit=1)[-1] for value in values]
