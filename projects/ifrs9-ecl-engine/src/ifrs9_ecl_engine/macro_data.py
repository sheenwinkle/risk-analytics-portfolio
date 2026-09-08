from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.macro_satellite import EXPECTED_REPORTING_BASIS

APRA_SERIES_END = pd.Timestamp("2021-12-31")
CURATED_SERIES_START = pd.Timestamp("2004-09-30")


@dataclass(frozen=True)
class RbaSeries:
    values: pd.Series
    series_id: str
    title: str
    description: str
    frequency: str
    adjustment_type: str
    units: str
    source: str
    publication_date: str


def build_public_macro_dataset(
    apra_workbook: str | Path,
    rba_labour_csv: str | Path,
    rba_gdp_csv: str | Path,
) -> tuple[pd.DataFrame, dict[str, RbaSeries]]:
    """Extract the frozen pre-APS 220 APRA proxy and join official macro series."""
    apra_frame = pd.read_excel(apra_workbook, sheet_name="Tab 2d", header=None)
    credit = extract_apra_credit_proxy(apra_frame)
    unemployment = read_rba_series(rba_labour_csv, "GLFSURSA")
    gdp = read_rba_series(rba_gdp_csv, "GGDPCVGDPY")

    if unemployment.frequency != "Monthly" or unemployment.adjustment_type != "Seasonally adjusted":
        raise ValueError("GLFSURSA must be monthly and seasonally adjusted")
    if gdp.frequency != "Quarterly" or gdp.adjustment_type != "Seasonally adjusted":
        raise ValueError("GGDPCVGDPY must be quarterly and seasonally adjusted")

    quarterly_unemployment = unemployment.values.resample("QE").mean().rename(
        "unemployment_rate_pct"
    )
    quarterly_gdp = gdp.values.rename("real_gdp_yoy_pct")
    merged = (
        credit.set_index("quarter")
        .join([quarterly_unemployment, quarterly_gdp], how="left")
        .reset_index()
    )
    required_macro = ["unemployment_rate_pct", "real_gdp_yoy_pct"]
    if merged[required_macro].isna().any().any():
        missing = merged.loc[merged[required_macro].isna().any(axis=1), "quarter"]
        raise ValueError(
            "Macro series do not cover APRA quarter ends: "
            + ", ".join(value.strftime("%Y-%m-%d") for value in missing)
        )
    merged["apra_reporting_basis"] = EXPECTED_REPORTING_BASIS
    return merged, {"unemployment": unemployment, "gdp": gdp}


def extract_apra_credit_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    labels = frame.iloc[:, 0].astype(str).str.strip()
    numerator_row = _unique_label_index(
        labels,
        "Sum of impaired facilities and past due items",
    )
    denominator_row = _unique_label_index(labels, "Gross loans and advances")
    quarter_marker = frame.iloc[:, 1].astype(str).str.strip()
    marker_rows = quarter_marker[quarter_marker == "Quarter end"].index.tolist()
    if len(marker_rows) != 1:
        raise ValueError("APRA sheet must contain exactly one Quarter end marker")
    date_row = marker_rows[0] + 1

    dates = pd.to_datetime(frame.iloc[date_row, 1:], format="%b %Y", errors="coerce")
    numerator = pd.to_numeric(frame.iloc[numerator_row, 1:], errors="coerce")
    denominator = pd.to_numeric(frame.iloc[denominator_row, 1:], errors="coerce")
    extracted = pd.DataFrame(
        {
            "quarter": dates.to_numpy(),
            "apra_impaired_plus_past_due_m": numerator.to_numpy(),
            "apra_gross_loans_advances_m": denominator.to_numpy(),
        }
    ).dropna(subset=["quarter"])
    extracted["quarter"] = extracted["quarter"] + pd.offsets.QuarterEnd(0)

    historical = extracted[
        (extracted["quarter"] >= CURATED_SERIES_START)
        & (extracted["quarter"] <= APRA_SERIES_END)
    ].copy()
    if historical["apra_impaired_plus_past_due_m"].isna().any():
        raise ValueError("APRA historical impaired plus past-due series contains gaps")
    if historical["apra_gross_loans_advances_m"].isna().any():
        raise ValueError("APRA gross loans and advances series contains gaps")
    if (historical["apra_gross_loans_advances_m"] <= 0).any():
        raise ValueError("APRA gross loans and advances must be positive")

    post_break = extracted[extracted["quarter"] > APRA_SERIES_END]
    if post_break["apra_impaired_plus_past_due_m"].notna().any():
        raise ValueError("Pre-APS 220 APRA proxy unexpectedly continues after 2021-12-31")
    historical["npl_proxy_ratio"] = (
        historical["apra_impaired_plus_past_due_m"]
        / historical["apra_gross_loans_advances_m"]
    )
    return historical.reset_index(drop=True)


def read_rba_series(path: str | Path, series_id: str) -> RbaSeries:
    with Path(path).open(encoding="utf-8-sig", newline="") as source_file:
        rows = list(csv.reader(source_file))
    if not rows:
        raise ValueError("RBA CSV must contain rows")
    width = max(len(row) for row in rows)
    raw = pd.DataFrame([row + [None] * (width - len(row)) for row in rows])
    series_rows = raw.index[raw.iloc[:, 0].eq("Series ID")].tolist()
    if len(series_rows) != 1:
        raise ValueError("RBA CSV must contain exactly one Series ID row")
    series_row = series_rows[0]
    matches = raw.columns[raw.iloc[series_row].eq(series_id)].tolist()
    if len(matches) != 1:
        raise ValueError(f"RBA series {series_id} must occur exactly once")
    column = matches[0]

    metadata = {
        label: _metadata_value(raw, label, column)
        for label in [
            "Title",
            "Description",
            "Frequency",
            "Type",
            "Units",
            "Source",
            "Publication date",
        ]
    }
    dates = pd.to_datetime(raw.iloc[series_row + 1 :, 0], dayfirst=True, errors="coerce")
    values = pd.to_numeric(raw.iloc[series_row + 1 :, column], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates, name=series_id).dropna()
    series = series[~series.index.isna()].sort_index()
    if series.index.duplicated().any():
        raise ValueError(f"RBA series {series_id} contains duplicate dates")
    return RbaSeries(
        values=series,
        series_id=series_id,
        title=metadata["Title"],
        description=metadata["Description"],
        frequency=metadata["Frequency"],
        adjustment_type=metadata["Type"],
        units=metadata["Units"],
        source=metadata["Source"],
        publication_date=metadata["Publication date"],
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_label_index(labels: pd.Series, label: str) -> int:
    matches = labels[labels == label].index.tolist()
    if len(matches) != 1:
        raise ValueError(f"APRA row label {label!r} must occur exactly once")
    return int(matches[0])


def _metadata_value(frame: pd.DataFrame, label: str, column: int) -> str:
    rows = frame.index[frame.iloc[:, 0].eq(label)].tolist()
    if len(rows) != 1:
        raise ValueError(f"RBA CSV must contain exactly one {label} row")
    value = frame.iat[rows[0], column]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RBA {label} metadata is missing")
    return value.strip()
