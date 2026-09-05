import json

import pandas as pd
import pytest

from model_validation.publication import PUBLIC_VALIDATION_FILES, publish_public_validation


def _write_validation_reports(report_dir) -> None:
    report_dir.mkdir()
    for filename in PUBLIC_VALIDATION_FILES:
        path = report_dir / filename
        if path.suffix == ".csv":
            pd.DataFrame({"metric": [filename], "value": [1.0]}).to_csv(path, index=False)
        else:
            path.write_text("# Aggregate validation report\n", encoding="utf-8")


def test_publish_public_validation_copies_safe_reports_and_model_lineage(tmp_path):
    reports = tmp_path / "reports"
    _write_validation_reports(reports)
    project1_lineage = tmp_path / "project1_lineage.json"
    project1_lineage.write_text(
        json.dumps({"raw_file": "accepted.csv.gz", "raw_file_sha256": "abc123"}),
        encoding="utf-8",
    )

    output_dir = tmp_path / "published"
    output_dir.mkdir()
    (output_dir / "oot_predictions.csv").write_text(
        "customer_id,recalibrated_pd\nSTALE-PRIVATE-1,0.2\n",
        encoding="utf-8",
    )
    publication = publish_public_validation(
        reports,
        project1_lineage,
        output_dir,
    )

    names = {path.name for path in publication.published_paths}
    assert names == {*PUBLIC_VALIDATION_FILES, "data_lineage.json"}
    lineage = json.loads(
        (publication.output_dir / "data_lineage.json").read_text(encoding="utf-8")
    )
    assert lineage["source_raw_file_sha256"] == "abc123"
    assert lineage["excluded_borrower_level_input"] == "oot_predictions.csv"
    assert not (publication.output_dir / "oot_predictions.csv").exists()


def test_publish_public_validation_rejects_customer_level_csv(tmp_path):
    reports = tmp_path / "reports"
    _write_validation_reports(reports)
    pd.DataFrame({"customer_id": ["private"]}).to_csv(
        reports / "model_metrics.csv",
        index=False,
    )
    lineage = tmp_path / "lineage.json"
    lineage.write_text(
        json.dumps({"raw_file": "accepted.csv.gz", "raw_file_sha256": "abc123"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot include customer_id"):
        publish_public_validation(reports, lineage, tmp_path / "published")
