# Data Guide

The project can run with synthetic data, so no external dataset is required. Default demo
reports are synthetic. The separately labelled `reports/public_lendingclub/` directory
contains aggregate evidence generated from the full public dataset.

## LendingClub Accepted Loans

The auditable ingestion path supports the Kaggle dataset
[All Lending Club loan data](https://www.kaggle.com/datasets/wordsforthewise/lending-club).
From the repository root, the public build script downloads the accepted-loans file through
Kaggle's anonymous public endpoint, processes it in bounded-memory chunks, runs Projects 1
and 3, and publishes only aggregate reports:

```powershell
.\scripts\run_public_lendingclub.ps1
```

Dataset caveat: review the Kaggle and source dataset terms before use. Do not commit the
raw file or any processed borrower-level output.

To prepare an already downloaded raw file manually:

```powershell
python scripts/prepare_lendingclub_data.py `
  --input data/raw/accepted_2007_to_2018Q4.csv.gz `
  --output data/processed/lendingclub_pd.csv `
  --audit data/processed/lendingclub_ingestion_audit.csv `
  --vintage-resolution data/processed/lendingclub_vintage_resolution.csv `
  --chunk-size 100000
```

Run the modelling workflow with a public-data out-of-time cutoff:

```powershell
python scripts/run_pipeline.py --input data/processed/lendingclub_pd.csv --oot-cutoff 2017-01-01
```

The adapter reads only origination-time fields needed for modelling and excludes unresolved
loan statuses such as `Current`, `Issued`, `In Grace Period`, and late loans. It does not use
post-origination performance fields as predictors. LendingClub does not disclose borrower age,
so the canonical `age` column is retained as missing rather than inferred.

This target is an eventual terminal-outcome proxy, not a Basel or IFRS 9 fixed-horizon PD
definition. Removing unresolved loans prevents active accounts from being labelled non-default,
but it creates right-censoring and selection bias in recent vintages. The optional vintage
output retains unresolved statuses in the denominator and reports issue-quarter resolution;
the full run falls from `48.4%` resolved in 2017Q1 to `3.9%` in 2018Q4. This control quantifies
the limitation but does not turn the target into a fixed-horizon default definition.

Project 2's PD integration bridge may consume the committed synthetic `reports/oot_predictions.csv`
output, but it uses only `customer_id`, `observation_date`, and `recalibrated_pd`. It does
not use `actual_default` or any future outcome to construct ECL inputs.

The decision-strategy workflow uses the pre-OOT calibration holdout to select a controlled
growth challenger, then freezes the cutoff before OOT evaluation. Its public evidence remains
conditional on the accepted-loan sample and cannot estimate outcomes for rejected applicants.
The retrospective comparison is not a randomized A/B test.

## Expected CSV Schema

If you use a real public dataset, transform it into this schema:

| Column | Type | Description |
| --- | --- | --- |
| `customer_id` | string | Unique modelling observation ID; LendingClub uses the loan ID |
| `observation_date` | date | Month or date of model observation; LendingClub uses issue month |
| `age` | integer | Borrower age; missing for LendingClub because it is not disclosed |
| `annual_income` | numeric | Annual income |
| `debt_to_income` | numeric | Debt-to-income ratio |
| `credit_utilisation` | numeric | Revolving credit utilisation |
| `delinquencies_2y` | integer | Number of delinquencies in prior two years |
| `loan_amount` | numeric | Loan principal |
| `interest_rate` | numeric | Contract interest rate |
| `employment_length` | integer | Years of employment |
| `home_ownership` | string | Rent, mortgage, own, or other |
| `purpose` | string | Loan purpose |
| `default` | integer | Binary target: 1 default, 0 non-default |

## GitHub Rule

Keep raw data out of the repository. Commit only:

- Data dictionaries
- Small sample files if legally allowed
- Transformation scripts
- Aggregate reports

The public-report publisher uses an explicit allow-list, rejects CSV files containing a
`customer_id` column, and never publishes `oot_predictions.csv`. The committed lineage file
records the source URL, licence, raw-file hash, input count, and resolved-output count.
It also publishes aggregate strategy and `vintage_resolution.csv` evidence; no borrower
identifiers are included.
