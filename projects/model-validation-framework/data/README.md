# Data and Lineage

Project 3 does not commit a second copy of borrower-level or account-level data. Its default
input is the committed synthetic score contract from Project 1:

```text
../credit-risk-pd-model/reports/oot_predictions.csv
```

## Source Contract

| Field | Role in validation |
| --- | --- |
| `customer_id` | Stable row identifier and deterministic tie-breaker |
| `observation_date` | OOT period and chronological stability split |
| `actual_default` | Observed binary outcome for backtesting |
| `selected_model` | Model-development selection carried into validation |
| `selected_model_raw_pd` | Selected raw score used for lineage reconciliation |
| `logistic_regression_pd` | Logistic raw incumbent/challenger score |
| `recalibrated_pd` | Selected model score after pre-OOT recalibration |
| `random_forest_pd` | Random forest raw incumbent/challenger score |

The adapter rejects missing fields, duplicate or blank IDs, invalid dates, one-class samples,
non-finite/out-of-range PDs, multiple selected models, unsupported model names, and row-level
selected-score mismatches.

## Privacy and Reproducibility

- The committed Project 1 file contains synthetic `C`-prefixed customer IDs.
- Raw LendingClub data and locally prepared borrower-level files remain excluded by the root
  `.gitignore` rules.
- Candidate reports under `reports/` are derived evidence, not source observations.
- The validation pipeline writes deterministic files without timestamps or local paths.

To validate a locally prepared public-data run, point `scripts/run_validation.py` at its
compatible OOT prediction report. Review dataset terms and identifiers before committing any
derived account-level output.
