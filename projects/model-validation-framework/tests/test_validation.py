from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from model_validation import (
    Project1OOTPredictionAdapter,
    ValidationPolicy,
    run_validation,
    run_validation_pipeline,
)

EXPECTED_REPORT_FILES = {
    "input_audit.csv",
    "model_metrics.csv",
    "calibration_by_decile.csv",
    "monthly_performance.csv",
    "metric_uncertainty.csv",
    "vintage_performance.csv",
    "segment_performance.csv",
    "stability_summary.csv",
    "stability_bins.csv",
    "benchmark_comparison.csv",
    "validation_summary.csv",
    "validation_findings.csv",
    "model_limitations.csv",
    "validation_report.md",
}


def _valid_predictions() -> pd.DataFrame:
    rows = []
    raw_scores = [0.10, 0.10, 0.40, 0.80, 0.80, 0.20, 0.30, 0.60, 0.70, 0.90, 0.50, 0.95]
    recalibrated = [0.04, 0.04, 0.08, 0.30, 0.30, 0.05, 0.07, 0.18, 0.24, 0.42, 0.13, 0.52]
    challenger = [0.30, 0.30, 0.35, 0.65, 0.65, 0.28, 0.33, 0.55, 0.60, 0.72, 0.45, 0.76]
    actual = [0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1]
    for index, (raw, rec, rf, default) in enumerate(
        zip(raw_scores, recalibrated, challenger, actual, strict=True),
        start=1,
    ):
        rows.append(
            {
                "customer_id": f"C{index:03d}",
                "observation_date": f"2022-{index:02d}-01",
                "home_ownership": "rent" if index % 2 else "mortgage",
                "purpose": "small_business" if index % 3 == 0 else "debt_consolidation",
                "actual_default": default,
                "logistic_regression_pd": raw,
                "selected_model": "logistic_regression",
                "selected_model_raw_pd": raw,
                "recalibrated_pd": rec,
                "random_forest_pd": rf,
            }
        )
    return pd.DataFrame(rows)


def _write_predictions(path: Path, frame: pd.DataFrame | None = None) -> None:
    (frame if frame is not None else _valid_predictions()).to_csv(path, index=False)


def test_run_validation_returns_input_audit_and_metrics_for_project1_predictions(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))

    assert result.input_audit["check"].tolist() == [
        "row_count",
        "required_columns",
        "customer_id",
        "observation_date",
        "home_ownership",
        "purpose",
        "actual_default",
        "selected_model",
        "selected_model_raw_pd",
        "logistic_regression_pd",
        "recalibrated_pd",
        "random_forest_pd",
    ]
    assert result.input_audit["status"].eq("pass").all()

    metrics = result.model_metrics.sort_values(["model_name", "score_version"]).reset_index(
        drop=True
    )
    assert metrics[["model_name", "score_version", "score_column"]].to_dict("records") == [
        {
            "model_name": "logistic_regression",
            "score_version": "raw",
            "score_column": "logistic_regression_pd",
        },
        {
            "model_name": "logistic_regression",
            "score_version": "recalibrated",
            "score_column": "recalibrated_pd",
        },
        {
            "model_name": "random_forest",
            "score_version": "raw",
            "score_column": "random_forest_pd",
        },
    ]
    assert metrics["observations"].tolist() == [12, 12, 12]
    assert metrics["defaults"].tolist() == [5, 5, 5]
    assert metrics["roc_auc"].between(0, 1).all()
    assert metrics["ks"].between(0, 1).all()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda frame: frame.iloc[0:0],
            "must contain at least one row",
        ),
        (
            lambda frame: frame.drop(columns=["selected_model"]),
            "missing required columns: selected_model",
        ),
        (
            lambda frame: frame.drop(columns=["selected_model_raw_pd"]),
            "missing required columns: selected_model_raw_pd",
        ),
        (
            lambda frame: frame.drop(columns=["home_ownership"]),
            "missing required columns: home_ownership",
        ),
        (
            lambda frame: frame.assign(purpose=""),
            "purpose must contain non-empty category values",
        ),
        (
            lambda frame: frame.assign(selected_model=["xgboost"] * len(frame)),
            "selected_model must contain exactly one supported model",
        ),
        (
            lambda frame: frame.assign(
                selected_model=["logistic_regression", "random_forest"] * 6,
            ),
            "selected_model must contain exactly one supported model",
        ),
        (
            lambda frame: frame.assign(selected_model_raw_pd=frame["logistic_regression_pd"] + 0.001),
            "selected_model_raw_pd must match logistic_regression_pd",
        ),
        (
            lambda frame: frame.assign(actual_default=0),
            "actual_default must contain both default classes",
        ),
        (
            lambda frame: frame.assign(observation_date="2022-06-01"),
            "observation_date must contain at least two distinct dates",
        ),
    ],
)
def test_adapter_rejects_invalid_selected_model_lineage(tmp_path, mutate, message) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path, mutate(_valid_predictions()))

    with pytest.raises(ValueError, match=message):
        run_validation(Project1OOTPredictionAdapter(prediction_path))


def test_adapter_rejects_missing_project1_report_file(tmp_path) -> None:
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError, match="Project 1 OOT prediction file not found"):
        run_validation(Project1OOTPredictionAdapter(missing_path))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda frame: frame.assign(customer_id=["C001"] * len(frame)),
            "customer_id must be unique",
        ),
        (
            lambda frame: frame.assign(customer_id=[""] * len(frame)),
            "customer_id must contain non-empty string values",
        ),
        (
            lambda frame: frame.assign(observation_date=["bad"] * len(frame)),
            "observation_date must contain parseable dates",
        ),
        (
            lambda frame: frame.assign(actual_default=[0, 1, 0, 2] * 3),
            "actual_default must contain only binary 0/1 values",
        ),
        (
            lambda frame: frame.assign(logistic_regression_pd=[float("inf")] * len(frame)),
            "logistic_regression_pd must contain finite numeric values",
        ),
        (
            lambda frame: frame.assign(recalibrated_pd=1.20),
            "recalibrated_pd must contain PD values between 0 and 1",
        ),
        (
            lambda frame: frame.assign(random_forest_pd=-0.10),
            "random_forest_pd must contain PD values between 0 and 1",
        ),
    ],
)
def test_run_validation_rejects_invalid_project1_prediction_inputs(
    tmp_path,
    mutate,
    message,
) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path, mutate(_valid_predictions()))

    with pytest.raises(ValueError, match=message):
        run_validation(Project1OOTPredictionAdapter(prediction_path))


def test_run_validation_uses_tie_safe_auc_ks_and_rank_deciles(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))
    by_score = result.model_metrics.set_index("score_column")

    assert by_score.loc["logistic_regression_pd", "roc_auc"] == pytest.approx(1.0)
    assert by_score.loc["logistic_regression_pd", "ks"] == pytest.approx(1.0)
    assert result.calibration_by_decile["decile"].tolist() == list(range(1, 11))
    assert result.calibration_by_decile["mean_pd"].is_monotonic_increasing
    assert result.calibration_by_decile.columns.tolist() == [
        "model_name",
        "score_version",
        "decile",
        "observations",
        "defaults",
        "expected_defaults",
        "mean_pd",
        "observed_default_rate",
        "calibration_gap",
        "expected_to_observed_ratio",
    ]


def test_stability_uses_chronological_halves_and_reference_bins(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))
    stability = result.stability_summary.iloc[0]

    assert stability["reference_start"] == "2022-01-01"
    assert stability["reference_end"] == "2022-06-01"
    assert stability["current_start"] == "2022-07-01"
    assert stability["current_end"] == "2022-12-01"
    assert stability["reference_observations"] == 6
    assert stability["current_observations"] == 6
    assert result.stability_bins["bin"].tolist() == list(range(1, len(result.stability_bins) + 1))
    assert result.stability_bins["reference_observations"].sum() == 6
    assert result.stability_bins["current_observations"].sum() == 6


def test_policy_status_and_findings_are_driven_by_warning_or_fail_checks(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)
    strict_policy = ValidationPolicy(
        auc_green_min=1.01,
        auc_warning_min=1.00,
        ks_green_min=1.01,
        ks_warning_min=1.00,
        absolute_calibration_gap_green_max=0.0,
        absolute_calibration_gap_warning_max=0.001,
        psi_green_max=0.0,
        psi_warning_max=0.001,
        challenger_auc_margin_green_max=-0.01,
        challenger_auc_margin_warning_max=0.0,
    )

    result = run_validation(Project1OOTPredictionAdapter(prediction_path), policy=strict_policy)

    summary = result.validation_summary.set_index("check")
    assert set(summary.index) == {
        "auc",
        "ks",
        "absolute_calibration_gap",
        "population_stability_index",
        "challenger_auc_margin",
    }
    assert set(summary["status"]).issubset({"pass", "warning", "fail"})
    assert not result.validation_findings.empty
    assert set(result.validation_findings["status"]).issubset({"warning", "fail"})


def test_benchmarking_compares_challenger_and_recalibration_impact(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))
    comparison = result.benchmark_comparison.set_index("comparison")

    assert set(comparison.index) == {
        "selected_recalibrated_vs_unselected_raw_challenger",
        "selected_raw_vs_selected_recalibrated",
    }
    assert (
        comparison.loc[
            "selected_recalibrated_vs_unselected_raw_challenger",
            "benchmark_model",
        ]
        == "random_forest"
    )
    assert (
        comparison.loc[
            "selected_raw_vs_selected_recalibrated",
            "baseline_score_version",
        ]
        == "raw"
    )


def test_selected_random_forest_lineage_labels_recalibrated_metrics_and_challenger(
    tmp_path,
) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    predictions = _valid_predictions().assign(
        selected_model="random_forest",
        selected_model_raw_pd=lambda frame: frame["random_forest_pd"],
    )
    _write_predictions(prediction_path, predictions)

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))
    recalibrated = result.model_metrics.loc[
        result.model_metrics["score_version"].eq("recalibrated")
    ].iloc[0]
    challenger = result.benchmark_comparison.loc[
        result.benchmark_comparison["comparison"].eq(
            "selected_recalibrated_vs_unselected_raw_challenger"
        )
    ].iloc[0]

    assert recalibrated["model_name"] == "random_forest"
    assert challenger["baseline_model"] == "random_forest"
    assert challenger["benchmark_model"] == "logistic_regression"


def test_selected_model_names_are_normalized_before_lineage_lookup(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(
        prediction_path,
        _valid_predictions().assign(selected_model="  logistic_regression  "),
    )

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))

    assert result.model_metrics.loc[
        result.model_metrics["score_version"].eq("recalibrated"),
        "model_name",
    ].iloc[0] == "logistic_regression"
    assert "logistic_regression" in result.input_audit.loc[
        result.input_audit["check"].eq("selected_model"),
        "detail",
    ].iloc[0]


def test_calibration_deciles_are_stable_when_input_rows_are_reordered(tmp_path) -> None:
    rows = []
    for index in range(1, 21):
        rows.append(
            {
                "customer_id": f"C{index:03d}",
                "observation_date": "2022-01-01" if index <= 10 else "2022-07-01",
                "home_ownership": "rent" if index % 2 else "mortgage",
                "purpose": "small_business" if index % 3 == 0 else "debt_consolidation",
                "actual_default": 0 if index <= 10 else 1,
                "logistic_regression_pd": 0.50,
                "selected_model": "logistic_regression",
                "selected_model_raw_pd": 0.50,
                "recalibrated_pd": 0.50,
                "random_forest_pd": 0.50,
            }
        )
    predictions = pd.DataFrame(rows)
    forward_path = tmp_path / "forward.csv"
    reverse_path = tmp_path / "reverse.csv"
    _write_predictions(forward_path, predictions)
    _write_predictions(reverse_path, predictions.iloc[::-1])

    forward = run_validation(Project1OOTPredictionAdapter(forward_path)).calibration_by_decile
    reverse = run_validation(Project1OOTPredictionAdapter(reverse_path)).calibration_by_decile

    pd.testing.assert_frame_equal(forward, reverse)


def test_psi_is_zero_for_identical_tied_reference_and_current_distributions(tmp_path) -> None:
    rows = []
    scores = [0.10, 0.10, 0.90, 0.90] * 2
    dates = ["2022-01-01", "2022-01-01", "2022-02-01", "2022-02-01"] + [
        "2022-07-01",
        "2022-07-01",
        "2022-08-01",
        "2022-08-01",
    ]
    for index, (score, date) in enumerate(zip(scores, dates, strict=True), start=1):
        rows.append(
            {
                "customer_id": f"C{index:03d}",
                "observation_date": date,
                "home_ownership": "rent" if index % 2 else "mortgage",
                "purpose": "small_business" if index % 3 == 0 else "debt_consolidation",
                "actual_default": int(score > 0.50),
                "logistic_regression_pd": score,
                "selected_model": "logistic_regression",
                "selected_model_raw_pd": score,
                "recalibrated_pd": score,
                "random_forest_pd": score,
            }
        )
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path, pd.DataFrame(rows))

    result = run_validation(Project1OOTPredictionAdapter(prediction_path))

    assert result.stability_summary["population_stability_index"].iloc[0] == pytest.approx(0.0)
    assert result.stability_summary["effective_bins"].iloc[0] == 2
    assert result.stability_bins["lower_pd_bound"].iloc[0] == 0.0
    assert result.stability_bins["upper_pd_bound"].iloc[-1] == 1.0


def test_monthly_discrimination_is_not_available_for_single_class_periods(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)

    monthly = run_validation(Project1OOTPredictionAdapter(prediction_path)).monthly_performance

    assert monthly["roc_auc"].isna().all()
    assert monthly["ks"].isna().all()
    assert monthly["discrimination_status"].eq("not_available_single_class").all()


@pytest.mark.parametrize(
    "policy_kwargs",
    [
        {"auc_green_min": 0.50, "auc_warning_min": 0.60},
        {"psi_green_max": 0.20, "psi_warning_max": 0.10},
        {"ks_green_min": np.nan},
    ],
)
def test_validation_policy_rejects_incoherent_or_non_finite_thresholds(policy_kwargs) -> None:
    with pytest.raises(ValueError, match="ValidationPolicy thresholds"):
        ValidationPolicy(**policy_kwargs)


def test_run_validation_result_exposes_static_limitations(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    _write_predictions(prediction_path)

    limitations = run_validation(Project1OOTPredictionAdapter(prediction_path)).model_limitations

    assert limitations["limitation"].tolist() == [
        "synthetic_data",
        "terminal_outcome_proxy",
        "limited_oot_horizon",
        "limited_feature_replication",
    ]
    assert limitations["severity"].tolist() == ["medium", "medium", "medium", "medium"]


def test_run_validation_pipeline_writes_exact_deterministic_outputs_with_lf_endings(tmp_path) -> None:
    prediction_path = tmp_path / "oot_predictions.csv"
    output_a = tmp_path / "reports_a"
    output_b = tmp_path / "reports_b"
    _write_predictions(prediction_path)

    result_a = run_validation_pipeline(Project1OOTPredictionAdapter(prediction_path), output_a)
    result_b = run_validation_pipeline(Project1OOTPredictionAdapter(prediction_path), output_b)

    assert {path.name for path in output_a.iterdir()} == EXPECTED_REPORT_FILES
    assert set(result_a.report_paths) == EXPECTED_REPORT_FILES
    assert set(result_b.report_paths) == EXPECTED_REPORT_FILES

    for filename in EXPECTED_REPORT_FILES:
        bytes_a = (output_a / filename).read_bytes()
        bytes_b = (output_b / filename).read_bytes()
        assert bytes_a == bytes_b
        assert b"\r\n" not in bytes_a
        assert b"\n" in bytes_a

    markdown = (output_a / "validation_report.md").read_text(encoding="utf-8")
    assert "Educational portfolio case study" in markdown
    assert "Overall policy outcome:" in markdown
    assert "## Calibration by Decile" in markdown
    assert "## Stability Summary" in markdown
    assert "Absolute calibration gap reached fail status" in markdown
    assert "Mean predicted PD:" in markdown
    assert "| nan |" not in markdown.lower()


def test_run_validation_pipeline_is_compatible_with_actual_project1_candidate_report(tmp_path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    prediction_path = project_dir.parent / "credit-risk-pd-model" / "reports" / "oot_predictions.csv"
    if not prediction_path.is_file():
        pytest.skip("Project 1 candidate report is not available in this checkout")

    result = run_validation_pipeline(
        Project1OOTPredictionAdapter(prediction_path),
        tmp_path / "reports",
    )

    assert result.input_audit["status"].eq("pass").all()
    assert result.calibration_by_decile["observations"].sum() == result.model_metrics.loc[
        result.model_metrics["score_column"].eq("recalibrated_pd"),
        "observations",
    ].iloc[0]
    assert {path.name for path in (tmp_path / "reports").iterdir()} == EXPECTED_REPORT_FILES


def test_adapter_preserves_numeric_looking_customer_ids_as_strings(tmp_path) -> None:
    prediction_path = tmp_path / "numeric_ids.csv"
    frame = _valid_predictions().copy()
    frame["customer_id"] = [str(10_000 + index) for index in range(len(frame))]
    frame.to_csv(prediction_path, index=False)

    loaded = Project1OOTPredictionAdapter(prediction_path).load()

    assert loaded["customer_id"].map(lambda value: isinstance(value, str)).all()
    result = run_validation(Project1OOTPredictionAdapter(prediction_path))
    assert result.input_audit.loc[
        result.input_audit["check"].eq("customer_id"), "status"
    ].item() == "pass"


def test_public_lendingclub_context_replaces_synthetic_limitation(tmp_path) -> None:
    prediction_path = tmp_path / "public_scores.csv"
    _valid_predictions().to_csv(prediction_path, index=False)

    result = run_validation(
        Project1OOTPredictionAdapter(
            prediction_path,
            data_context="public_lendingclub",
        )
    )

    limitations = set(result.model_limitations["limitation"])
    assert "synthetic_data" not in limitations
    assert "accepted_loan_selection_bias" in limitations
    horizon = result.model_limitations.loc[
        result.model_limitations["limitation"].eq("limited_oot_horizon"),
        "description",
    ].item()
    assert "2022-01-01 to 2022-12-01" in horizon
