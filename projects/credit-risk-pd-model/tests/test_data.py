import pandas as pd

from credit_risk_pd.data import generate_synthetic_credit_data, make_out_of_time_split


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

