from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from credit_risk_pd.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    add_credit_features,
)

SCORING_CONTRACT_VERSION = "1.0"
ALLOWED_POLICY_DECISIONS = frozenset({"advance_challenger", "retain_incumbent"})
DERIVED_FEATURES = ("loan_to_income",)
APPLICATION_NUMERIC_FEATURES = tuple(
    feature for feature in NUMERIC_FEATURES if feature not in DERIVED_FEATURES
)
APPLICATION_CATEGORICAL_FEATURES = tuple(CATEGORICAL_FEATURES)
APPLICATION_COLUMNS = (
    "application_id",
    *APPLICATION_NUMERIC_FEATURES,
    *APPLICATION_CATEGORICAL_FEATURES,
)
RISK_BAND_EDGES = (0.10, 0.15, 0.25)
EXPLANATION_METHOD = "policy_input_flags_not_model_attribution"
NUMERIC_BOUNDS = {
    "age": (18.0, 120.0, True),
    "annual_income": (0.0, None, True),
    "debt_to_income": (-0.01, 10.0, True),
    "credit_utilisation": (0.0, 5.0, True),
    "delinquencies_2y": (0.0, None, True),
    "loan_amount": (0.0, None, False),
    "interest_rate": (0.0, 1.0, True),
    "employment_length": (0.0, 80.0, True),
}


@dataclass(frozen=True)
class DeploymentManifest:
    contract_version: str
    model_version: str
    selected_model_name: str
    artifact_filename: str
    artifact_sha256: str
    contract_sha256: str
    approval_cutoff: float
    policy_decision: str
    max_batch_size: int
    application_columns: tuple[str, ...]
    derived_features: tuple[str, ...]
    categorical_levels: dict[str, tuple[str, ...]]
    numeric_bounds: dict[str, dict[str, float | bool | None]]
    risk_band_edges: tuple[float, ...]
    explanation_method: str


@dataclass(frozen=True)
class ScoringBatchResult:
    scores: pd.DataFrame
    audit: pd.DataFrame
    data_quality: pd.DataFrame


@dataclass(frozen=True)
class PDScoringService:
    model: Any
    manifest: DeploymentManifest

    def score_batch(
        self,
        applications: pd.DataFrame,
        *,
        request_id: str,
        scored_at: datetime,
    ) -> ScoringBatchResult:
        normalized = _validate_applications(applications, self.manifest)
        features = add_credit_features(normalized.drop(columns="application_id"))
        raw_pd = np.asarray(self.model.predict_raw_proba(features), dtype=float)
        recalibrated_pd = np.asarray(self.model.predict_proba(features), dtype=float)[:, 1]
        expected_shape = (len(normalized),)
        if not (
            raw_pd.shape == expected_shape
            and recalibrated_pd.shape == expected_shape
            and np.isfinite(raw_pd).all()
            and np.isfinite(recalibrated_pd).all()
            and ((0 <= raw_pd) & (raw_pd <= 1)).all()
            and ((0 <= recalibrated_pd) & (recalibrated_pd <= 1)).all()
        ):
            raise ValueError("Model returned invalid probability output")

        scores = pd.DataFrame(
            {
                "application_id": normalized["application_id"].to_numpy(),
                "raw_pd": raw_pd,
                "recalibrated_pd": recalibrated_pd,
                "risk_band": _risk_bands(recalibrated_pd),
                "policy_outcome": np.where(
                    recalibrated_pd <= self.manifest.approval_cutoff,
                    "within_cutoff",
                    "above_cutoff",
                ),
                "input_risk_flags": [
                    _input_risk_flags(row) for _, row in features.iterrows()
                ],
            }
        )
        data_quality = _data_quality_summary(normalized, self.manifest)
        within_cutoff = scores["policy_outcome"].eq("within_cutoff")
        audit = pd.DataFrame(
            [
                {
                    "request_id": _nonblank(request_id, "request_id"),
                    "scored_at_utc": _utc_isoformat(scored_at),
                    "contract_version": self.manifest.contract_version,
                    "model_version": self.manifest.model_version,
                    "selected_model_name": self.manifest.selected_model_name,
                    "contract_sha256": self.manifest.contract_sha256,
                    "artifact_sha256": self.manifest.artifact_sha256,
                    "artifact_integrity_verified": True,
                    "records_scored": len(scores),
                    "batches_scored": 1,
                    "approval_cutoff": self.manifest.approval_cutoff,
                    "within_cutoff_count": int(within_cutoff.sum()),
                    "within_cutoff_rate": float(within_cutoff.mean()),
                    "mean_recalibrated_pd": float(recalibrated_pd.mean()),
                    "explanation_method": EXPLANATION_METHOD,
                    "missing_input_values": int(data_quality["missing_count"].sum()),
                    "unseen_category_values": int(
                        data_quality["unseen_category_count"].sum()
                    ),
                }
            ]
        )
        return ScoringBatchResult(
            scores=scores,
            audit=audit,
            data_quality=data_quality,
        )


def write_deployment_manifest(
    artifact_path: str | Path,
    model: Any,
    *,
    model_version: str,
    approval_cutoff: float,
    policy_decision: str,
    max_batch_size: int = 1_000,
    output_path: str | Path | None = None,
) -> Path:
    artifact = Path(artifact_path)
    if not artifact.is_file():
        raise FileNotFoundError(f"Model artifact not found: {artifact}")
    version = _nonblank(model_version, "model_version")
    selected_model_name = _nonblank(
        getattr(model, "selected_model_name", ""),
        "selected_model_name",
    )
    cutoff = _probability(approval_cutoff, "approval_cutoff")
    decision = _policy_decision(policy_decision)
    if isinstance(max_batch_size, bool) or not isinstance(max_batch_size, int):
        raise TypeError("max_batch_size must be an integer")
    if max_batch_size <= 0:
        raise ValueError("max_batch_size must be positive")

    contract = {
        "application_columns": list(APPLICATION_COLUMNS),
        "approval_cutoff": cutoff,
        "categorical_levels": _extract_categorical_levels(model),
        "contract_version": SCORING_CONTRACT_VERSION,
        "derived_features": list(DERIVED_FEATURES),
        "explanation_method": EXPLANATION_METHOD,
        "max_batch_size": max_batch_size,
        "model_version": version,
        "numeric_bounds": _numeric_bounds_contract(),
        "policy_decision": decision,
        "risk_band_edges": list(RISK_BAND_EDGES),
        "selected_model_name": selected_model_name,
    }
    manifest = {
        **contract,
        "artifact_filename": artifact.name,
        "artifact_sha256": _sha256_file(artifact),
        "contract_sha256": _sha256_payload(contract),
    }
    destination = (
        Path(output_path)
        if output_path is not None
        else artifact.with_suffix(".manifest.json")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return destination


def load_scoring_service(
    artifact_path: str | Path,
    manifest_path: str | Path,
) -> PDScoringService:
    artifact = Path(artifact_path)
    manifest_data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    manifest = _parse_manifest(manifest_data)
    return _load_verified_service(artifact, manifest)


def load_scoring_service_from_manifest(
    manifest_path: str | Path,
) -> PDScoringService:
    """Load the sibling artifact named by a verified deployment manifest."""
    manifest_file = Path(manifest_path)
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest = _parse_manifest(manifest_data)
    artifact = manifest_file.parent / manifest.artifact_filename
    return _load_verified_service(artifact, manifest)


def _load_verified_service(
    artifact: Path,
    manifest: DeploymentManifest,
) -> PDScoringService:
    if artifact.name != manifest.artifact_filename:
        raise ValueError("Model artifact filename does not match deployment manifest")
    if _sha256_file(artifact) != manifest.artifact_sha256:
        raise ValueError("Model artifact SHA-256 does not match deployment manifest")
    model = joblib.load(artifact)
    if getattr(model, "selected_model_name", None) != manifest.selected_model_name:
        raise ValueError("Loaded model identity does not match deployment manifest")
    return PDScoringService(model=model, manifest=manifest)


def _parse_manifest(data: dict[str, Any]) -> DeploymentManifest:
    if not isinstance(data, dict):
        raise TypeError("Deployment manifest must be a JSON object")
    contract_keys = {
        "application_columns",
        "approval_cutoff",
        "categorical_levels",
        "contract_version",
        "derived_features",
        "explanation_method",
        "max_batch_size",
        "model_version",
        "numeric_bounds",
        "policy_decision",
        "risk_band_edges",
        "selected_model_name",
    }
    required = contract_keys | {
        "artifact_filename",
        "artifact_sha256",
        "contract_sha256",
    }
    missing = required - set(data)
    if missing:
        raise ValueError("Deployment manifest missing fields: " + ", ".join(sorted(missing)))
    contract = {key: data[key] for key in contract_keys}
    if _sha256_payload(contract) != data["contract_sha256"]:
        raise ValueError("Deployment contract SHA-256 does not match manifest contents")
    if data["contract_version"] != SCORING_CONTRACT_VERSION:
        raise ValueError("Unsupported scoring contract version")
    if tuple(data["application_columns"]) != APPLICATION_COLUMNS:
        raise ValueError("Deployment application columns do not match service contract")
    if tuple(data["derived_features"]) != DERIVED_FEATURES:
        raise ValueError("Deployment derived features do not match service contract")
    numeric_bounds = _numeric_bounds_contract()
    if data["numeric_bounds"] != numeric_bounds:
        raise ValueError("Deployment numeric bounds do not match service contract")
    if tuple(data["risk_band_edges"]) != RISK_BAND_EDGES:
        raise ValueError("Deployment risk bands do not match service contract")
    if data["explanation_method"] != EXPLANATION_METHOD:
        raise ValueError("Deployment explanation method does not match service contract")
    categorical_levels = _parse_categorical_levels(data["categorical_levels"])
    return DeploymentManifest(
        contract_version=str(data["contract_version"]),
        model_version=_nonblank(data["model_version"], "model_version"),
        selected_model_name=_nonblank(
            data["selected_model_name"], "selected_model_name"
        ),
        artifact_filename=_safe_artifact_filename(data["artifact_filename"]),
        artifact_sha256=_sha256_value(data["artifact_sha256"], "artifact_sha256"),
        contract_sha256=_sha256_value(data["contract_sha256"], "contract_sha256"),
        approval_cutoff=_probability(data["approval_cutoff"], "approval_cutoff"),
        policy_decision=_policy_decision(data["policy_decision"]),
        max_batch_size=_positive_integer(data["max_batch_size"], "max_batch_size"),
        application_columns=tuple(data["application_columns"]),
        derived_features=tuple(data["derived_features"]),
        categorical_levels=categorical_levels,
        numeric_bounds=numeric_bounds,
        risk_band_edges=RISK_BAND_EDGES,
        explanation_method=EXPLANATION_METHOD,
    )


def _validate_applications(
    applications: pd.DataFrame,
    manifest: DeploymentManifest,
) -> pd.DataFrame:
    if not isinstance(applications, pd.DataFrame):
        raise TypeError("applications must be a pandas DataFrame")
    missing = set(manifest.application_columns) - set(applications.columns)
    extra = set(applications.columns) - set(manifest.application_columns)
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        if extra:
            details.append("unexpected: " + ", ".join(sorted(extra)))
        raise ValueError("Application schema mismatch (" + "; ".join(details) + ")")
    if applications.empty:
        raise ValueError("Scoring batch must contain at least one application")
    if len(applications) > manifest.max_batch_size:
        raise ValueError(
            f"Scoring batch exceeds max_batch_size={manifest.max_batch_size}"
        )
    normalized = applications.loc[:, manifest.application_columns].copy()
    normalized["application_id"] = normalized["application_id"].astype("string").str.strip()
    if normalized["application_id"].isna().any() or normalized[
        "application_id"
    ].eq("").any():
        raise ValueError("application_id must be non-empty")
    if normalized["application_id"].duplicated().any():
        raise ValueError("application_id must be unique within a scoring batch")
    _validate_numeric_features(normalized)
    for column in APPLICATION_CATEGORICAL_FEATURES:
        values = normalized[column].astype("string").str.strip()
        if values.isna().any() or values.eq("").any():
            raise ValueError(f"{column} must contain non-empty values")
        normalized[column] = values
    return normalized


def _validate_numeric_features(frame: pd.DataFrame) -> None:
    for column in APPLICATION_NUMERIC_FEATURES:
        original = frame[column]
        converted = pd.to_numeric(original, errors="coerce")
        invalid = converted.isna() & original.notna()
        if invalid.any():
            raise ValueError(f"{column} must contain numeric values or null")
        finite = converted.dropna().to_numpy(dtype=float)
        if not np.isfinite(finite).all():
            raise ValueError(f"{column} must contain finite values")
        lower, upper, lower_inclusive = NUMERIC_BOUNDS[column]
        below = converted.lt(lower) if lower_inclusive else converted.le(lower)
        if below.any() or (upper is not None and converted.gt(upper).any()):
            lower_word = "at least" if lower_inclusive else "greater than"
            upper_text = "" if upper is None else f" and at most {upper:g}"
            raise ValueError(
                f"{column} must be {lower_word} {lower:g}{upper_text} when present"
            )
        if column == "delinquencies_2y" and not np.equal(
            finite,
            np.floor(finite),
        ).all():
            raise ValueError("delinquencies_2y must contain whole numbers")
        frame[column] = converted


def _data_quality_summary(
    frame: pd.DataFrame,
    manifest: DeploymentManifest,
) -> pd.DataFrame:
    rows = []
    for feature in (*APPLICATION_NUMERIC_FEATURES, *APPLICATION_CATEGORICAL_FEATURES):
        missing_count = int(frame[feature].isna().sum())
        unseen_count = 0
        if feature in APPLICATION_CATEGORICAL_FEATURES:
            known = set(manifest.categorical_levels[feature])
            unseen_count = int((~frame[feature].isin(known) & frame[feature].notna()).sum())
        rows.append(
            {
                "feature": feature,
                "feature_type": (
                    "categorical"
                    if feature in APPLICATION_CATEGORICAL_FEATURES
                    else "numeric"
                ),
                "records": len(frame),
                "missing_count": missing_count,
                "missing_rate": missing_count / len(frame),
                "unseen_category_count": unseen_count,
                "unseen_category_rate": unseen_count / len(frame),
            }
        )
    return pd.DataFrame(rows)


def _extract_categorical_levels(model: Any) -> dict[str, list[str]]:
    try:
        encoder = model.base_estimator.named_steps["preprocessor"].named_transformers_[
            "cat"
        ].named_steps["onehot"]
        categories = encoder.categories_
    except (AttributeError, KeyError) as exc:
        raise ValueError(
            "Model does not expose fitted categorical preprocessing metadata"
        ) from exc
    if len(categories) != len(APPLICATION_CATEGORICAL_FEATURES):
        raise ValueError("Model categorical metadata does not match scoring features")
    return {
        feature: [str(value) for value in levels]
        for feature, levels in zip(
            APPLICATION_CATEGORICAL_FEATURES,
            categories,
            strict=True,
        )
    }


def _parse_categorical_levels(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict) or set(value) != set(
        APPLICATION_CATEGORICAL_FEATURES
    ):
        raise ValueError("categorical_levels must cover every categorical feature")
    parsed = {}
    for feature in APPLICATION_CATEGORICAL_FEATURES:
        levels = value[feature]
        if not isinstance(levels, list) or not levels:
            raise ValueError(f"categorical_levels.{feature} must be a non-empty list")
        normalized = tuple(_nonblank(level, f"categorical_levels.{feature}") for level in levels)
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"categorical_levels.{feature} must be unique")
        parsed[feature] = normalized
    return parsed


def _risk_bands(probabilities: np.ndarray) -> np.ndarray:
    return np.select(
        [
            probabilities <= RISK_BAND_EDGES[0],
            probabilities <= RISK_BAND_EDGES[1],
            probabilities <= RISK_BAND_EDGES[2],
        ],
        ["low", "moderate", "high"],
        default="very_high",
    )


def _input_risk_flags(row: pd.Series) -> str:
    candidates = (
        ("recent_delinquency", row["delinquencies_2y"] > 0),
        ("high_credit_utilisation", row["credit_utilisation"] >= 0.75),
        ("high_debt_to_income", row["debt_to_income"] >= 0.40),
        ("high_loan_to_income", row["loan_to_income"] >= 0.50),
        ("high_interest_rate", row["interest_rate"] >= 0.20),
        (
            "short_employment_history",
            pd.notna(row["employment_length"])
            and row["employment_length"] <= 1,
        ),
    )
    flags = [name for name, triggered in candidates if bool(triggered)]
    return "|".join(flags[:3]) if flags else "none"


def _utc_isoformat(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("scored_at must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _nonblank(value: object, label: str) -> str:
    converted = str(value).strip()
    if not converted:
        raise ValueError(f"{label} must not be blank")
    return converted


def _policy_decision(value: object) -> str:
    decision = _nonblank(value, "policy_decision")
    if decision not in ALLOWED_POLICY_DECISIONS:
        allowed = ", ".join(sorted(ALLOWED_POLICY_DECISIONS))
        raise ValueError(f"policy_decision must be one of: {allowed}")
    return decision


def _safe_artifact_filename(value: object) -> str:
    filename = _nonblank(value, "artifact_filename")
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("artifact_filename must be a file name without directories")
    return filename


def _numeric_bounds_contract() -> dict[str, dict[str, float | bool | None]]:
    return {
        feature: {
            "minimum": minimum,
            "maximum": maximum,
            "minimum_inclusive": minimum_inclusive,
        }
        for feature, (minimum, maximum, minimum_inclusive) in NUMERIC_BOUNDS.items()
    }


def _probability(value: object, label: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite probability") from exc
    if not math.isfinite(converted) or not 0 < converted < 1:
        raise ValueError(f"{label} must be greater than 0 and less than 1")
    return converted


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _sha256_value(value: object, label: str) -> str:
    converted = str(value)
    if len(converted) != 64 or any(character not in "0123456789abcdef" for character in converted):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return converted


def _sha256_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
