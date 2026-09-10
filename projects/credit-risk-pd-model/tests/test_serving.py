from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from credit_risk_pd.calibration import LogisticPDRecalibrator, RecalibratedPDModel
from credit_risk_pd.data import generate_synthetic_credit_data
from credit_risk_pd.features import add_credit_features, split_features_target
from credit_risk_pd.model import build_logistic_pd_model
from credit_risk_pd.serving import (
    PDScoringService,
    load_scoring_service,
    load_scoring_service_from_manifest,
    write_deployment_manifest,
)


def test_verified_model_artifact_scores_a_batch_with_frozen_lineage(
    tmp_path: Path,
) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
        max_batch_size=100,
    )
    service = load_scoring_service(artifact_path, manifest_path)
    applications = _scoring_applications().iloc[:3].copy()

    result = service.score_batch(
        applications,
        request_id="REQ-0001",
        scored_at=datetime(2026, 9, 9, 8, 30, tzinfo=UTC),
    )

    expected_features = add_credit_features(
        applications.drop(columns="application_id")
    )
    expected_pd = model.predict_proba(expected_features)[:, 1]
    np.testing.assert_allclose(result.scores["recalibrated_pd"], expected_pd)
    assert result.scores["application_id"].tolist() == applications[
        "application_id"
    ].tolist()
    assert result.audit.loc[0, "model_version"] == "synthetic-pd-v1"
    assert result.audit.loc[0, "artifact_integrity_verified"]
    assert result.audit.loc[0, "records_scored"] == 3


def test_scoring_rejects_values_outside_the_canonical_credit_contract(
    tmp_path: Path,
) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    service = load_scoring_service(artifact_path, manifest_path)
    applications = _scoring_applications().iloc[:1].copy()
    applications.loc[:, "annual_income"] = -1.0

    with pytest.raises(ValueError, match="annual_income"):
        service.score_batch(
            applications,
            request_id="REQ-INVALID",
            scored_at=datetime(2026, 9, 9, 8, 30, tzinfo=UTC),
        )


def test_scoring_accepts_fitted_public_data_boundary_values(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    service = load_scoring_service(artifact_path, manifest_path)
    applications = _scoring_applications().iloc[:1].copy()
    applications.loc[:, "annual_income"] = 0.0
    applications.loc[:, "debt_to_income"] = -0.01

    result = service.score_batch(
        applications,
        request_id="REQ-PUBLIC-BOUNDARY",
        scored_at=datetime(2026, 9, 9, 8, 30, tzinfo=UTC),
    )

    assert len(result.scores) == 1
    assert "high_loan_to_income" in result.scores.loc[0, "input_risk_flags"]


def test_scoring_returns_governed_risk_bands_and_input_flags(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    service = load_scoring_service(artifact_path, manifest_path)
    applications = _scoring_applications().iloc[:1].copy()
    applications.loc[:, "debt_to_income"] = 0.65
    applications.loc[:, "credit_utilisation"] = 0.90
    applications.loc[:, "delinquencies_2y"] = 2

    result = service.score_batch(
        applications,
        request_id="REQ-RISK-FLAGS",
        scored_at=datetime(2026, 9, 9, 8, 30, tzinfo=UTC),
    )

    score = result.scores.iloc[0]
    assert score["risk_band"] in {"low", "moderate", "high", "very_high"}
    assert score["input_risk_flags"] == (
        "recent_delinquency|high_credit_utilisation|high_debt_to_income"
    )
    assert result.audit.loc[0, "explanation_method"] == (
        "policy_input_flags_not_model_attribution"
    )


def test_scoring_audits_missing_values_and_unseen_categories(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    service = load_scoring_service(artifact_path, manifest_path)
    applications = _scoring_applications().iloc[:2].copy()
    applications.loc[applications.index[0], "age"] = np.nan
    applications.loc[applications.index[1], "purpose"] = "new_product_purpose"

    result = service.score_batch(
        applications,
        request_id="REQ-DATA-QUALITY",
        scored_at=datetime(2026, 9, 9, 8, 30, tzinfo=UTC),
    )

    quality = result.data_quality.set_index("feature")
    assert quality.loc["age", "missing_count"] == 1
    assert quality.loc["purpose", "unseen_category_count"] == 1
    assert result.audit.loc[0, "missing_input_values"] == 1
    assert result.audit.loc[0, "unseen_category_values"] == 1
    assert len(result.scores) == 2


def test_scoring_audit_normalises_request_time_to_utc(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    service = load_scoring_service(artifact_path, manifest_path)

    result = service.score_batch(
        _scoring_applications().iloc[:1],
        request_id="REQ-TIME",
        scored_at=datetime(
            2026,
            9,
            9,
            8,
            30,
            tzinfo=timezone(timedelta(hours=10)),
        ),
    )

    assert result.audit.loc[0, "scored_at_utc"] == "2026-09-08T22:30:00+00:00"


def test_http_api_scores_a_strict_batch_contract(tmp_path: Path) -> None:
    from credit_risk_pd.api import create_scoring_app

    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    service = load_scoring_service(artifact_path, manifest_path)
    applications = _scoring_applications().iloc[:2]
    records = applications.to_dict(orient="records")
    records[0]["debt_to_income"] = None
    app = create_scoring_app(service)
    response = _post_json(
        app,
        "/v1/pd/score",
        {
            "request_id": "REQ-HTTP-0001",
            "applications": records,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["model_version"] == "synthetic-pd-v1"
    assert payload["batch"]["records_scored"] == 2
    assert payload["batch"]["missing_input_values"] == 1
    assert len(payload["scores"]) == 2
    assert payload["scores"][0]["application_id"] == applications.iloc[0][
        "application_id"
    ]


def test_http_api_exposes_verified_health_and_enforces_manifest_batch_limit(
    tmp_path: Path,
) -> None:
    from credit_risk_pd.api import create_scoring_app

    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
        max_batch_size=1,
    )
    app = create_scoring_app(load_scoring_service_from_manifest(manifest_path))

    health = _get(app, "/health")
    assert health.status_code == 200
    assert health.json()["artifact_integrity_verified"] is True
    response = _post_json(
        app,
        "/v1/pd/score",
        {
            "request_id": "REQ-TOO-LARGE",
            "applications": _scoring_applications().iloc[:2].to_dict(orient="records"),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Scoring batch exceeds max_batch_size=1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("annual_income", "85000"),
        ("actual_default", 0),
    ],
)
def test_http_api_rejects_coercion_and_unknown_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    from credit_risk_pd.api import create_scoring_app

    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    record = _scoring_applications().iloc[0].to_dict()
    record[field] = value

    response = _post_json(
        create_scoring_app(load_scoring_service(artifact_path, manifest_path)),
        "/v1/pd/score",
        {"request_id": "REQ-STRICT", "applications": [record]},
    )

    assert response.status_code == 422
    locations = [error["loc"] for error in response.json()["detail"]]
    assert any(
        location[:4] == ["body", "applications", 0, field]
        for location in locations
    )


def test_service_refuses_a_model_artifact_changed_after_registration(
    tmp_path: Path,
) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    artifact_path.write_bytes(artifact_path.read_bytes() + b"changed")

    with pytest.raises(ValueError, match="artifact SHA-256"):
        load_scoring_service(artifact_path, manifest_path)


def test_service_refuses_probability_output_outside_zero_and_one(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    verified = load_scoring_service(artifact_path, manifest_path)

    class InvalidProbabilityModel:
        def predict_raw_proba(self, features):
            return np.full(len(features), -0.01)

        def predict_proba(self, features):
            return np.column_stack(
                [np.full(len(features), -0.01), np.full(len(features), 1.01)]
            )

    service = PDScoringService(
        model=InvalidProbabilityModel(),
        manifest=verified.manifest,
    )

    with pytest.raises(ValueError, match="invalid probability output"):
        service.score_batch(
            _scoring_applications().iloc[:1],
            request_id="REQ-BAD-PD",
            scored_at=datetime(2026, 9, 9, 8, 30, tzinfo=UTC),
        )


def test_service_refuses_a_manifest_changed_after_registration(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)
    manifest_path = write_deployment_manifest(
        artifact_path,
        model,
        model_version="synthetic-pd-v1",
        approval_cutoff=0.15,
        policy_decision="retain_incumbent",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["approval_cutoff"] = 0.99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="contract SHA-256"):
        load_scoring_service_from_manifest(manifest_path)


def test_deployment_manifest_rejects_unknown_policy_decisions(tmp_path: Path) -> None:
    model, artifact_path = _write_fitted_model(tmp_path)

    with pytest.raises(ValueError, match="policy_decision"):
        write_deployment_manifest(
            artifact_path,
            model,
            model_version="synthetic-pd-v1",
            approval_cutoff=0.15,
            policy_decision="manual_override",
        )


def _write_fitted_model(tmp_path: Path) -> tuple[RecalibratedPDModel, Path]:
    data = generate_synthetic_credit_data(n_rows=1_000, random_state=17)
    development = data.iloc[:700]
    calibration = data.iloc[700:]
    x_development, y_development = split_features_target(development)
    x_calibration, y_calibration = split_features_target(calibration)
    base_model = build_logistic_pd_model().fit(x_development, y_development)
    recalibrator = LogisticPDRecalibrator().fit(
        base_model.predict_proba(x_calibration)[:, 1],
        y_calibration,
    )
    model = RecalibratedPDModel(
        selected_model_name="logistic_regression",
        base_estimator=base_model,
        recalibrator=recalibrator,
    )
    artifact_path = tmp_path / "logistic_regression_recalibrated.joblib"
    joblib.dump(model, artifact_path)
    return model, artifact_path


def _scoring_applications() -> pd.DataFrame:
    data = generate_synthetic_credit_data(n_rows=20, random_state=23)
    return data.rename(columns={"customer_id": "application_id"}).drop(
        columns=["observation_date", "default"]
    )


def _post_json(app: object, path: str, payload: dict[str, object]):
    from httpx2 import ASGITransport, AsyncClient

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(path, json=payload)

    return asyncio.run(request())


def _get(app: object, path: str):
    from httpx2 import ASGITransport, AsyncClient

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(request())
