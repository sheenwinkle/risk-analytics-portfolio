import numpy as np
import pandas as pd
import pytest

from credit_risk_pd.woe import calculate_woe_iv


def test_woe_remains_finite_for_zero_good_or_bad_bins():
    features = pd.DataFrame(
        {
            "age": [21, 22, 65, 66],
            "risk_segment": ["low", "low", "high", "high"],
        }
    )
    target = pd.Series([0, 0, 1, 1])

    bins, _ = calculate_woe_iv(
        features,
        target,
        numeric_features=["age"],
        categorical_features=["risk_segment"],
        numeric_bins=2,
        smoothing=0.5,
    )

    assert np.isfinite(bins["woe"]).all()
    assert np.isfinite(bins["iv"]).all()
    assert set(bins["feature_type"]) == {"numeric", "categorical"}
    low_risk_woe = bins.loc[
        (bins["feature"] == "risk_segment") & (bins["bin"] == "low"), "woe"
    ].iloc[0]
    high_risk_woe = bins.loc[
        (bins["feature"] == "risk_segment") & (bins["bin"] == "high"), "woe"
    ].iloc[0]
    assert low_risk_woe > 0
    assert high_risk_woe < 0


def test_information_value_aggregates_and_ranks_features():
    features = pd.DataFrame(
        {
            "risk_segment": ["low", "low", "high", "high"],
            "flat_segment": ["same", "same", "same", "same"],
        }
    )
    target = pd.Series([0, 0, 1, 1])

    bins, summary = calculate_woe_iv(
        features,
        target,
        numeric_features=[],
        categorical_features=["flat_segment", "risk_segment"],
        smoothing=0.5,
    )

    aggregated = bins.groupby("feature")["iv"].sum()
    assert summary.iloc[0]["feature"] == "risk_segment"
    assert summary.iloc[0]["rank"] == 1
    assert np.isclose(
        summary.loc[summary["feature"] == "risk_segment", "information_value"].iloc[0],
        aggregated["risk_segment"],
    )
    assert aggregated["risk_segment"] > aggregated["flat_segment"]


@pytest.mark.parametrize(
    ("target", "expected_message"),
    [
        (pd.Series([0, 1, None]), "no missing values"),
        (pd.Series([0, 0, 0]), "both 0 and 1 classes"),
    ],
)
def test_woe_rejects_invalid_targets(target, expected_message):
    features = pd.DataFrame({"age": [21, 35, 65]})

    with pytest.raises(ValueError, match=expected_message):
        calculate_woe_iv(features, target, numeric_features=["age"], categorical_features=[])


def test_woe_rejects_misaligned_rows_and_missing_features():
    features = pd.DataFrame({"age": [21, 35, 65]})

    with pytest.raises(ValueError, match="same number of rows"):
        calculate_woe_iv(
            features,
            pd.Series([0, 1]),
            numeric_features=["age"],
            categorical_features=[],
        )

    with pytest.raises(ValueError, match="missing required columns: income"):
        calculate_woe_iv(
            features,
            pd.Series([0, 1, 0]),
            numeric_features=["income"],
            categorical_features=[],
        )
