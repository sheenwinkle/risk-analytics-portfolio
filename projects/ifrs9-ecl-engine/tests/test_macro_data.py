from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from ifrs9_ecl_engine.macro_data import extract_apra_credit_proxy, read_rba_series


def _write_rba_fixture(path: Path, data_rows: list[tuple[str, str]]) -> None:
    rows = [
        ["H5 LABOUR FORCE"],
        ["Title", "Unemployment rate"],
        ["Description", "Unemployed persons as percentage of labour force"],
        ["Frequency", "Monthly"],
        ["Type", "Seasonally adjusted"],
        ["Units", "Per cent"],
        [],
        ["Source", "ABS"],
        ["Publication date", "21-Aug-2026"],
        ["Series ID", "GLFSURSA"],
        *[list(row) for row in data_rows],
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        csv.writer(output).writerows(rows)


def _apra_fixture(*, post_break_value: float | None = None) -> pd.DataFrame:
    quarters = pd.date_range("2004-09-30", "2022-03-31", freq="QE")
    width = len(quarters) + 1
    frame = pd.DataFrame([[None] * width for _ in range(4)])
    frame.iat[0, 1] = "Quarter end"
    for position, quarter in enumerate(quarters, start=1):
        frame.iat[1, position] = quarter.strftime("%b %Y")
    frame.iat[2, 0] = "Sum of impaired facilities and past due items"
    frame.iat[3, 0] = "Gross loans and advances"
    for position, quarter in enumerate(quarters, start=1):
        frame.iat[2, position] = (
            8_000.0 + position if quarter <= pd.Timestamp("2021-12-31") else post_break_value
        )
        frame.iat[3, position] = 1_000_000.0 + position
    return frame


def test_rba_parser_reads_metadata_values_and_rejects_duplicate_dates(tmp_path: Path) -> None:
    valid_path = tmp_path / "h5.csv"
    _write_rba_fixture(
        valid_path,
        [("31/01/2020", "5.2"), ("29/02/2020", "5.1")],
    )

    series = read_rba_series(valid_path, "GLFSURSA")

    assert series.series_id == "GLFSURSA"
    assert series.frequency == "Monthly"
    assert series.adjustment_type == "Seasonally adjusted"
    assert series.source == "ABS"
    assert series.values.to_list() == [5.2, 5.1]

    duplicate_path = tmp_path / "h5_duplicate.csv"
    _write_rba_fixture(
        duplicate_path,
        [("31/01/2020", "5.2"), ("31/01/2020", "5.1")],
    )
    with pytest.raises(ValueError, match="duplicate dates"):
        read_rba_series(duplicate_path, "GLFSURSA")


def test_apra_parser_freezes_pre_aps220_history_and_rejects_splicing() -> None:
    result = extract_apra_credit_proxy(_apra_fixture())

    assert len(result) == 70
    assert result["quarter"].iloc[0] == pd.Timestamp("2004-09-30")
    assert result["quarter"].iloc[-1] == pd.Timestamp("2021-12-31")
    assert result["npl_proxy_ratio"].between(0, 1).all()

    with pytest.raises(ValueError, match="unexpectedly continues"):
        extract_apra_credit_proxy(_apra_fixture(post_break_value=9_999.0))
