import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin

from credit_risk_pd.config import ModelConfig
from credit_risk_pd.data import (
    CANONICAL_COLUMNS,
    generate_synthetic_credit_data,
    make_out_of_time_split,
)
from credit_risk_pd.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, split_features_target
from credit_risk_pd.pipeline import run_pd_modelling_workflow


class FeatureScoreEstimator(ClassifierMixin, BaseEstimator):
    def __init__(self, invert: bool = False):
        self.invert = invert

    def fit(self, x, y):
        self.fit_rows_ = len(x)
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, x):
        values = x["annual_income"].astype(float).to_numpy()
        spread = values.max() - values.min()
        scores = np.full(len(values), 0.5) if spread == 0 else (values - values.min()) / spread
        if self.invert:
            scores = 1 - scores
        scores = 0.05 + 0.90 * scores
        return np.column_stack([1 - scores, scores])


def test_pipeline_creates_outputs(tmp_path):
    outputs = run_pd_modelling_workflow(
        output_dir=tmp_path / "reports",
        model_dir=tmp_path / "models",
    )

    assert "feature_importance" in outputs
    assert "woe_bins" in outputs
    assert "woe_summary" in outputs
    assert "recalibration_summary" in outputs
    assert "approval_strategy" in outputs
    assert "model_selection_audit" in outputs
    assert "model_development_sample" in outputs
    assert "model_development_spec" in outputs
    assert "model_parameter_reference" in outputs
    for path in outputs.values():
        assert path.exists()

    development_sample = pd.read_csv(outputs["model_development_sample"])
    assert development_sample.columns.tolist() == [
        "customer_id",
        "observation_date",
        "sample_role",
        *NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
        "actual_default",
    ]
    assert set(development_sample["sample_role"]) == {
        "model_development",
        "calibration_holdout",
    }
    role_dates = development_sample.groupby("sample_role")["observation_date"].agg(
        ["min", "max"]
    )
    assert (
        role_dates.loc["model_development", "max"]
        < role_dates.loc["calibration_holdout", "min"]
    )

    specification = json.loads(outputs["model_development_spec"].read_text(encoding="utf-8"))
    assert specification["contract_version"] == "1.0"
    assert specification["numeric_features"] == NUMERIC_FEATURES
    assert specification["categorical_features"] == CATEGORICAL_FEATURES
    assert set(specification["candidate_models"]) == {
        "logistic_regression",
        "random_forest",
    }

    parameter_reference = pd.read_csv(outputs["model_parameter_reference"])
    assert set(parameter_reference["model"]) == {
        "logistic_regression",
        "random_forest",
    }
    assert set(parameter_reference["parameter_type"]) == {
        "standardized_coefficient",
        "impurity_importance",
    }
    assert not parameter_reference.duplicated(["model", "feature_name"]).any()

    predictions = pd.read_csv(outputs["predictions"])
    assert {
        "selected_model_raw_pd",
        "recalibrated_pd",
        *NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
    }.issubset(predictions.columns)
    assert predictions["recalibrated_pd"].between(0, 1).all()
    assert predictions[["home_ownership", "purpose"]].notna().all().all()
    expected_loan_to_income = predictions["loan_amount"] / predictions[
        "annual_income"
    ].clip(lower=1)
    np.testing.assert_allclose(
        predictions["loan_to_income"],
        expected_loan_to_income,
        equal_nan=True,
    )

    recalibration = pd.read_csv(outputs["recalibration_summary"])
    assert {
        "score_type",
        "evaluation_sample",
        "recalibration_fit_sample",
        "recalibration_fit_intercept",
        "recalibration_fit_slope",
        "calibration_intercept",
        "calibration_slope",
    }.issubset(recalibration.columns)
    assert set(recalibration["score_type"]) == {"raw", "recalibrated"}
    assert set(recalibration["evaluation_sample"]) == {"out_of_time"}

    strategy = pd.read_csv(outputs["approval_strategy"])
    assert {"max_pd_cutoff", "lgd", "approval_rate", "expected_loss"}.issubset(
        strategy.columns
    )

    metrics = pd.read_csv(outputs["metrics"])
    assert metrics["classification_threshold"].eq(ModelConfig().test_threshold).all()

    loaded_model = joblib.load(outputs["model"])
    assert loaded_model.base_estimator is not None
    assert loaded_model.recalibrator.slope_ > 0
    assert loaded_model.classes_.tolist() == [0, 1]
    source_data = generate_synthetic_credit_data(random_state=ModelConfig().random_state)
    _, oot = make_out_of_time_split(
        source_data,
        cutoff_date=ModelConfig().oot_cutoff_date,
    )
    x_oot, y_oot = split_features_target(oot, ModelConfig())
    probabilities = loaded_model.predict_proba(x_oot)[:, 1]
    assert len(probabilities) == len(y_oot)
    np.testing.assert_allclose(
        probabilities,
        predictions["recalibrated_pd"].to_numpy(),
        rtol=1e-12,
        atol=1e-12,
    )

    woe_bins = pd.read_csv(outputs["woe_bins"])
    woe_summary = pd.read_csv(outputs["woe_summary"])
    assert {"feature", "bin", "goods", "bads", "woe", "iv"}.issubset(woe_bins.columns)
    assert {"rank", "feature", "information_value", "iv_band"}.issubset(woe_summary.columns)
    assert woe_summary["information_value"].is_monotonic_decreasing


def test_pipeline_selects_model_on_calibration_holdout_not_oot(monkeypatch, tmp_path):
    data = _temporal_selection_fixture()
    input_path = tmp_path / "credit_data.csv"
    data.to_csv(input_path, index=False)

    def fake_candidate_models(config):
        return {
            "calibration_winner": FeatureScoreEstimator(invert=False),
            "oot_winner_if_leaky": FeatureScoreEstimator(invert=True),
        }

    monkeypatch.setattr("credit_risk_pd.pipeline.candidate_models", fake_candidate_models)

    outputs = run_pd_modelling_workflow(
        input_path=input_path,
        output_dir=tmp_path / "reports",
        model_dir=tmp_path / "models",
        config=ModelConfig(oot_cutoff_date="2021-01-01", calibration_fraction=0.25),
    )

    selection = pd.read_csv(outputs["model_selection_audit"])
    assert set(selection["model"]) == {"calibration_winner", "oot_winner_if_leaky"}
    assert selection.loc[selection["selected_model"], "model"].tolist() == ["calibration_winner"]
    assert "oot_roc_auc" not in selection.columns
    assert selection["model_development_end"].max() < selection["calibration_holdout_start"].min()
    assert selection["calibration_holdout_end"].max() < "2021-01-01"

    metrics = pd.read_csv(outputs["metrics"])
    raw_metrics = metrics.loc[metrics["score_type"].eq("raw")].set_index("model")
    assert (
        raw_metrics.loc["oot_winner_if_leaky", "roc_auc"]
        > raw_metrics.loc["calibration_winner", "roc_auc"]
    )


def test_pipeline_rejects_single_class_calibration_holdout(tmp_path):
    data = _single_class_holdout_fixture()
    input_path = tmp_path / "credit_data.csv"
    data.to_csv(input_path, index=False)

    with pytest.raises(
        ValueError,
        match="Calibration holdout sample must contain both default and non-default",
    ):
        run_pd_modelling_workflow(
            input_path=input_path,
            output_dir=tmp_path / "reports",
            model_dir=tmp_path / "models",
            config=ModelConfig(oot_cutoff_date="2021-01-01", calibration_fraction=0.50),
        )


def _temporal_selection_fixture() -> pd.DataFrame:
    rows = []
    for index in range(100):
        if index < 60:
            date = "2020-01-01"
            default = 1 if index % 5 == 0 else 0
        elif index < 80:
            date = "2020-07-01"
            default = 1 if index % 20 >= 10 else 0
        else:
            date = "2021-01-01"
            default = 1 if index % 20 < 10 else 0

        rows.append(_canonical_row(index, date, default))
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


def _single_class_holdout_fixture() -> pd.DataFrame:
    rows = []
    for index in range(120):
        if index < 40:
            date = "2019-01-01"
            default = index % 2
        elif index < 80:
            date = "2020-01-01"
            default = 0
        else:
            date = "2021-01-01"
            default = index % 2
        rows.append(_canonical_row(index, date, default))
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


def _canonical_row(index: int, date: str, default: int) -> dict[str, object]:
    return {
        "customer_id": f"T{index:06d}",
        "observation_date": date,
        "age": 35,
        "annual_income": 40_000 + (index % 20) * 1_000,
        "debt_to_income": 0.20,
        "credit_utilisation": 0.35,
        "delinquencies_2y": 0,
        "loan_amount": 10_000 + (index % 10) * 500,
        "interest_rate": 0.12,
        "employment_length": 5,
        "home_ownership": "rent" if index % 2 else "mortgage",
        "purpose": "debt_consolidation",
        "default": default,
    }
