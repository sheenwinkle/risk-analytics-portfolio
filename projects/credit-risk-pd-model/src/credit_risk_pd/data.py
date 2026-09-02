from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk_pd.config import DEFAULT_CONFIG, ModelConfig

CANONICAL_COLUMNS = [
    "customer_id",
    "observation_date",
    "age",
    "annual_income",
    "debt_to_income",
    "credit_utilisation",
    "delinquencies_2y",
    "loan_amount",
    "interest_rate",
    "employment_length",
    "home_ownership",
    "purpose",
    "default",
]

REQUIRED_COLUMNS = set(CANONICAL_COLUMNS)


def generate_synthetic_credit_data(n_rows: int = 5_000, random_state: int = 42) -> pd.DataFrame:
    """Generate realistic-enough credit data for local development and portfolio demos."""
    rng = np.random.default_rng(random_state)

    dates = pd.date_range("2018-01-01", "2022-12-01", freq="MS")
    observation_date = rng.choice(dates, size=n_rows)
    age = np.clip(rng.normal(38, 11, n_rows).round(), 21, 72).astype(int)
    annual_income = np.clip(rng.lognormal(mean=10.95, sigma=0.45, size=n_rows), 28_000, 220_000)
    loan_amount = np.clip(rng.lognormal(mean=9.75, sigma=0.55, size=n_rows), 2_000, 85_000)
    debt_to_income = np.clip(rng.beta(2.4, 5.2, n_rows) * 0.95, 0.02, 0.95)
    credit_utilisation = np.clip(rng.beta(2.1, 2.8, n_rows), 0.01, 0.99)
    delinquencies_2y = rng.poisson(lam=np.clip(credit_utilisation * 1.2, 0.05, 2.5))
    employment_length = np.clip(rng.normal(6.5, 4.0, n_rows).round(), 0, 30).astype(int)
    home_ownership = rng.choice(
        ["rent", "mortgage", "own", "other"],
        size=n_rows,
        p=[0.43, 0.39, 0.15, 0.03],
    )
    purpose = rng.choice(
        ["debt_consolidation", "car", "home_improvement", "small_business", "medical", "other"],
        size=n_rows,
        p=[0.47, 0.15, 0.13, 0.08, 0.06, 0.11],
    )

    macro_stress = (pd.Series(observation_date).dt.year.to_numpy() >= 2022).astype(float)
    rent_flag = (home_ownership == "rent").astype(float)
    small_business_flag = (purpose == "small_business").astype(float)

    logit_pd = (
        -4.0
        + 2.5 * debt_to_income
        + 1.8 * credit_utilisation
        + 0.32 * delinquencies_2y
        + 0.55 * rent_flag
        + 0.65 * small_business_flag
        + 0.75 * macro_stress
        + 0.000012 * loan_amount
        - 0.000008 * annual_income
        - 0.035 * employment_length
    )
    pd_score = 1 / (1 + np.exp(-logit_pd))
    default = rng.binomial(1, pd_score)

    return pd.DataFrame(
        {
            "customer_id": [f"C{i:06d}" for i in range(1, n_rows + 1)],
            "observation_date": pd.to_datetime(observation_date),
            "age": age,
            "annual_income": annual_income.round(2),
            "debt_to_income": debt_to_income.round(4),
            "credit_utilisation": credit_utilisation.round(4),
            "delinquencies_2y": delinquencies_2y.astype(int),
            "loan_amount": loan_amount.round(2),
            "interest_rate": np.clip(
                0.045 + pd_score * 0.23 + rng.normal(0, 0.018, n_rows),
                0.035,
                0.42,
            ).round(4),
            "employment_length": employment_length,
            "home_ownership": home_ownership,
            "purpose": purpose,
            "default": default.astype(int),
        }
    )


def load_credit_data(path: str | Path, config: ModelConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    """Load a CSV file and validate the columns required by the modelling pipeline."""
    path = Path(path)
    data = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Input data is missing required columns: {missing}")
    return _validated_dated_copy(data, config.date_col)


def make_out_of_time_split(
    data: pd.DataFrame,
    cutoff_date: str,
    date_col: str = DEFAULT_CONFIG.date_col,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split observations into development and out-of-time samples."""
    try:
        cutoff = pd.Timestamp(cutoff_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("cutoff_date must be a valid date.") from exc
    if pd.isna(cutoff):
        raise ValueError("cutoff_date must be a valid date.")
    dated = _validated_dated_copy(data, date_col)

    train = dated.loc[dated[date_col] < cutoff].reset_index(drop=True)
    oot = dated.loc[dated[date_col] >= cutoff].reset_index(drop=True)

    if train.empty or oot.empty:
        raise ValueError("Out-of-time split produced an empty train or test sample.")
    return train, oot


def make_temporal_calibration_split(
    development: pd.DataFrame,
    calibration_fraction: float,
    date_col: str = DEFAULT_CONFIG.date_col,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split pre-OOT data into earlier model-development and later calibration samples."""
    try:
        fraction = float(calibration_fraction)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "calibration_fraction must be greater than 0 and less than 1."
        ) from exc
    if not np.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError("calibration_fraction must be greater than 0 and less than 1.")

    dated = _validated_dated_copy(development, date_col)
    dated = dated.sort_values(date_col, kind="mergesort").reset_index(drop=True)
    date_counts = dated.groupby(date_col, sort=True).size()
    if len(date_counts) < 2:
        raise ValueError("Calibration split requires at least two distinct development dates.")

    target_development_rows = len(dated) * (1 - fraction)
    cumulative_rows = date_counts.cumsum()
    eligible_boundaries = cumulative_rows.iloc[:-1].to_numpy()
    split_position = int(np.argmin(np.abs(eligible_boundaries - target_development_rows)))
    split_date = date_counts.index[split_position]

    model_development = dated.loc[dated[date_col] <= split_date].reset_index(drop=True)
    calibration_holdout = dated.loc[dated[date_col] > split_date].reset_index(drop=True)
    if model_development.empty or calibration_holdout.empty:
        raise ValueError("Calibration split produced an empty model-development or holdout sample.")
    if model_development[date_col].max() >= calibration_holdout[date_col].min():
        raise ValueError(
            "Calibration split must keep the holdout after the model-development sample."
        )
    return model_development, calibration_holdout


def _validated_dated_copy(data: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if date_col not in data.columns:
        raise ValueError(f"Input data is missing date column: {date_col}")
    if data.empty:
        raise ValueError("Input data must contain at least one row.")

    dated = data.copy()
    try:
        dated[date_col] = pd.to_datetime(dated[date_col], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{date_col} must contain valid dates.") from exc
    if dated[date_col].isna().any():
        raise ValueError(f"{date_col} must not contain missing dates.")
    return dated

