# Public LendingClub Aggregate Evidence

This directory contains privacy-safe aggregate evidence from a full run on the public
[All Lending Club loan data](https://www.kaggle.com/datasets/wordsforthewise/lending-club)
accepted-loans file. Kaggle identifies the dataset license as CC0: Public Domain.

## Data Lineage

- Raw file: `accepted_2007_to_2018Q4.csv.gz`
- SHA-256: `55c16f75120f897683f02e7aabcf080d0e4a20c4832feb1d592cfa941bd62a2d`
- Raw rows read: 2,260,701
- Resolved terminal-outcome rows retained: 1,348,099
- Unresolved status rows excluded: 912,602
- Observation period: June 2007 to December 2018
- OOT cutoff: 1 January 2017
- OOT accounts: 225,639
- Raw status resolution: 48.4% in 2017Q1, declining to 3.9% in 2018Q4

The target remains a resolved terminal-outcome proxy rather than a regulatory fixed-horizon
default definition. `vintage_resolution.csv` retains unresolved raw statuses in each issue
quarter's denominator. It shows that recent-vintage censoring and accepted-loan selection bias
remain material limitations rather than silently treating resolved rows as a complete cohort.

## Aggregate Result

The random forest was selected using the later pre-OOT calibration holdout. On the untouched
2017-2018 OOT cohort it achieved ROC-AUC `0.700`, Gini `0.400`, and KS `0.292`. Logistic
recalibration reduced Brier score from `0.208` to `0.155`; mean recalibrated PD was `23.9%`
against an observed default rate of `21.3%`.

## Credit Decision Strategy Backtest

The incumbent 15% max-PD cutoff and candidate thresholds were compared on the pre-OOT
calibration holdout. A controlled 20% challenger was selected because it stayed within the
illustrative 13% bad-rate, 6% expected-loss-rate, and five-percentage-point cutoff-change
limits. The rule was frozen before the 2017-2018 OOT evaluation.
The pre-OOT holdout supports both recalibration and policy development, so its selection
evidence may be optimistic even though the OOT decision remains untouched.

| OOT evidence | Incumbent | Challenger | Increment |
| --- | ---: | ---: | ---: |
| Approved accounts | 65,820 | 101,696 | +35,876 |
| Approval rate | 29.2% | 45.1% | +15.9 pp |
| Approved exposure | 800.3m | 1,249.7m | +449.4m |
| Expected credit contribution proxy | 30.1m | 44.8m | +14.7m |
| Realised credit contribution proxy | 34.8m | 51.8m | +17.0m |

Amounts in this table are USD.
The paired marginal-cohort bootstrap interval for incremental realised contribution is
`16.1m-18.0m`, so the illustrative decision is `advance_challenger`. This is not a randomized
A/B test or a causal production estimate. The dataset contains only accepted loans, and the
one-year proxy omits funding, operating costs, prepayment, and cash-flow timing.

The largest decile-level calibration gap was `7.1%` in D10. Credit utilisation had the largest
PSI at `0.188`, a moderate rather than material shift under the project's disclosed policy.

The resolved-only OOT sample is not maturity-neutral. From 2017Q1 to 2018Q4, outcome resolution
declines from `48.4%` to `3.9%`, while the resolved-sample default rate falls from `22.9%` to
`2.4%`. The latter is therefore not presented as genuine credit improvement; it is evidence of
right-censoring in the terminal-status target.

## Privacy Boundary

Only aggregate reports are committed. Raw data, canonical borrower-level data, fitted model
objects, and `oot_predictions.csv` remain under Git-ignored local directories. The publication
script rejects any safe-list CSV containing a `customer_id` column.

## Reproduce Locally

From the repository root, rebuild the complete public-data evidence chain:

```powershell
.\scripts\run_public_lendingclub.ps1
```

The equivalent Project 1 steps are:

```powershell
cd projects/credit-risk-pd-model
python scripts/prepare_lendingclub_data.py `
  --input data/raw/accepted_2007_to_2018Q4.csv.gz `
  --output data/processed/lendingclub_pd.csv `
  --audit data/processed/lendingclub_ingestion_audit.csv `
  --vintage-resolution data/processed/lendingclub_vintage_resolution.csv `
  --chunk-size 100000

python scripts/run_pipeline.py `
  --input data/processed/lendingclub_pd.csv `
  --oot-cutoff 2017-01-01 `
  --reports data/processed/public_run/reports `
  --models data/processed/public_run/models

python scripts/publish_public_run.py `
  --source-reports data/processed/public_run/reports `
  --ingestion-audit data/processed/lendingclub_ingestion_audit.csv `
  --vintage-resolution data/processed/lendingclub_vintage_resolution.csv `
  --raw-input data/raw/accepted_2007_to_2018Q4.csv.gz `
  --output-dir reports/public_lendingclub
```
