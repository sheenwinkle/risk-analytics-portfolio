import pandas as pd
import pytest

from credit_risk_pd.config import ModelConfig
from credit_risk_pd.data import CANONICAL_COLUMNS
from credit_risk_pd.lendingclub import (
    prepare_lendingclub_data,
    transform_lendingclub_accepted_loans,
)
from credit_risk_pd.pipeline import run_pd_modelling_workflow


def _raw_lendingclub_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        "id": "1001",
        "issue_d": "Jan-2017",
        "annual_inc": 120_000,
        "dti": "18.5",
        "revol_util": "45.5%",
        "delinq_2yrs": 1,
        "loan_amnt": 15_000,
        "int_rate": "13.99%",
        "emp_length": "10+ years",
        "home_ownership": "MORTGAGE",
        "purpose": "debt_consolidation",
        "loan_status": "Fully Paid",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_transform_maps_lendingclub_rows_to_canonical_schema():
    raw = _raw_lendingclub_rows(
        [
            {"id": "A", "loan_status": "Fully Paid", "emp_length": "10+ years"},
            {"id": "B", "loan_status": "Charged Off", "emp_length": "< 1 year"},
            {"id": "C", "loan_status": "Current"},
        ]
    )

    prepared, audit = transform_lendingclub_accepted_loans(raw, input_path="accepted.csv.gz")

    assert list(prepared.columns) == CANONICAL_COLUMNS
    assert prepared["customer_id"].tolist() == ["A", "B"]
    assert prepared["default"].tolist() == [0, 1]
    assert prepared["age"].isna().all()
    assert prepared["debt_to_income"].tolist() == pytest.approx([0.185, 0.185])
    assert prepared["credit_utilisation"].tolist() == pytest.approx([0.455, 0.455])
    assert prepared["interest_rate"].tolist() == pytest.approx([0.1399, 0.1399])
    assert prepared["employment_length"].tolist() == [10, 0]
    assert prepared["home_ownership"].tolist() == ["mortgage", "mortgage"]
    assert audit["excluded_unresolved_status_rows"] == 1


def test_transform_maps_legacy_policy_statuses_and_filters_unresolved_statuses():
    raw = _raw_lendingclub_rows(
        [
            {
                "id": "A",
                "loan_status": " Does not meet the credit policy. Status: Fully Paid ",
            },
            {"id": "B", "loan_status": "Does not meet the credit policy. Status:Charged Off"},
            {"id": "C", "loan_status": "Default"},
            {"id": "D", "loan_status": "Issued"},
            {"id": "E", "loan_status": "In Grace Period"},
            {"id": "F", "loan_status": "Late (31-120 days)"},
        ]
    )

    prepared, audit = transform_lendingclub_accepted_loans(raw)

    assert prepared["customer_id"].tolist() == ["A", "B", "C"]
    assert prepared["default"].tolist() == [0, 1, 1]
    assert audit["excluded_unresolved_status_rows"] == 3


def test_transform_reports_audit_counts_for_invalid_and_duplicate_rows():
    raw = _raw_lendingclub_rows(
        [
            {"id": "A", "loan_status": "Fully Paid", "issue_d": "Jan-2017"},
            {"id": "B", "loan_status": "Current", "issue_d": "Jan-2017"},
            {"id": "", "loan_status": "Charged Off", "issue_d": "Jan-2017"},
            {"id": "C", "loan_status": "Default", "issue_d": "not a date"},
            {"id": "A", "loan_status": "Charged Off", "issue_d": "Feb-2017"},
        ]
    )

    prepared, audit = transform_lendingclub_accepted_loans(raw)

    assert prepared["customer_id"].tolist() == ["A"]
    assert audit["input_rows"] == 5
    assert audit["excluded_rows"] == 4
    assert audit["excluded_unresolved_status_rows"] == 1
    assert audit["invalid_key_or_date_rows"] == 2
    assert audit["duplicate_rows"] == 1
    assert audit["output_rows"] == 1
    assert audit["non_default_count"] == 1
    assert audit["default_count"] == 0
    assert audit["default_rate"] == 0.0
    assert audit["observation_date_min"] == "2017-01-01"
    assert audit["observation_date_max"] == "2017-01-01"


def test_transform_validates_missing_raw_columns_clearly():
    raw = _raw_lendingclub_rows([{}]).drop(columns=["loan_status", "issue_d"])

    with pytest.raises(ValueError, match="issue_d, loan_status"):
        transform_lendingclub_accepted_loans(raw)


def test_prepare_lendingclub_data_reads_gzipped_csv_and_writes_audit(tmp_path):
    raw_path = tmp_path / "accepted_2007_to_2018Q4.csv.gz"
    output_path = tmp_path / "processed" / "lendingclub_pd.csv"
    audit_path = tmp_path / "processed" / "lendingclub_audit.csv"
    raw = _raw_lendingclub_rows(
        [
            {"id": "000123", "loan_status": "Fully Paid"},
            {"id": "B", "loan_status": "Charged Off"},
        ]
    )
    raw.to_csv(raw_path, index=False, compression="gzip")

    result = prepare_lendingclub_data(raw_path, output_path, audit_path, max_rows=1)

    prepared = pd.read_csv(result.output_path, dtype={"customer_id": "string"})
    audit = pd.read_csv(result.audit_path)
    assert prepared["customer_id"].tolist() == ["000123"]
    assert audit.loc[0, "input_rows"] == 1
    assert audit.loc[0, "output_rows"] == 1


def test_prepare_lendingclub_data_rejects_non_positive_row_limit(tmp_path):
    raw_path = tmp_path / "accepted.csv"
    _raw_lendingclub_rows([{}]).to_csv(raw_path, index=False)

    with pytest.raises(ValueError, match="max_rows must be at least 1"):
        prepare_lendingclub_data(
            raw_path,
            tmp_path / "prepared.csv",
            tmp_path / "audit.csv",
            max_rows=0,
        )


def test_prepared_lendingclub_data_runs_end_to_end_pd_workflow(tmp_path):
    rows = []
    for index in range(240):
        if index >= 160:
            issue_d = "Jan-2017"
        elif index >= 120:
            issue_d = "Jul-2016"
        else:
            issue_d = "Jan-2016"

        rows.append(
            {
                "id": f"LC{index:06d}",
                "issue_d": issue_d,
                "annual_inc": 50_000 + (index % 20) * 2_500,
                "dti": 12 + index % 25,
                "revol_util": f"{20 + index % 60}%",
                "delinq_2yrs": index % 3,
                "loan_amnt": 5_000 + (index % 15) * 1_000,
                "int_rate": f"{8 + index % 12}.49%",
                "emp_length": f"{1 + index % 10} years",
                "home_ownership": ["RENT", "MORTGAGE", "OWN"][index % 3],
                "purpose": ["car", "credit_card", "debt_consolidation"][index % 3],
                "loan_status": "Charged Off" if index % 4 == 0 else "Fully Paid",
            }
        )

    raw_path = tmp_path / "accepted.csv.gz"
    prepared_path = tmp_path / "processed" / "lendingclub_pd.csv"
    audit_path = tmp_path / "processed" / "ingestion_audit.csv"
    _raw_lendingclub_rows(rows).to_csv(raw_path, index=False, compression="gzip")
    prepare_lendingclub_data(raw_path, prepared_path, audit_path)

    outputs = run_pd_modelling_workflow(
        input_path=prepared_path,
        output_dir=tmp_path / "reports",
        model_dir=tmp_path / "models",
        config=ModelConfig(oot_cutoff_date="2017-01-01"),
    )

    assert all(path.exists() for path in outputs.values())
    metrics = pd.read_csv(outputs["metrics"])
    assert set(metrics["model"]) == {"logistic_regression", "random_forest"}
    psi = pd.read_csv(outputs["psi"])
    age_row = psi.loc[psi["feature"].eq("age")].iloc[0]
    assert pd.isna(age_row["psi"])
    assert age_row["status"] == "not_available"
    report = outputs["report"].read_text(encoding="utf-8")
    assert "| age | N/A | not_available |" in report
