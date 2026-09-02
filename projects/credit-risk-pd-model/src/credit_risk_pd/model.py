from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from credit_risk_pd.config import DEFAULT_CONFIG, ModelConfig
from credit_risk_pd.features import build_preprocessor


def build_logistic_pd_model(config: ModelConfig = DEFAULT_CONFIG) -> Pipeline:
    """Build an interpretable baseline PD model."""
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1_000,
                    class_weight="balanced",
                    random_state=config.random_state,
                ),
            ),
        ]
    )


def build_random_forest_pd_model(config: ModelConfig = DEFAULT_CONFIG) -> Pipeline:
    """Build a non-linear challenger model for benchmark comparison."""
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=180,
                    min_samples_leaf=40,
                    class_weight="balanced_subsample",
                    random_state=config.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def candidate_models(config: ModelConfig = DEFAULT_CONFIG) -> dict[str, Pipeline]:
    """Return baseline and challenger models."""
    return {
        "logistic_regression": build_logistic_pd_model(config),
        "random_forest": build_random_forest_pd_model(config),
    }

