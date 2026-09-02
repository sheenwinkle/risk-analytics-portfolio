import pandas as pd

from credit_risk_pd.monitoring import population_stability_index, psi_report


def test_population_stability_index_near_zero_for_same_distribution():
    series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    assert population_stability_index(series, series) < 0.001


def test_psi_report_labels_material_shift():
    expected = pd.DataFrame({"score": list(range(100))})
    actual = pd.DataFrame({"score": list(range(100, 200))})

    report = psi_report(expected, actual, ["score"])

    assert report.loc[0, "status"] == "material_shift"


def test_psi_report_marks_all_missing_feature_not_available():
    expected = pd.DataFrame({"age": [None, None]})
    actual = pd.DataFrame({"age": [None, None]})

    report = psi_report(expected, actual, ["age"])

    assert pd.isna(report.loc[0, "psi"])
    assert report.loc[0, "status"] == "not_available"

