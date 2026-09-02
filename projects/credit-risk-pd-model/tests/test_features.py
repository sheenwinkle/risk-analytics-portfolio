import numpy as np
import pandas as pd

from credit_risk_pd.features import build_preprocessor


def test_numeric_preprocessing_handles_all_missing_age():
    features = pd.DataFrame(
        {
            "age": [np.nan, np.nan],
            "annual_income": [80_000, 95_000],
            "debt_to_income": [0.25, 0.30],
            "credit_utilisation": [0.40, 0.35],
            "delinquencies_2y": [0, 1],
            "loan_amount": [12_000, 18_000],
            "interest_rate": [0.12, 0.15],
            "employment_length": [5, 8],
            "loan_to_income": [0.15, 0.19],
            "home_ownership": ["rent", "mortgage"],
            "purpose": ["debt_consolidation", "car"],
        }
    )

    transformed = build_preprocessor().fit_transform(features)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()

    assert transformed.shape[0] == 2
    assert not np.isnan(transformed).any()
