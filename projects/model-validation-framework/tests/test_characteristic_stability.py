import numpy as np
import pandas as pd
import pytest

from model_validation.characteristic_stability import (
    build_characteristic_stability_tables,
)


def _stability_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observation_date": pd.to_datetime(
                ["2022-01-01"] * 4 + ["2022-07-01"] * 4
            ),
            "annual_income": [10.0, 20.0, 30.0, np.nan, 20.0, 30.0, 100.0, np.nan],
            "all_missing": [np.nan] * 8,
            "purpose": ["a", "a", "b", "missing", "a", "c", "c", "missing"],
        }
    )


def test_characteristic_stability_uses_reference_bins_and_explicit_missing_buckets():
    summary, bins = build_characteristic_stability_tables(
        _stability_fixture(),
        numeric_features=("annual_income", "all_missing"),
        categorical_features=("purpose",),
        requested_bins=3,
    )

    assert summary["feature_name"].tolist() == [
        "annual_income",
        "all_missing",
        "purpose",
    ]
    assert summary["reference_start"].eq("2022-01-01").all()
    assert summary["current_start"].eq("2022-07-01").all()
    assert summary["reference_observations"].eq(4).all()
    assert summary["current_observations"].eq(4).all()

    for feature_name, feature_bins in bins.groupby("feature_name", sort=False):
        assert feature_bins["reference_observations"].sum() == 4, feature_name
        assert feature_bins["current_observations"].sum() == 4, feature_name
        assert feature_bins["reference_share"].sum() == pytest.approx(1.0)
        assert feature_bins["current_share"].sum() == pytest.approx(1.0)
        expected_csi = feature_bins["csi_component"].sum()
        actual_csi = summary.loc[
            summary["feature_name"].eq(feature_name),
            "characteristic_stability_index",
        ].item()
        assert actual_csi == pytest.approx(expected_csi)

    income_bins = bins[bins["feature_name"].eq("annual_income")]
    assert income_bins["bin"].tolist() == ["B01", "B02", "B03", "MISSING"]
    assert income_bins.loc[income_bins["bin"].eq("MISSING"), "reference_share"].item() == 0.25
    assert income_bins.loc[income_bins["bin"].eq("MISSING"), "current_share"].item() == 0.25
    assert income_bins.loc[income_bins["bin"].eq("B03"), "current_observations"].item() == 2

    purpose_bins = bins[bins["feature_name"].eq("purpose")].set_index("category_value")
    assert purpose_bins.loc["c", "reference_observations"] == 0
    assert purpose_bins.loc["c", "current_observations"] == 2
    assert purpose_bins.loc["c", "csi_component"] > 0
    assert summary.loc[
        summary["feature_name"].eq("purpose"), "stability_status"
    ].item() == "material_shift"

    all_missing = summary.loc[summary["feature_name"].eq("all_missing")].iloc[0]
    assert all_missing["availability_status"] == "all_missing"
    assert all_missing["stability_status"] == "not_available"


def test_reference_midpoints_do_not_split_tied_numeric_values():
    frame = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(
                ["2022-01-01"] * 6 + ["2022-07-01"] * 6
            ),
            "score_input": [1.0] * 3 + [2.0] * 3 + [1.0] * 3 + [2.0] * 3,
        }
    )

    summary, bins = build_characteristic_stability_tables(
        frame,
        numeric_features=("score_input",),
        categorical_features=(),
        requested_bins=10,
    )

    assert summary.loc[0, "effective_bins"] == 2
    assert summary.loc[0, "characteristic_stability_index"] == pytest.approx(0.0)
    assert bins["reference_observations"].tolist() == [3, 3]
    assert bins["current_observations"].tolist() == [3, 3]


@pytest.mark.parametrize("requested_bins", [0, -1])
def test_characteristic_stability_rejects_invalid_bin_count(requested_bins):
    with pytest.raises(ValueError, match="requested_bins"):
        build_characteristic_stability_tables(
            _stability_fixture(),
            numeric_features=("annual_income",),
            categorical_features=(),
            requested_bins=requested_bins,
        )
