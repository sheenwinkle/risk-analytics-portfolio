from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from credit_risk_pd.serving import PDScoringService


class CreditApplicationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    application_id: str = Field(min_length=1, max_length=128)
    age: int | float | None = Field(ge=18, le=120)
    annual_income: int | float | None = Field(ge=0)
    debt_to_income: int | float | None = Field(ge=-0.01, le=10)
    credit_utilisation: int | float | None = Field(ge=0, le=5)
    delinquencies_2y: int | None = Field(ge=0)
    loan_amount: int | float | None = Field(gt=0)
    interest_rate: int | float | None = Field(ge=0, le=1)
    employment_length: int | float | None = Field(ge=0, le=80)
    home_ownership: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=120)

    @field_validator("application_id", "home_ownership", "purpose")
    @classmethod
    def strip_nonblank_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class BatchScoringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str = Field(min_length=1, max_length=128)
    applications: list[CreditApplicationPayload] = Field(min_length=1)

    @field_validator("request_id")
    @classmethod
    def strip_request_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class BatchMetadataPayload(BaseModel):
    request_id: str
    scored_at_utc: str
    contract_version: str
    model_version: str
    selected_model_name: str
    contract_sha256: str
    artifact_sha256: str
    artifact_integrity_verified: bool
    records_scored: int
    batches_scored: int
    approval_cutoff: float
    within_cutoff_count: int
    within_cutoff_rate: float
    mean_recalibrated_pd: float
    explanation_method: str
    missing_input_values: int
    unseen_category_values: int


class ApplicationScorePayload(BaseModel):
    application_id: str
    raw_pd: float
    recalibrated_pd: float
    risk_band: str
    policy_outcome: str
    input_risk_flags: str


class DataQualityPayload(BaseModel):
    feature: str
    feature_type: str
    records: int
    missing_count: int
    missing_rate: float
    unseen_category_count: int
    unseen_category_rate: float


class BatchScoringResponse(BaseModel):
    batch: BatchMetadataPayload
    scores: list[ApplicationScorePayload]
    data_quality: list[DataQualityPayload]


class HealthResponse(BaseModel):
    status: str
    contract_version: str
    model_version: str
    selected_model_name: str
    artifact_sha256: str
    artifact_integrity_verified: bool


def create_scoring_app(service: PDScoringService) -> FastAPI:
    """Create an injected scoring API around one verified in-memory model."""
    app = FastAPI(
        title="Credit Risk PD Scoring API",
        version=service.manifest.contract_version,
        description=(
            "Portfolio reference API for governed batch PD scoring. Policy flags are "
            "not local model attributions or adverse-action reasons."
        ),
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        manifest = service.manifest
        return HealthResponse(
            status="ready",
            contract_version=manifest.contract_version,
            model_version=manifest.model_version,
            selected_model_name=manifest.selected_model_name,
            artifact_sha256=manifest.artifact_sha256,
            artifact_integrity_verified=True,
        )

    @app.post("/v1/pd/score", response_model=BatchScoringResponse)
    def score(request: BatchScoringRequest) -> BatchScoringResponse:
        applications = pd.DataFrame(
            [application.model_dump() for application in request.applications]
        )
        try:
            result = service.score_batch(
                applications,
                request_id=request.request_id,
                scored_at=datetime.now(UTC),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return BatchScoringResponse(
            batch=BatchMetadataPayload.model_validate(result.audit.iloc[0].to_dict()),
            scores=[
                ApplicationScorePayload.model_validate(row)
                for row in result.scores.to_dict(orient="records")
            ],
            data_quality=[
                DataQualityPayload.model_validate(row)
                for row in result.data_quality.to_dict(orient="records")
            ],
        )

    return app
