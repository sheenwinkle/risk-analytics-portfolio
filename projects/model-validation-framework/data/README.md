# Data and Lineage

Project 3 does not commit a second copy of borrower-level or account-level data. Its default
input is the committed synthetic score contract from Project 1:

```text
../credit-risk-pd-model/reports/oot_predictions.csv
```

The separately labelled `reports/public_lendingclub/` evidence was generated from the local,
ignored public OOT contract using `data_context=public_lendingclub`. Its committed source
lineage records only aggregate counts, dates, dataset metadata, and source hashes.

## Source Contract

| Field | Role in validation |
| --- | --- |
| `customer_id` | Stable row identifier and deterministic tie-breaker |
| `observation_date` | OOT period and chronological stability split |
| `home_ownership` | Non-sensitive business segment for grouped backtesting |
| `purpose` | Non-sensitive loan-purpose segment for grouped backtesting |
| `actual_default` | Observed binary outcome for backtesting |
| `selected_model` | Model-development selection carried into validation |
| `selected_model_raw_pd` | Selected raw score used for lineage reconciliation |
| `logistic_regression_pd` | Logistic raw incumbent/challenger score |
| `recalibrated_pd` | Selected model score after pre-OOT recalibration |
| `random_forest_pd` | Random forest raw incumbent/challenger score |

The adapter rejects missing fields, duplicate or blank IDs, blank segment values, invalid
dates, one-class samples, non-finite/out-of-range PDs, multiple selected models, unsupported
model names, and row-level selected-score mismatches.

## Privacy and Reproducibility

- The committed Project 1 file contains synthetic `C`-prefixed customer IDs.
- Raw LendingClub data and locally prepared borrower-level files remain excluded by the root
  `.gitignore` rules.
- Candidate reports under `reports/` are derived evidence, not source observations.
- Vintage and segment reports contain aggregate counts and metrics only.
- The validation pipeline writes deterministic files without timestamps or local paths.
- The public publisher uses an explicit aggregate allow-list and rejects CSV files containing
  a `customer_id` column.

To validate a locally prepared public-data run, point `scripts/run_validation.py` at its
compatible OOT prediction report and set `--data-context public_lendingclub`. Then use
`scripts/publish_public_validation.py` to publish the safe aggregate subset. Review dataset
terms and identifiers before committing any derived output.
