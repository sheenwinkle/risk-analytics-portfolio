from __future__ import annotations

import argparse
import json
from pathlib import Path

from ifrs9_ecl_engine.macro_data import build_public_macro_dataset, sha256_file

APRA_URL = (
    "https://www.apra.gov.au/system/files/2026-06/"
    "Quarterly%20authorised%20deposit-taking%20institution%20performance-"
    "September%202004%20to%20March%202026.xlsx"
)
RBA_H5_URL = "https://www.rba.gov.au/statistics/tables/csv/h5-data.csv"
RBA_H1_URL = "https://www.rba.gov.au/statistics/tables/csv/h1-data.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the attributed Australian macro-credit snapshot."
    )
    parser.add_argument("--apra-workbook", type=Path, required=True)
    parser.add_argument("--rba-h5", type=Path, required=True)
    parser.add_argument("--rba-h1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lineage-output", type=Path, required=True)
    parser.add_argument("--retrieved-at", default="2026-09-07")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data, rba_series = build_public_macro_dataset(
        args.apra_workbook,
        args.rba_h5,
        args.rba_h1,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(
        args.output,
        index=False,
        date_format="%Y-%m-%d",
        float_format="%.10f",
        lineterminator="\n",
    )

    lineage = {
        "schema_version": 1,
        "dataset": "australia_macro_credit",
        "retrieved_at": args.retrieved_at,
        "coverage": {
            "start": data["quarter"].min().strftime("%Y-%m-%d"),
            "end": data["quarter"].max().strftime("%Y-%m-%d"),
            "quarterly_observations": len(data),
        },
        "target_definition": (
            "APRA banks' sum of impaired facilities and past-due items divided by "
            "gross loans and advances"
        ),
        "reporting_break": {
            "excluded_from": "2022-03-31",
            "reason": (
                "APRA updated asset-quality series for APS 220; the post-break "
                "non-performing definition is not spliced into the historical proxy."
            ),
        },
        "sources": [
            {
                "publisher": "APRA",
                "title": "Quarterly ADI performance statistics",
                "url": APRA_URL,
                "sha256": sha256_file(args.apra_workbook),
                "sheet": "Tab 2d",
                "rows": [
                    "Sum of impaired facilities and past due items",
                    "Gross loans and advances",
                ],
                "attribution": "© Australian Prudential Regulation Authority 2026",
                "licence": "CC BY 4.0",
            },
            {
                "publisher": "RBA",
                "underlying_source": rba_series["unemployment"].source,
                "title": "H5 Labour Force",
                "url": RBA_H5_URL,
                "sha256": sha256_file(args.rba_h5),
                "series_id": rba_series["unemployment"].series_id,
                "publication_date": rba_series["unemployment"].publication_date,
                "transformation": "Quarterly arithmetic mean of monthly observations",
                "attribution": "Based on Australian Bureau of Statistics data via RBA",
            },
            {
                "publisher": "RBA",
                "underlying_source": rba_series["gdp"].source,
                "title": "H1 Gross Domestic Product and Income",
                "url": RBA_H1_URL,
                "sha256": sha256_file(args.rba_h1),
                "series_id": rba_series["gdp"].series_id,
                "publication_date": rba_series["gdp"].publication_date,
                "transformation": "No aggregation; quarterly year-ended growth",
                "attribution": "Based on Australian Bureau of Statistics data via RBA",
            },
        ],
        "curated_file_sha256": sha256_file(args.output),
    }
    args.lineage_output.parent.mkdir(parents=True, exist_ok=True)
    args.lineage_output.write_text(
        json.dumps(lineage, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(args.output)
    print(args.lineage_output)


if __name__ == "__main__":
    main()
