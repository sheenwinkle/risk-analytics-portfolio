from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, Self

import pandas as pd

from model_validation.macro_remediation import MacroRemediationValidationResult
from model_validation.macro_satellite import MacroSatelliteValidationResult
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


@dataclass(frozen=True)
class MacroSatelliteRunMetadata:
    source_report_path: str
    source_commit_sha: str | None = None
    development_end: date = date(2015, 12, 31)
    validation_end: date = date(2018, 12, 31)
    oot_end: date = date(2021, 12, 31)

    def __post_init__(self) -> None:
        if not self.source_report_path.strip():
            raise ValueError("source_report_path must not be blank")
        cutoffs = (self.development_end, self.validation_end, self.oot_end)
        if not cutoffs[0] < cutoffs[1] < cutoffs[2]:
            raise ValueError("Macro model cutoffs must be increasing")
        if not all(pd.Timestamp(value).is_quarter_end for value in cutoffs):
            raise ValueError("Macro model cutoffs must be quarter-end dates")
        if self.oot_end >= date(2022, 3, 31):
            raise ValueError("Macro OOT period must end before the APS 220 reporting break")


@dataclass(frozen=True)
class MacroSatellitePersistenceRecords:
    run: dict[str, object]
    checks: tuple[dict[str, object], ...]
    findings: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class MacroRemediationRunMetadata:
    source_report_path: str
    source_commit_sha: str | None = None

    def __post_init__(self) -> None:
        if not self.source_report_path.strip():
            raise ValueError("source_report_path must not be blank")


@dataclass(frozen=True)
class MacroRemediationPersistenceRecords:
    run: dict[str, object]
    checks: tuple[dict[str, object], ...]
    events: tuple[dict[str, object], ...]


def build_macro_remediation_persistence_records(
    result: MacroRemediationValidationResult,
    metadata: MacroRemediationRunMetadata,
) -> MacroRemediationPersistenceRecords:
    summary = result.validation_summary
    required_checks = {
        "check",
        "metric_value",
        "threshold",
        "direction",
        "status",
        "rationale",
    }
    missing_checks = required_checks - set(summary.columns)
    if missing_checks:
        raise ValueError(
            "Macro remediation summary missing columns: "
            + ", ".join(sorted(missing_checks))
        )
    if summary.empty or summary["check"].duplicated().any():
        raise ValueError("Macro remediation checks must be non-empty and unique")
    if not set(summary["status"]).issubset({"pass", "warning", "fail"}):
        raise ValueError("Macro remediation summary contains unsupported statuses")
    if result.overall_opinion not in {"acceptable", "conditional", "restricted"}:
        raise ValueError("Macro remediation result contains an unsupported opinion")

    selection = result.selection_reperformance
    required_selection = {
        "developer_candidate_id",
        "developer_alpha",
        "selection_reconciled",
    }
    missing_selection = required_selection - set(selection.columns)
    if missing_selection:
        raise ValueError(
            "Macro remediation selection missing columns: "
            + ", ".join(sorted(missing_selection))
        )
    if len(selection) != 1 or not bool(selection.iloc[0]["selection_reconciled"]):
        raise ValueError("Macro remediation selection must independently reconcile")
    selected = selection.iloc[0]
    selected_alpha = float(selected["developer_alpha"])
    if not math.isfinite(selected_alpha) or selected_alpha <= 0:
        raise ValueError("Selected macro remediation alpha must be finite and positive")

    lifecycle = result.finding_lifecycle
    required_lifecycle = {
        "finding_id",
        "remediation_action",
        "retest_status",
        "retest_metric",
        "closure_status",
        "closure_reason",
        "evidence_freshness",
    }
    missing_lifecycle = required_lifecycle - set(lifecycle.columns)
    if missing_lifecycle:
        raise ValueError(
            "Macro finding lifecycle missing columns: "
            + ", ".join(sorted(missing_lifecycle))
        )
    expected_findings = {"MSV-001", "MSV-002", "MSV-003"}
    if set(lifecycle["finding_id"]) != expected_findings:
        raise ValueError("Macro finding lifecycle must cover MSV-001 through MSV-003")
    if lifecycle["finding_id"].duplicated().any():
        raise ValueError("Macro lifecycle finding IDs must be unique")
    evidence_freshness = set(lifecycle["evidence_freshness"])
    if len(evidence_freshness) != 1:
        raise ValueError("Macro finding lifecycle must use one evidence freshness label")
    evidence_label = str(next(iter(evidence_freshness)))
    if evidence_label not in {"reused_oot", "fresh_oot"}:
        raise ValueError("Macro finding lifecycle has unsupported evidence freshness")
    if evidence_label == "reused_oot" and lifecycle["closure_status"].eq("closed").any():
        raise ValueError("Reused OOT evidence cannot close a macro finding")

    run = {
        "selected_candidate_id": str(selected["developer_candidate_id"]),
        "selected_alpha": selected_alpha,
        "source_report_path": metadata.source_report_path,
        "source_commit_sha": metadata.source_commit_sha,
        "overall_opinion": result.overall_opinion,
        "intended_use": "sensitivity_only",
        "evidence_freshness": evidence_label,
    }
    checks = tuple(
        {
            "check_name": str(row["check"]),
            "metric_value": float(row["metric_value"]),
            "threshold": float(row["threshold"]),
            "direction": str(row["direction"]),
            "status": str(row["status"]),
            "rationale": str(row["rationale"]),
        }
        for _, row in summary.iterrows()
    )
    evidence_references = {
        "MSV-001": "replicated_performance.csv",
        "MSV-002": "validation_summary.csv",
        "MSV-003": "validation_summary.csv",
    }
    events = tuple(
        event
        for _, row in lifecycle.iterrows()
        for event in (
            {
                "finding_id": str(row["finding_id"]),
                "event_type": "remediation_retest",
                "event_status": str(row["retest_status"]),
                "metric_value": float(row["retest_metric"]),
                "evidence_freshness": str(row["evidence_freshness"]),
                "evidence_reference": evidence_references[str(row["finding_id"])],
                "detail": str(row["remediation_action"]),
            },
            {
                "finding_id": str(row["finding_id"]),
                "event_type": "closure_decision",
                "event_status": str(row["closure_status"]),
                "metric_value": None,
                "evidence_freshness": str(row["evidence_freshness"]),
                "evidence_reference": "finding_lifecycle.csv",
                "detail": str(row["closure_reason"]),
            },
        )
    )
    return MacroRemediationPersistenceRecords(run=run, checks=checks, events=events)


def build_macro_satellite_persistence_records(
    result: MacroSatelliteValidationResult,
    metadata: MacroSatelliteRunMetadata,
) -> MacroSatellitePersistenceRecords:
    summary = result.validation_summary
    required_checks = {
        "check",
        "metric_value",
        "threshold",
        "direction",
        "status",
        "rationale",
    }
    missing_checks = required_checks - set(summary.columns)
    if missing_checks:
        raise ValueError(
            "Macro validation summary missing columns: "
            + ", ".join(sorted(missing_checks))
        )
    if summary.empty or summary["check"].duplicated().any():
        raise ValueError("Macro validation checks must be non-empty and unique")
    if not set(summary["status"]).issubset({"pass", "warning", "fail"}):
        raise ValueError("Macro validation summary contains unsupported statuses")
    if result.overall_opinion not in {"acceptable", "conditional", "restricted"}:
        raise ValueError("Macro validation result contains an unsupported opinion")
    if len(result.replicated_performance) != 1:
        raise ValueError("Macro validation must contain exactly one replicated OOT row")
    validated_oot_end = _date(result.replicated_performance.iloc[0]["period_end"])
    if validated_oot_end != metadata.oot_end:
        raise ValueError("Metadata oot_end does not match validated OOT evidence")

    findings = result.findings
    required_findings = {
        "finding_id",
        "severity",
        "title",
        "status",
        "use_restriction",
        "required_action",
    }
    missing_findings = required_findings - set(findings.columns)
    if missing_findings:
        raise ValueError(
            "Macro validation findings missing columns: "
            + ", ".join(sorted(missing_findings))
        )
    if findings["finding_id"].duplicated().any():
        raise ValueError("Macro validation finding IDs must be unique")

    run = {
        "model_name": "australian_macro_satellite",
        "source_report_path": metadata.source_report_path,
        "source_commit_sha": metadata.source_commit_sha,
        "development_end": metadata.development_end,
        "validation_end": metadata.validation_end,
        "oot_end": metadata.oot_end,
        "overall_opinion": result.overall_opinion,
        "intended_use": "sensitivity_only",
    }
    check_records = tuple(
        {
            "check_name": str(row["check"]),
            "metric_value": float(row["metric_value"]),
            "threshold": float(row["threshold"]),
            "direction": str(row["direction"]),
            "status": str(row["status"]),
            "rationale": str(row["rationale"]),
        }
        for _, row in summary.iterrows()
    )
    finding_records = tuple(
        {
            "finding_id": str(row["finding_id"]),
            "severity": str(row["severity"]),
            "title": str(row["title"]),
            "status": str(row["status"]),
            "use_restriction": str(row["use_restriction"]),
            "required_action": str(row["required_action"]),
        }
        for _, row in findings.iterrows()
    )
    return MacroSatellitePersistenceRecords(
        run=run,
        checks=check_records,
        findings=finding_records,
    )


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


def persist_macro_satellite_result(
    connection: Connection,
    result: MacroSatelliteValidationResult,
    metadata: MacroSatelliteRunMetadata,
) -> int:
    records = build_macro_satellite_persistence_records(result, metadata)
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
                INSERT INTO model_validation_macro_run (
                    model_name, source_report_path, source_commit_sha,
                    development_end, validation_end, oot_end,
                    overall_opinion, intended_use
                ) VALUES (
                    %(model_name)s, %(source_report_path)s, %(source_commit_sha)s,
                    %(development_end)s, %(validation_end)s, %(oot_end)s,
                    %(overall_opinion)s, %(intended_use)s
                )
                RETURNING macro_validation_run_id
                """,
            records.run,
        )
        inserted = cursor.fetchone()
        if inserted is None:
            raise RuntimeError("PostgreSQL did not return a macro_validation_run_id")
        macro_validation_run_id = int(inserted[0])
        cursor.executemany(
            """
                INSERT INTO model_validation_macro_check (
                    macro_validation_run_id, check_name, metric_value,
                    threshold, direction, status, rationale
                ) VALUES (
                    %(macro_validation_run_id)s, %(check_name)s, %(metric_value)s,
                    %(threshold)s, %(direction)s, %(status)s, %(rationale)s
                )
                """,
            [
                dict(record, macro_validation_run_id=macro_validation_run_id)
                for record in records.checks
            ],
        )
        if records.findings:
            cursor.executemany(
                """
                    INSERT INTO model_validation_macro_finding (
                        macro_validation_run_id, finding_id, severity, title,
                        status, use_restriction, required_action
                    ) VALUES (
                        %(macro_validation_run_id)s, %(finding_id)s, %(severity)s,
                        %(title)s, %(status)s, %(use_restriction)s,
                        %(required_action)s
                    )
                    """,
                [
                    dict(record, macro_validation_run_id=macro_validation_run_id)
                    for record in records.findings
                ],
            )
    return macro_validation_run_id


def persist_macro_remediation_result(
    connection: Connection,
    macro_validation_run_id: int,
    result: MacroRemediationValidationResult,
    metadata: MacroRemediationRunMetadata,
) -> int:
    if macro_validation_run_id <= 0:
        raise ValueError("macro_validation_run_id must be positive")
    records = build_macro_remediation_persistence_records(result, metadata)
    run = dict(records.run, macro_validation_run_id=macro_validation_run_id)
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
                INSERT INTO model_validation_macro_remediation_run (
                    macro_validation_run_id, selected_candidate_id, selected_alpha,
                    source_report_path, source_commit_sha, overall_opinion,
                    intended_use, evidence_freshness
                ) VALUES (
                    %(macro_validation_run_id)s, %(selected_candidate_id)s,
                    %(selected_alpha)s, %(source_report_path)s, %(source_commit_sha)s,
                    %(overall_opinion)s, %(intended_use)s, %(evidence_freshness)s
                )
                RETURNING macro_remediation_run_id
                """,
            run,
        )
        inserted = cursor.fetchone()
        if inserted is None:
            raise RuntimeError("PostgreSQL did not return a macro_remediation_run_id")
        macro_remediation_run_id = int(inserted[0])
        cursor.executemany(
            """
                INSERT INTO model_validation_macro_remediation_check (
                    macro_remediation_run_id, check_name, metric_value,
                    threshold, direction, status, rationale
                ) VALUES (
                    %(macro_remediation_run_id)s, %(check_name)s, %(metric_value)s,
                    %(threshold)s, %(direction)s, %(status)s, %(rationale)s
                )
                """,
            [
                dict(record, macro_remediation_run_id=macro_remediation_run_id)
                for record in records.checks
            ],
        )
        cursor.executemany(
            """
                INSERT INTO model_validation_macro_finding_event (
                    macro_remediation_run_id, macro_validation_run_id, finding_id,
                    event_type, event_status, metric_value, evidence_freshness,
                    evidence_reference, detail
                ) VALUES (
                    %(macro_remediation_run_id)s, %(macro_validation_run_id)s,
                    %(finding_id)s, %(event_type)s, %(event_status)s,
                    %(metric_value)s, %(evidence_freshness)s,
                    %(evidence_reference)s, %(detail)s
                )
                """,
            [
                dict(
                    record,
                    macro_remediation_run_id=macro_remediation_run_id,
                    macro_validation_run_id=macro_validation_run_id,
                )
                for record in records.events
            ],
        )
    return macro_remediation_run_id


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
