import hashlib
import json

import pandas as pd
import pytest

from credit_risk_pd.publication import (
    SAFE_AGGREGATE_REPORTS,
    publish_public_lendingclub_run,
)


def _write_source_reports(report_dir) -> None:
    report_dir.mkdir()
    for filename in SAFE_AGGREGATE_REPORTS:
        path = report_dir / filename
        if path.suffix == ".csv":
            pd.DataFrame({"metric": [filename], "value": [1.0]}).to_csv(path, index=False)
        else:
            path.write_text("# Aggregate model report\n", encoding="utf-8")


def test_publish_public_run_copies_only_aggregate_evidence_and_writes_lineage(tmp_path):
    report_dir = tmp_path / "source_reports"
    _write_source_reports(report_dir)
    (report_dir / "oot_predictions.csv").write_text(
        "customer_id,recalibrated_pd\nPRIVATE-1,0.2\n",
        encoding="utf-8",
    )
    raw_input = tmp_path / "accepted.csv.gz"
    raw_input.write_bytes(b"public dataset fixture")
    audit_path = tmp_path / "ingestion_audit.csv"
    pd.DataFrame(
        [
            {
                "input_path": str(raw_input),
                "input_rows": 100,
                "output_rows": 80,
                "observation_date_min": "2007-06-01",
                "observation_date_max": "2018-12-01",
            }
        ]
    ).to_csv(audit_path, index=False)

    output_dir = tmp_path / "published"
    output_dir.mkdir()
    (output_dir / "oot_predictions.csv").write_text(
        "customer_id,recalibrated_pd\nSTALE-PRIVATE-1,0.2\n",
        encoding="utf-8",
    )
    publication = publish_public_lendingclub_run(
        report_dir,
        audit_path,
        raw_input,
        output_dir,
    )

    published_names = {path.name for path in publication.published_paths}
    assert published_names == {
        *SAFE_AGGREGATE_REPORTS,
        "ingestion_audit.csv",
        "data_lineage.json",
    }
    assert not (publication.output_dir / "oot_predictions.csv").exists()
    published_audit = pd.read_csv(publication.output_dir / "ingestion_audit.csv")
    assert published_audit.loc[0, "input_path"] == "data/raw/accepted.csv.gz"
    manifest = json.loads(publication.manifest_path.read_text(encoding="utf-8"))
    assert manifest["raw_file_sha256"] == hashlib.sha256(raw_input.read_bytes()).hexdigest()
    assert manifest["excluded_borrower_level_reports"] == ["oot_predictions.csv"]
    assert publication.manifest_path.read_bytes().endswith(b"\n")


def test_publish_public_run_rejects_report_with_customer_identifier(tmp_path):
    report_dir = tmp_path / "source_reports"
    _write_source_reports(report_dir)
    pd.DataFrame({"customer_id": ["PRIVATE-1"]}).to_csv(
        report_dir / "model_metrics.csv",
        index=False,
    )
    raw_input = tmp_path / "accepted.csv.gz"
    raw_input.write_bytes(b"fixture")
    audit_path = tmp_path / "audit.csv"
    pd.DataFrame(
        [
            {
                "input_path": str(raw_input),
                "input_rows": 1,
                "output_rows": 1,
                "observation_date_min": "2018-01-01",
                "observation_date_max": "2018-01-01",
            }
        ]
    ).to_csv(audit_path, index=False)

    with pytest.raises(ValueError, match="cannot include customer_id"):
        publish_public_lendingclub_run(
            report_dir,
            audit_path,
            raw_input,
            tmp_path / "published",
        )
