from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from credit_risk_pd.config import DEFAULT_CONFIG, ModelConfig


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


def add_credit_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add derived features that are common in credit affordability analysis."""
    featured = data.copy()
    income = featured["annual_income"].clip(lower=1)
    featured["loan_to_income"] = featured["loan_amount"] / income
    return featured


def split_features_target(
    data: pd.DataFrame,
    config: ModelConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, pd.Series]:
    """Return model features and binary default target."""
    featured = add_credit_features(data)
    selected = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    return featured[selected], featured[config.target_col].astype(int)


def build_preprocessor() -> ColumnTransformer:
    """Build preprocessing for numeric and categorical credit risk variables."""
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ]
    )

