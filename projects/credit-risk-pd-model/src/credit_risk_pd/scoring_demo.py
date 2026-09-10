from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk_pd.serving import (
    APPLICATION_COLUMNS,
    PDScoringService,
    ScoringBatchResult,
    load_scoring_service,
    load_scoring_service_from_manifest,
)

REPLAY_TOLERANCE = 1e-12
REPORTING_DECIMAL_PLACES = 12
RISK_BAND_ORDER = ("low", "moderate", "high", "very_high")
SCORING_DATA_CONTEXTS = frozenset({"public_lendingclub", "synthetic_demo"})


@dataclass(frozen=True)
class ScoringDemoOutput:
    scoring: ScoringBatchResult
    reconciliation: pd.DataFrame
    report_paths: dict[str, Path]


def run_scoring_service_demo(
    *,
    manifest_path: str | Path,
    prediction_path: str | Path,
    output_dir: str | Path,
    data_context: str = "synthetic_demo",
    model_path: str | Path | None = None,
) -> ScoringDemoOutput:
    """Replay frozen OOT features through the deployed service and publish aggregates."""
    if data_context not in SCORING_DATA_CONTEXTS:
        allowed = ", ".join(sorted(SCORING_DATA_CONTEXTS))
        raise ValueError(f"data_context must be one of: {allowed}")
    predictions = pd.read_csv(prediction_path)
    applications, expected_pd = _replay_inputs(predictions)
    service = (
        load_scoring_service_from_manifest(manifest_path)
        if model_path is None
        else load_scoring_service(model_path, manifest_path)
    )
    scoring = _score_replay_batches(service, applications)
    deltas = np.abs(
        scoring.scores["recalibrated_pd"].to_numpy(dtype=float) - expected_pd
    )
    maximum_delta = float(deltas.max())
    reconciliation = pd.DataFrame(
        [
            {
                "model_version": service.manifest.model_version,
                "selected_model_name": service.manifest.selected_model_name,
                "contract_version": service.manifest.contract_version,
                "contract_sha256": service.manifest.contract_sha256,
                "policy_decision": service.manifest.policy_decision,
                "data_context": data_context,
                "approval_cutoff": service.manifest.approval_cutoff,
                "records_replayed": len(applications),
                "batches_scored": int(scoring.audit.loc[0, "batches_scored"]),
                "reporting_decimal_places": REPORTING_DECIMAL_PLACES,
                "expected_mean_pd": round(
                    float(expected_pd.mean()), REPORTING_DECIMAL_PLACES
                ),
                "service_mean_pd": round(
                    float(scoring.scores["recalibrated_pd"].mean()),
                    REPORTING_DECIMAL_PLACES,
                ),
                "mean_absolute_pd_delta": round(
                    float(deltas.mean()), REPORTING_DECIMAL_PLACES
                ),
                "maximum_absolute_pd_delta": round(
                    maximum_delta, REPORTING_DECIMAL_PLACES
                ),
                "replay_tolerance": REPLAY_TOLERANCE,
                "replay_reconciled": maximum_delta <= REPLAY_TOLERANCE,
                "artifact_integrity_verified": bool(
                    scoring.audit.loc[0, "artifact_integrity_verified"]
                ),
            }
        ]
    )
    score_bands = _score_band_summary(scoring.scores)
    safe_audit = scoring.audit.drop(columns="artifact_sha256")
    safe_audit["mean_recalibrated_pd"] = safe_audit["mean_recalibrated_pd"].round(
        REPORTING_DECIMAL_PLACES
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_paths = _write_reports(
        reconciliation,
        score_bands,
        safe_audit,
        scoring.data_quality,
        output_path,
    )
    return ScoringDemoOutput(
        scoring=scoring,
        reconciliation=reconciliation,
        report_paths=report_paths,
    )


def _score_replay_batches(
    service: PDScoringService,
    applications: pd.DataFrame,
) -> ScoringBatchResult:
    batch_results = []
    batch_size = service.manifest.max_batch_size
    scored_at = datetime(2026, 1, 1, tzinfo=UTC)
    for batch_number, start in enumerate(range(0, len(applications), batch_size), start=1):
        batch_results.append(
            service.score_batch(
                applications.iloc[start : start + batch_size],
                request_id=f"oot-replay-001-{batch_number:04d}",
                scored_at=scored_at,
            )
        )

    scores = pd.concat(
        [result.scores for result in batch_results],
        ignore_index=True,
    )
    quality = pd.concat(
        [result.data_quality for result in batch_results],
        ignore_index=True,
    )
    data_quality = (
        quality.groupby(["feature", "feature_type"], as_index=False, sort=False)[
            ["records", "missing_count", "unseen_category_count"]
        ]
        .sum()
    )
    data_quality["missing_rate"] = (
        data_quality["missing_count"] / data_quality["records"]
    )
    data_quality["unseen_category_rate"] = (
        data_quality["unseen_category_count"] / data_quality["records"]
    )
    data_quality = data_quality.loc[
        :,
        [
            "feature",
            "feature_type",
            "records",
            "missing_count",
            "missing_rate",
            "unseen_category_count",
            "unseen_category_rate",
        ],
    ]

    audit = batch_results[0].audit.copy()
    within_cutoff = scores["policy_outcome"].eq("within_cutoff")
    audit.loc[0, "request_id"] = "oot-replay-001"
    audit.loc[0, "records_scored"] = len(scores)
    audit.loc[0, "batches_scored"] = len(batch_results)
    audit.loc[0, "within_cutoff_count"] = int(within_cutoff.sum())
    audit.loc[0, "within_cutoff_rate"] = float(within_cutoff.mean())
    audit.loc[0, "mean_recalibrated_pd"] = float(scores["recalibrated_pd"].mean())
    audit.loc[0, "missing_input_values"] = int(data_quality["missing_count"].sum())
    audit.loc[0, "unseen_category_values"] = int(
        data_quality["unseen_category_count"].sum()
    )
    return ScoringBatchResult(
        scores=scores,
        audit=audit,
        data_quality=data_quality,
    )


def _replay_inputs(predictions: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    required = {
        "customer_id",
        "recalibrated_pd",
        *(column for column in APPLICATION_COLUMNS if column != "application_id"),
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(
            "Frozen prediction file missing scoring fields: "
            + ", ".join(sorted(missing))
        )
    if predictions.empty:
        raise ValueError("Frozen prediction file must contain records")
    customer_ids = predictions["customer_id"].astype("string").str.strip()
    if customer_ids.isna().any() or customer_ids.eq("").any():
        raise ValueError("customer_id must be non-empty")
    if customer_ids.duplicated().any():
        raise ValueError("customer_id must be unique across the frozen OOT file")
    applications = predictions.rename(
        columns={"customer_id": "application_id"}
    ).loc[:, APPLICATION_COLUMNS]
    applications.loc[:, "application_id"] = customer_ids
    expected_pd = pd.to_numeric(
        predictions["recalibrated_pd"],
        errors="coerce",
    ).to_numpy(dtype=float)
    if not np.isfinite(expected_pd).all() or (
        (expected_pd < 0) | (expected_pd > 1)
    ).any():
        raise ValueError("Frozen recalibrated PD must contain finite probabilities")
    return applications, expected_pd


def _score_band_summary(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(scores)
    for risk_band in RISK_BAND_ORDER:
        sample = scores.loc[scores["risk_band"].eq(risk_band)]
        within_cutoff = sample["policy_outcome"].eq("within_cutoff")
        rows.append(
            {
                "risk_band": risk_band,
                "records": len(sample),
                "portfolio_share": len(sample) / total,
                "mean_recalibrated_pd": (
                    round(
                        float(sample["recalibrated_pd"].mean()),
                        REPORTING_DECIMAL_PLACES,
                    )
                    if not sample.empty
                    else np.nan
                ),
                "minimum_recalibrated_pd": (
                    round(
                        float(sample["recalibrated_pd"].min()),
                        REPORTING_DECIMAL_PLACES,
                    )
                    if not sample.empty
                    else np.nan
                ),
                "maximum_recalibrated_pd": (
                    round(
                        float(sample["recalibrated_pd"].max()),
                        REPORTING_DECIMAL_PLACES,
                    )
                    if not sample.empty
                    else np.nan
                ),
                "within_cutoff_count": int(within_cutoff.sum()),
                "within_cutoff_rate": (
                    float(within_cutoff.mean()) if not sample.empty else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_reports(
    reconciliation: pd.DataFrame,
    score_bands: pd.DataFrame,
    scoring_audit: pd.DataFrame,
    data_quality: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    frames = {
        "scoring_reconciliation.csv": reconciliation,
        "score_band_summary.csv": score_bands,
        "scoring_audit.csv": scoring_audit,
        "data_quality_summary.csv": data_quality,
    }
    report_paths = {}
    for file_name, frame in frames.items():
        path = output_dir / file_name
        frame.to_csv(
            path,
            index=False,
            float_format=f"%.{REPORTING_DECIMAL_PLACES}f",
            lineterminator="\n",
        )
        report_paths[file_name] = path
    report_path = output_dir / "scoring_service_report.md"
    report_path.write_text(
        _markdown_report(reconciliation, score_bands, scoring_audit, data_quality),
        encoding="utf-8",
        newline="\n",
    )
    report_paths[report_path.name] = report_path
    return report_paths


def _markdown_report(
    reconciliation: pd.DataFrame,
    score_bands: pd.DataFrame,
    scoring_audit: pd.DataFrame,
    data_quality: pd.DataFrame,
) -> str:
    replay = reconciliation.iloc[0]
    audit = scoring_audit.iloc[0]
    unseen = int(data_quality["unseen_category_count"].sum())
    missing = int(data_quality["missing_count"].sum())
    band_lines = [
        (
            f"| {row['risk_band']} | {int(row['records'])} | "
            f"{row['portfolio_share']:.2%} | "
            f"{_format_optional_percentage(row['mean_recalibrated_pd'])} |"
        )
        for _, row in score_bands.iterrows()
    ]
    return "\n".join(
        [
            "# Governed PD Scoring Service",
            "",
            "## Deployment Reconciliation",
            "",
            f"- Model version: `{replay['model_version']}`.",
            f"- Selected estimator: `{replay['selected_model_name']}`.",
            f"- Policy decision: `{replay['policy_decision']}`.",
            f"- Data context: `{replay['data_context']}`.",
            f"- Active maximum-PD cutoff: {replay['approval_cutoff']:.2%}.",
            f"- Frozen OOT records replayed: {int(replay['records_replayed']):,}.",
            f"- Governed scoring batches executed: {int(replay['batches_scored']):,}.",
            (
                "- Maximum offline-versus-service PD delta at "
                f"{int(replay['reporting_decimal_places'])} decimal places: "
                f"{replay['maximum_absolute_pd_delta']:.2e}."
            ),
            f"- Replay reconciled at 1e-12: **{bool(replay['replay_reconciled'])}**.",
            (
                "- Artifact integrity verified: "
                f"**{bool(replay['artifact_integrity_verified'])}**."
            ),
            "",
            "## Score Distribution",
            "",
            "| Risk band | Records | Share | Mean PD |",
            "| --- | ---: | ---: | ---: |",
            *band_lines,
            "",
            "## Input Monitoring",
            "",
            (
                "- Missing input cells accepted by the fitted preprocessing contract: "
                f"{missing:,}."
            ),
            f"- Unseen categorical values handled and flagged: {unseen}.",
            f"- Records within the governed cutoff: {int(audit['within_cutoff_count']):,}.",
            "",
            "## Governance Boundary",
            "",
            (
                "The API returns rule-based policy input flags for monitoring. They are "
                "not local model attribution, adverse-action reasons, or an automated "
                "credit approval. Authentication, authorization, durable logging, model "
                "registry signatures, and production infrastructure remain outside this "
                "portfolio reference implementation."
            ),
            "",
            (
                "Only aggregate replay evidence is committed. Application identifiers, "
                "row-level scores, the model binary, and the artifact digest remain local."
            ),
            "",
        ]
    )


def _format_optional_percentage(value: object) -> str:
    return "not_available" if pd.isna(value) else f"{float(value):.2%}"
