from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from credit_risk_pd.data import CANONICAL_COLUMNS

RAW_COLUMNS = [
    "id",
    "issue_d",
    "annual_inc",
    "dti",
    "revol_util",
    "delinq_2yrs",
    "loan_amnt",
    "int_rate",
    "emp_length",
    "home_ownership",
    "purpose",
    "loan_status",
]

DEFAULT_CHUNK_SIZE = 100_000
VINTAGE_RESOLUTION_COLUMNS = (
    "vintage_quarter",
    "input_rows",
    "resolved_rows",
    "unresolved_rows",
    "resolution_rate",
    "defaults",
    "non_defaults",
    "resolved_default_rate",
)

NON_DEFAULT_STATUSES = {
    "fully paid",
    "does not meet the credit policy. status:fully paid",
}

DEFAULT_STATUSES = {
    "charged off",
    "default",
    "does not meet the credit policy. status:charged off",
}


@dataclass(frozen=True)
class LendingClubPreparationResult:
    """Paths and audit metrics produced by a LendingClub preparation run."""

    output_path: Path
    audit_path: Path
    audit: dict[str, object]
    vintage_resolution_path: Path | None = None


def prepare_lendingclub_data(
    input_path: str | Path,
    output_path: str | Path,
    audit_path: str | Path,
    *,
    max_rows: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    vintage_resolution_path: str | Path | None = None,
) -> LendingClubPreparationResult:
    """Prepare a user-downloaded LendingClub accepted-loans file for the PD pipeline."""
    if max_rows is not None and max_rows < 1:
        raise ValueError("max_rows must be at least 1 when provided")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    input_path = Path(input_path)
    output_path = Path(output_path)
    audit_path = Path(audit_path)
    vintage_path = (
        Path(vintage_resolution_path) if vintage_resolution_path is not None else None
    )

    header = pd.read_csv(input_path, nrows=0, compression="infer")
    _validate_raw_columns(header.columns)

    chunks = pd.read_csv(
        input_path,
        usecols=RAW_COLUMNS,
        dtype={"id": "string"},
        nrows=max_rows,
        chunksize=chunk_size,
        compression="infer",
        low_memory=False,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    if vintage_path is not None:
        vintage_path.parent.mkdir(parents=True, exist_ok=True)
    output_temp_path = output_path.with_name(f".{output_path.name}.tmp")
    audit_temp_path = audit_path.with_name(f".{audit_path.name}.tmp")
    vintage_temp_path = (
        vintage_path.with_name(f".{vintage_path.name}.tmp")
        if vintage_path is not None
        else None
    )

    seen_customer_ids: set[str] = set()
    input_rows = 0
    unresolved_count = 0
    invalid_key_or_date_count = 0
    duplicate_count = 0
    output_rows = 0
    default_count = 0
    chunks_processed = 0
    observation_date_min: pd.Timestamp | None = None
    observation_date_max: pd.Timestamp | None = None
    vintage_chunks: list[pd.DataFrame] = []

    try:
        output_temp_path.unlink(missing_ok=True)
        audit_temp_path.unlink(missing_ok=True)
        if vintage_temp_path is not None:
            vintage_temp_path.unlink(missing_ok=True)
        wrote_header = False

        for raw_chunk in chunks:
            chunks_processed += 1
            if vintage_path is not None:
                vintage_chunks.append(build_lendingclub_vintage_resolution(raw_chunk))
            prepared_chunk, chunk_audit = transform_lendingclub_accepted_loans(
                raw_chunk,
                input_path=input_path,
            )
            input_rows += int(chunk_audit["input_rows"])
            unresolved_count += int(chunk_audit["excluded_unresolved_status_rows"])
            invalid_key_or_date_count += int(chunk_audit["invalid_key_or_date_rows"])
            duplicate_count += int(chunk_audit["duplicate_rows"])

            cross_chunk_duplicate_mask = prepared_chunk["customer_id"].isin(seen_customer_ids)
            duplicate_count += int(cross_chunk_duplicate_mask.sum())
            prepared_chunk = prepared_chunk.loc[~cross_chunk_duplicate_mask].copy()
            seen_customer_ids.update(prepared_chunk["customer_id"].astype(str).tolist())

            if not prepared_chunk.empty:
                chunk_min = pd.Timestamp(prepared_chunk["observation_date"].min())
                chunk_max = pd.Timestamp(prepared_chunk["observation_date"].max())
                observation_date_min = (
                    chunk_min
                    if observation_date_min is None
                    else min(observation_date_min, chunk_min)
                )
                observation_date_max = (
                    chunk_max
                    if observation_date_max is None
                    else max(observation_date_max, chunk_max)
                )
                output_rows += len(prepared_chunk)
                default_count += int(prepared_chunk["default"].sum())

            prepared_chunk.to_csv(
                output_temp_path,
                mode="a",
                header=not wrote_header,
                index=False,
                lineterminator="\n",
            )
            wrote_header = True

        if not wrote_header:
            pd.DataFrame(columns=CANONICAL_COLUMNS).to_csv(
                output_temp_path,
                index=False,
                lineterminator="\n",
            )

        audit = {
            "input_path": str(input_path),
            "input_rows": input_rows,
            "excluded_rows": input_rows - output_rows,
            "excluded_unresolved_status_rows": unresolved_count,
            "invalid_key_or_date_rows": invalid_key_or_date_count,
            "duplicate_rows": duplicate_count,
            "output_rows": output_rows,
            "non_default_count": output_rows - default_count,
            "default_count": default_count,
            "default_rate": default_count / output_rows if output_rows else 0.0,
            "observation_date_min": _format_audit_date(observation_date_min),
            "observation_date_max": _format_audit_date(observation_date_max),
            "chunks_processed": chunks_processed,
            "chunk_size": chunk_size,
        }
        pd.DataFrame([audit]).to_csv(audit_temp_path, index=False, lineterminator="\n")
        if vintage_temp_path is not None:
            _combine_vintage_resolution(vintage_chunks).to_csv(
                vintage_temp_path,
                index=False,
                lineterminator="\n",
            )
        output_temp_path.replace(output_path)
        audit_temp_path.replace(audit_path)
        if vintage_temp_path is not None and vintage_path is not None:
            vintage_temp_path.replace(vintage_path)
    except Exception:
        output_temp_path.unlink(missing_ok=True)
        audit_temp_path.unlink(missing_ok=True)
        if vintage_temp_path is not None:
            vintage_temp_path.unlink(missing_ok=True)
        raise

    return LendingClubPreparationResult(
        output_path=output_path,
        audit_path=audit_path,
        audit=audit,
        vintage_resolution_path=vintage_path,
    )


def build_lendingclub_vintage_resolution(raw: pd.DataFrame) -> pd.DataFrame:
    """Summarise resolved and unresolved raw loan statuses by issue quarter."""
    _validate_raw_columns(raw.columns)
    issue_date = _parse_issue_date(raw["issue_d"])
    mapped_default = raw["loan_status"].map(_map_default_status)
    working = pd.DataFrame(
        {
            "issue_date": issue_date,
            "resolved": mapped_default.notna(),
            "default": mapped_default.eq(1),
        }
    ).dropna(subset=["issue_date"])
    if working.empty:
        return pd.DataFrame(columns=VINTAGE_RESOLUTION_COLUMNS)

    working["vintage_quarter"] = working["issue_date"].dt.to_period("Q").astype(str)
    counts = (
        working.groupby("vintage_quarter", as_index=False, sort=True)
        .agg(
            input_rows=("resolved", "size"),
            resolved_rows=("resolved", "sum"),
            defaults=("default", "sum"),
        )
    )
    return _finalise_vintage_resolution(counts)


def _combine_vintage_resolution(chunks: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [chunk for chunk in chunks if not chunk.empty]
    if not non_empty:
        return pd.DataFrame(columns=VINTAGE_RESOLUTION_COLUMNS)
    counts = (
        pd.concat(non_empty, ignore_index=True)
        .groupby("vintage_quarter", as_index=False, sort=True)[
            ["input_rows", "resolved_rows", "defaults"]
        ]
        .sum()
    )
    return _finalise_vintage_resolution(counts)


def _finalise_vintage_resolution(counts: pd.DataFrame) -> pd.DataFrame:
    result = counts.copy()
    for column in ("input_rows", "resolved_rows", "defaults"):
        result[column] = result[column].astype(int)
    result["unresolved_rows"] = result["input_rows"] - result["resolved_rows"]
    result["resolution_rate"] = result["resolved_rows"] / result["input_rows"]
    result["non_defaults"] = result["resolved_rows"] - result["defaults"]
    result["resolved_default_rate"] = result["defaults"].div(
        result["resolved_rows"].where(result["resolved_rows"].ne(0))
    )
    return result.loc[:, VINTAGE_RESOLUTION_COLUMNS]


def transform_lendingclub_accepted_loans(
    raw: pd.DataFrame,
    *,
    input_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Transform raw LendingClub accepted-loan rows into the canonical PD schema."""
    _validate_raw_columns(raw.columns)

    working = raw.loc[:, RAW_COLUMNS].copy()
    input_rows = len(working)

    working["default"] = working["loan_status"].map(_map_default_status)
    unresolved_mask = working["default"].isna()
    unresolved_count = int(unresolved_mask.sum())
    working = working.loc[~unresolved_mask].copy()

    working["customer_id"] = working["id"].astype("string").str.strip()
    working.loc[working["customer_id"].isin(["", "<NA>"]), "customer_id"] = pd.NA
    working["observation_date"] = _parse_issue_date(working["issue_d"])
    invalid_key_or_date_mask = working["customer_id"].isna() | working["observation_date"].isna()
    invalid_key_or_date_count = int(invalid_key_or_date_mask.sum())
    working = working.loc[~invalid_key_or_date_mask].copy()

    duplicate_mask = working.duplicated(subset=["customer_id"], keep="first")
    duplicate_count = int(duplicate_mask.sum())
    working = working.loc[~duplicate_mask].copy()

    canonical = pd.DataFrame(
        {
            "customer_id": working["customer_id"],
            "observation_date": working["observation_date"],
            "age": pd.NA,
            "annual_income": pd.to_numeric(working["annual_inc"], errors="coerce"),
            "debt_to_income": _percentage_points_to_fraction(working["dti"]),
            "credit_utilisation": _percentage_points_to_fraction(working["revol_util"]),
            "delinquencies_2y": pd.to_numeric(working["delinq_2yrs"], errors="coerce"),
            "loan_amount": pd.to_numeric(working["loan_amnt"], errors="coerce"),
            "interest_rate": _percentage_points_to_fraction(working["int_rate"]),
            "employment_length": working["emp_length"].map(_parse_employment_length),
            "home_ownership": working["home_ownership"].map(_normalise_home_ownership),
            "purpose": working["purpose"].map(_normalise_category),
            "default": working["default"].astype(int),
        },
        columns=CANONICAL_COLUMNS,
    ).reset_index(drop=True)

    default_count = int(canonical["default"].sum())
    non_default_count = int((canonical["default"] == 0).sum())
    output_rows = len(canonical)
    audit = {
        "input_path": str(input_path) if input_path is not None else "",
        "input_rows": input_rows,
        "excluded_rows": input_rows - output_rows,
        "excluded_unresolved_status_rows": unresolved_count,
        "invalid_key_or_date_rows": invalid_key_or_date_count,
        "duplicate_rows": duplicate_count,
        "output_rows": output_rows,
        "non_default_count": non_default_count,
        "default_count": default_count,
        "default_rate": default_count / output_rows if output_rows else 0.0,
        "observation_date_min": _format_audit_date(canonical["observation_date"].min()),
        "observation_date_max": _format_audit_date(canonical["observation_date"].max()),
    }
    return canonical, audit


def _validate_raw_columns(columns: pd.Index) -> None:
    missing_columns = [column for column in RAW_COLUMNS if column not in columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Input data is missing required LendingClub columns: {missing}")


def _map_default_status(value: object) -> int | None:
    status = _normalise_status(value)
    if status in NON_DEFAULT_STATUSES:
        return 0
    if status in DEFAULT_STATUSES:
        return 1
    return None


def _normalise_status(value: object) -> str:
    if pd.isna(value):
        return ""
    text = " ".join(str(value).strip().lower().split())
    return text.replace("status: ", "status:")


def _parse_issue_date(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip()
    parsed = pd.to_datetime(text, format="%b-%Y", errors="coerce")
    iso_date_mask = parsed.isna() & text.str.match(r"\d{4}-\d{1,2}-\d{1,2}$", na=False)
    parsed.loc[iso_date_mask] = pd.to_datetime(
        text.loc[iso_date_mask],
        format="%Y-%m-%d",
        errors="coerce",
    )
    return parsed.dt.to_period("M").dt.to_timestamp()


def _percentage_points_to_fraction(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.rstrip("%")
    return (pd.to_numeric(cleaned, errors="coerce") / 100).round(6)


def _parse_employment_length(value: object) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"", "n/a", "na", "none"}:
        return None
    if text.startswith("<"):
        return 0
    digits = "".join(character for character in text if character.isdigit())
    if not digits:
        return None
    return int(digits)


def _normalise_home_ownership(value: object) -> str:
    category = _normalise_category(value)
    if category in {"rent", "mortgage", "own"}:
        return category
    return "other"


def _normalise_category(value: object) -> str:
    if pd.isna(value):
        return "other"
    category = str(value).strip().lower().replace(" ", "_")
    return category or "other"


def _format_audit_date(value: object) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()
