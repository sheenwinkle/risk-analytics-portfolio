# Third-Party Data Notices

The repository's MIT licence applies to original project code and documentation. It does
not replace the terms attached to third-party source data.

## Australian Prudential Regulation Authority

`projects/ifrs9-ecl-engine/data/public/australia_macro_credit.csv` includes transformed,
aggregate values from APRA's *Quarterly authorised deposit-taking institution performance*
statistics.

- Attribution: © Australian Prudential Regulation Authority 2026
- Source: [Quarterly ADI performance statistics](https://www.apra.gov.au/news-and-publications/quarterly-authorised-deposit-taking-institution-statistics)
- Terms: [APRA copyright](https://www.apra.gov.au/copyright), CC BY 4.0
- Changes: selected impaired/past-due and gross-loan series, restricted history to the
  pre-APS 220 reporting basis, aligned quarter ends, and calculated an aggregate ratio

## Reserve Bank of Australia and Australian Bureau of Statistics

The same curated file includes unemployment and real-GDP series distributed through RBA
statistical tables. The RBA source files identify the underlying source as ABS.

- Source: [RBA statistical tables](https://www.rba.gov.au/statistics/tables/), H5 series
  `GLFSURSA` and H1 series `GGDPCVGDPY`
- Terms: [RBA copyright](https://www.rba.gov.au/copyright/index.html) and
  [ABS privacy and legal terms](https://www.abs.gov.au/privacy-and-legals)
- Attribution: based on Australian Bureau of Statistics data distributed by the RBA
- Changes: monthly unemployment observations were averaged to calendar quarters; quarterly
  year-ended real-GDP growth was aligned to the APRA series

The raw source files are not redistributed. Source URLs, publication dates, transformations,
and SHA-256 hashes are retained in
`projects/ifrs9-ecl-engine/data/public/australia_macro_credit_lineage.json`.
