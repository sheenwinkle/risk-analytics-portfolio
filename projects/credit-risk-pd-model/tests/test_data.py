import numpy as np
import pandas as pd
import pytest

from credit_risk_pd.data import (
    generate_synthetic_credit_data,
    make_out_of_time_split,
    make_temporal_calibration_split,
)


def test_generate_synthetic_credit_data_has_expected_columns():
    data = generate_synthetic_credit_data(n_rows=100, random_state=7)

    assert len(data) == 100
    assert "default" in data.columns
    assert set(data["default"].unique()).issubset({0, 1})


def test_make_out_of_time_split_uses_cutoff_date():
    data = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(["2021-12-01", "2022-01-01"]),
            "default": [0, 1],
        }
    )

    train, oot = make_out_of_time_split(data, cutoff_date="2022-01-01")

    assert train["observation_date"].max() < pd.Timestamp("2022-01-01")
    assert oot["observation_date"].min() >= pd.Timestamp("2022-01-01")


def test_temporal_calibration_split_keeps_date_vintages_intact():
    development = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(
                ["2019-01-01"] * 4 + ["2020-01-01"] * 3 + ["2020-07-01"] * 3
            ),
            "default": [0, 1] * 5,
        }
    )

    model_development, calibration_holdout = make_temporal_calibration_split(
        development,
        calibration_fraction=0.30,
    )

    assert len(model_development) + len(calibration_holdout) == len(development)
    assert model_development["observation_date"].max() < calibration_holdout[
        "observation_date"
    ].min()
    assert set(model_development["observation_date"]).isdisjoint(
        set(calibration_holdout["observation_date"])
    )


@pytest.mark.parametrize("fraction", [0.0, 1.0, np.nan])
def test_temporal_calibration_split_rejects_invalid_fraction(fraction):
    development = pd.DataFrame(
        {
            "observation_date": ["2019-01-01", "2020-01-01"],
            "default": [0, 1],
        }
    )

    with pytest.raises(ValueError, match="calibration_fraction"):
        make_temporal_calibration_split(development, calibration_fraction=fraction)


def test_time_splits_reject_missing_dates():
    data = pd.DataFrame(
        {
            "observation_date": ["2019-01-01", None, "2022-01-01"],
            "default": [0, 0, 1],
        }
    )

    with pytest.raises(ValueError, match="must not contain missing dates"):
        make_out_of_time_split(data, cutoff_date="2022-01-01")

