from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, Self

import pandas as pd

from model_validation.remediation import RemediationResult
from model_validation.validation import ValidationResult

STATUS_PRIORITY = {"pass": 0, "warning": 1, "fail": 2}


class Cursor(Protocol):
    def execute(self, query: str, params: dict[str, object]) -> Any: ...

    def executemany(self, query: str, params_seq: list[dict[str, object]]) -> Any: ...

    def fetchone(self) -> tuple[object, ...] | None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...


class Transaction(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def transaction(self) -> Transaction: ...


@dataclass(frozen=True)
class ValidationRunMetadata:
    source_report_path: str
    source_commit_sha: str | None = None

    def __post_init__(self) -> None:
        if not self.source_report_path.strip():
            raise ValueError("source_report_path must not be blank")


@dataclass(frozen=True)
class ValidationPersistenceRecords:
    run: dict[str, object]
    metrics: tuple[dict[str, object], ...]
    uncertainty: tuple[dict[str, object], ...]
    group_performance: tuple[dict[str, object], ...]
    characteristic_summaries: tuple[dict[str, object], ...]
    characteristic_bins: tuple[dict[str, object], ...]
    findings: tuple[dict[str, object], ...]
    benchmarks: tuple[dict[str, object], ...]
    limitations: tuple[dict[str, object], ...]


def build_persistence_records(
    result: ValidationResult,
    metadata: ValidationRunMetadata,
) -> ValidationPersistenceRecords:
    selected = result.model_metrics.loc[
        result.model_metrics["score_version"].eq("recalibrated")
    ]
    if len(selected) != 1:
        raise ValueError("Validation result must contain exactly one recalibrated selected model")
    selected_row = selected.iloc[0]

    if len(result.stability_summary) != 1:
        raise ValueError("Validation result must contain exactly one stability summary row")
    stability = result.stability_summary.iloc[0]
    statuses = result.validation_summary["status"].astype(str).tolist()
    if not statuses or any(status not in STATUS_PRIORITY for status in statuses):
        raise ValueError("Validation summary contains unsupported or missing policy statuses")

    run = {
        "model_name": str(selected_row["model_name"]),
        "score_version": str(selected_row["score_version"]),
        "source_report_path": metadata.source_report_path,
        "source_commit_sha": metadata.source_commit_sha,
        "reference_start": _date(stability["reference_start"]),
        "reference_end": _date(stability["reference_end"]),
        "current_start": _date(stability["current_start"]),
        "current_end": _date(stability["current_end"]),
        "reference_observations": int(stability["reference_observations"]),
        "current_observations": int(stability["current_observations"]),
        "requested_bins": int(stability["requested_bins"]),
        "effective_bins": int(stability["effective_bins"]),
        "overall_status": max(statuses, key=STATUS_PRIORITY.__getitem__),
    }

    metrics = tuple(
        {
            "check_name": str(row["check"]),
            "metric_value": float(row["metric_value"]),
            "direction": str(row["direction"]),
            "green_threshold": float(row["green_threshold"]),
            "warning_threshold": float(row["warning_threshold"]),
            "status": str(row["status"]),
            "detail": str(row["detail"]),
        }
        for _, row in result.validation_summary.iterrows()
    )
    findings = tuple(
        {
            "check_name": str(row["check"]),
            "status": str(row["status"]),
            "finding": str(row["finding"]),
            "recommended_action": str(row["recommended_action"]),
        }
        for _, row in result.validation_findings.iterrows()
    )
    uncertainty = tuple(
        {
            key: _python_value(row[key])
            for key in (
                "metric",
                "estimate",
                "lower_bound",
                "upper_bound",
                "confidence_level",
                "method",
                "observations",
                "defaults",
            )
        }
        for _, row in result.metric_uncertainty.iterrows()
    )
    group_performance = (
        *_group_performance_records(
            result.vintage_performance,
            group_type="vintage",
            dimension_column=None,
            value_column="vintage_quarter",
        ),
        *_group_performance_records(
            result.segment_performance,
            group_type="segment",
            dimension_column="segment_dimension",
            value_column="segment_value",
        ),
    )
    characteristic_summaries = tuple(
        {
            "feature_name": str(row["feature_name"]),
            "feature_type": str(row["feature_type"]),
            "reference_start": _date(row["reference_start"]),
            "reference_end": _date(row["reference_end"]),
            "current_start": _date(row["current_start"]),
            "current_end": _date(row["current_end"]),
            "reference_observations": int(row["reference_observations"]),
            "current_observations": int(row["current_observations"]),
            "reference_missing_rate": float(row["reference_missing_rate"]),
            "current_missing_rate": float(row["current_missing_rate"]),
            "missing_rate_delta": float(row["missing_rate_delta"]),
            "requested_bins": (
                None if pd.isna(row["requested_bins"]) else int(row["requested_bins"])
            ),
            "effective_bins": int(row["effective_bins"]),
            "binning_method": str(row["binning_method"]),
            "availability_status": str(row["availability_status"]),
            "characteristic_stability_index": float(
                row["characteristic_stability_index"]
            ),
            "stability_status": str(row["stability_status"]),
        }
        for _, row in result.characteristic_stability_summary.iterrows()
    )
    characteristic_bins = tuple(
        {
            "feature_name": str(row["feature_name"]),
            "feature_type": str(row["feature_type"]),
            "bin": str(row["bin"]),
            "bin_label": str(row["bin_label"]),
            "lower_bound": _python_value(row["lower_bound"]),
            "upper_bound": _python_value(row["upper_bound"]),
            "category_value": _python_value(row["category_value"]),
            "reference_observations": int(row["reference_observations"]),
            "current_observations": int(row["current_observations"]),
            "reference_share": float(row["reference_share"]),
            "current_share": float(row["current_share"]),
            "csi_component": float(row["csi_component"]),
        }
        for _, row in result.characteristic_stability_bins.iterrows()
    )
    benchmarks = tuple(
        {
            key: _python_value(row[key])
            for key in (
                "comparison",
                "baseline_model",
                "baseline_score_version",
                "benchmark_model",
                "benchmark_score_version",
                "baseline_auc",
                "benchmark_auc",
                "auc_delta",
                "baseline_ks",
                "benchmark_ks",
                "ks_delta",
                "baseline_absolute_calibration_gap",
                "benchmark_absolute_calibration_gap",
                "absolute_calibration_gap_delta",
                "baseline_brier_score",
                "benchmark_brier_score",
                "brier_score_delta",
            )
        }
        for _, row in result.benchmark_comparison.iterrows()
    )
    limitations = tuple(
        {
            "limitation": str(row["limitation"]),
            "severity": str(row["severity"]),
            "description": str(row["description"]),
            "mitigation": str(row["mitigation"]),
        }
        for _, row in result.model_limitations.iterrows()
    )
    return ValidationPersistenceRecords(
        run=run,
        metrics=metrics,
        uncertainty=uncertainty,
        group_performance=group_performance,
        characteristic_summaries=characteristic_summaries,
        characteristic_bins=characteristic_bins,
        findings=findings,
        benchmarks=benchmarks,
        limitations=limitations,
    )


def persist_validation_result(
    connection: Connection,
    result: ValidationResult,
    metadata: ValidationRunMetadata,
) -> int:
    records = build_persistence_records(result, metadata)
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
                INSERT INTO model_validation_run (
                    model_name, score_version, source_report_path, source_commit_sha,
                    reference_start, reference_end, current_start, current_end,
                    reference_observations, current_observations, requested_bins,
                    effective_bins, overall_status
                ) VALUES (
                    %(model_name)s, %(score_version)s, %(source_report_path)s,
                    %(source_commit_sha)s, %(reference_start)s, %(reference_end)s,
                    %(current_start)s, %(current_end)s, %(reference_observations)s,
                    %(current_observations)s, %(requested_bins)s, %(effective_bins)s,
                    %(overall_status)s
                )
                RETURNING validation_run_id
                """,
            records.run,
        )
        inserted = cursor.fetchone()
        if inserted is None:
            raise RuntimeError("PostgreSQL did not return a validation_run_id")
        validation_run_id = int(inserted[0])

        _insert_metrics(cursor, validation_run_id, records.metrics)
        _insert_uncertainty(cursor, validation_run_id, records.uncertainty)
        _insert_group_performance(
            cursor,
            validation_run_id,
            records.group_performance,
        )
        _insert_characteristic_summaries(
            cursor,
            validation_run_id,
            records.characteristic_summaries,
        )
        _insert_characteristic_bins(
            cursor,
            validation_run_id,
            records.characteristic_bins,
        )
        _insert_findings(cursor, validation_run_id, records.findings)
        _insert_benchmarks(cursor, validation_run_id, records.benchmarks)
        _insert_limitations(cursor, validation_run_id, records.limitations)
    return validation_run_id


def persist_remediation_result(
    connection: Connection,
    validation_run_id: int,
    result: RemediationResult,
) -> int:
    if len(result.finding_lifecycle) != 1:
        raise ValueError("Remediation result must contain exactly one finding lifecycle row")
    lifecycle = result.finding_lifecycle.iloc[0]
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT finding_id
                FROM model_validation_finding
                WHERE validation_run_id = %(validation_run_id)s
                  AND check_name = %(check_name)s
                """,
            {
                "validation_run_id": validation_run_id,
                "check_name": str(lifecycle["check"]),
            },
        )
        selected = cursor.fetchone()
        if selected is None:
            raise ValueError("Matching validation finding was not persisted")
        finding_id = int(selected[0])
        cursor.execute(
            """
                UPDATE model_validation_finding
                SET lifecycle_status = %(lifecycle_status)s
                WHERE finding_id = %(finding_id)s
                """,
            {
                "lifecycle_status": str(lifecycle["closure_status"]),
                "finding_id": finding_id,
            },
        )
        cursor.executemany(
            """
                INSERT INTO model_validation_finding_event (
                    finding_id, event_type, event_status, metric_value,
                    evidence_reference, detail
                ) VALUES (
                    %(finding_id)s, %(event_type)s, %(event_status)s,
                    %(metric_value)s, %(evidence_reference)s, %(detail)s
                )
                """,
            [
                {
                    "finding_id": finding_id,
                    "event_type": "identified",
                    "event_status": str(lifecycle["initial_status"]),
                    "metric_value": float(lifecycle["initial_metric_value"]),
                    "evidence_reference": "validation_findings.csv",
                    "detail": "Initial independent validation finding.",
                },
                {
                    "finding_id": finding_id,
                    "event_type": "remediation_retest",
                    "event_status": str(lifecycle["retest_status"]),
                    "metric_value": float(lifecycle["retest_metric_value"]),
                    "evidence_reference": str(lifecycle["evidence_reference"]),
                    "detail": str(lifecycle["remediation_action"]),
                },
                {
                    "finding_id": finding_id,
                    "event_type": "closure_decision",
                    "event_status": str(lifecycle["closure_status"]),
                    "metric_value": None,
                    "evidence_reference": str(lifecycle["evidence_reference"]),
                    "detail": str(lifecycle["closure_reason"]),
                },
            ],
        )
    return finding_id


def _insert_metrics(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_metric (
            validation_run_id, check_name, metric_value, direction, green_threshold,
            warning_threshold, status, detail
        ) VALUES (
            %(validation_run_id)s, %(check_name)s, %(metric_value)s, %(direction)s,
            %(green_threshold)s, %(warning_threshold)s, %(status)s, %(detail)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_findings(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    if not records:
        return
    cursor.executemany(
        """
        INSERT INTO model_validation_finding (
            validation_run_id, check_name, status, finding, recommended_action
        ) VALUES (
            %(validation_run_id)s, %(check_name)s, %(status)s, %(finding)s,
            %(recommended_action)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_uncertainty(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_uncertainty (
            validation_run_id, metric, estimate, lower_bound, upper_bound,
            confidence_level, method, observations, defaults
        ) VALUES (
            %(validation_run_id)s, %(metric)s, %(estimate)s, %(lower_bound)s,
            %(upper_bound)s, %(confidence_level)s, %(method)s, %(observations)s,
            %(defaults)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_group_performance(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_group_performance (
            validation_run_id, group_type, group_dimension, group_value,
            observations, portfolio_share, defaults, non_defaults,
            expected_defaults, mean_pd, observed_default_rate,
            observed_default_rate_lower, observed_default_rate_upper,
            calibration_gap, calibration_gap_lower, calibration_gap_upper,
            expected_to_observed_ratio, roc_auc, roc_auc_lower, roc_auc_upper,
            ks, discrimination_status, reliability_status, calibration_signal
        ) VALUES (
            %(validation_run_id)s, %(group_type)s, %(group_dimension)s,
            %(group_value)s, %(observations)s, %(portfolio_share)s, %(defaults)s,
            %(non_defaults)s, %(expected_defaults)s, %(mean_pd)s,
            %(observed_default_rate)s, %(observed_default_rate_lower)s,
            %(observed_default_rate_upper)s, %(calibration_gap)s,
            %(calibration_gap_lower)s, %(calibration_gap_upper)s,
            %(expected_to_observed_ratio)s, %(roc_auc)s, %(roc_auc_lower)s,
            %(roc_auc_upper)s, %(ks)s, %(discrimination_status)s,
            %(reliability_status)s, %(calibration_signal)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_characteristic_summaries(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_characteristic_summary (
            validation_run_id, feature_name, feature_type,
            reference_start, reference_end, current_start, current_end,
            reference_observations, current_observations,
            reference_missing_rate, current_missing_rate, missing_rate_delta,
            requested_bins, effective_bins, binning_method, availability_status,
            characteristic_stability_index, stability_status
        ) VALUES (
            %(validation_run_id)s, %(feature_name)s, %(feature_type)s,
            %(reference_start)s, %(reference_end)s, %(current_start)s, %(current_end)s,
            %(reference_observations)s, %(current_observations)s,
            %(reference_missing_rate)s, %(current_missing_rate)s, %(missing_rate_delta)s,
            %(requested_bins)s, %(effective_bins)s, %(binning_method)s,
            %(availability_status)s, %(characteristic_stability_index)s,
            %(stability_status)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_characteristic_bins(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_characteristic_bin (
            validation_run_id, feature_name, feature_type, bin, bin_label,
            lower_bound, upper_bound, category_value,
            reference_observations, current_observations,
            reference_share, current_share, csi_component
        ) VALUES (
            %(validation_run_id)s, %(feature_name)s, %(feature_type)s,
            %(bin)s, %(bin_label)s, %(lower_bound)s, %(upper_bound)s,
            %(category_value)s, %(reference_observations)s,
            %(current_observations)s, %(reference_share)s,
            %(current_share)s, %(csi_component)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_benchmarks(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_benchmark (
            validation_run_id, comparison, baseline_model, baseline_score_version,
            benchmark_model, benchmark_score_version, baseline_auc, benchmark_auc,
            auc_delta, baseline_ks, benchmark_ks, ks_delta,
            baseline_absolute_calibration_gap, benchmark_absolute_calibration_gap,
            absolute_calibration_gap_delta, baseline_brier_score,
            benchmark_brier_score, brier_score_delta
        ) VALUES (
            %(validation_run_id)s, %(comparison)s, %(baseline_model)s,
            %(baseline_score_version)s, %(benchmark_model)s,
            %(benchmark_score_version)s, %(baseline_auc)s, %(benchmark_auc)s,
            %(auc_delta)s, %(baseline_ks)s, %(benchmark_ks)s, %(ks_delta)s,
            %(baseline_absolute_calibration_gap)s,
            %(benchmark_absolute_calibration_gap)s,
            %(absolute_calibration_gap_delta)s, %(baseline_brier_score)s,
            %(benchmark_brier_score)s, %(brier_score_delta)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _insert_limitations(
    cursor: Cursor,
    validation_run_id: int,
    records: tuple[dict[str, object], ...],
) -> None:
    cursor.executemany(
        """
        INSERT INTO model_validation_limitation (
            validation_run_id, limitation, severity, description, mitigation
        ) VALUES (
            %(validation_run_id)s, %(limitation)s, %(severity)s, %(description)s,
            %(mitigation)s
        )
        """,
        _with_run_id(records, validation_run_id),
    )


def _with_run_id(
    records: tuple[dict[str, object], ...],
    validation_run_id: int,
) -> list[dict[str, object]]:
    return [dict(record, validation_run_id=validation_run_id) for record in records]


def _group_performance_records(
    frame: pd.DataFrame,
    *,
    group_type: str,
    dimension_column: str | None,
    value_column: str,
) -> tuple[dict[str, object], ...]:
    metric_columns = (
        "observations",
        "portfolio_share",
        "defaults",
        "non_defaults",
        "expected_defaults",
        "mean_pd",
        "observed_default_rate",
        "observed_default_rate_lower",
        "observed_default_rate_upper",
        "calibration_gap",
        "calibration_gap_lower",
        "calibration_gap_upper",
        "expected_to_observed_ratio",
        "roc_auc",
        "roc_auc_lower",
        "roc_auc_upper",
        "ks",
        "discrimination_status",
        "reliability_status",
        "calibration_signal",
    )
    records = []
    for _, row in frame.iterrows():
        records.append(
            {
                "group_type": group_type,
                "group_dimension": (
                    str(row[dimension_column])
                    if dimension_column is not None
                    else "vintage_quarter"
                ),
                "group_value": str(row[value_column]),
                **{column: _python_value(row[column]) for column in metric_columns},
            }
        )
    return tuple(records)


def _date(value: object) -> date:
    return pd.Timestamp(value).date()


def _python_value(value: object) -> object:
    if isinstance(value, str):
        return value
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
