# Credit Risk PD Modelling

Probability of default modelling workflow for credit risk analytics and model validation roles.

## Business Problem

Credit risk teams need more than a binary classifier. A useful PD model should estimate a borrower's probability of default, remain calibrated over time, and be monitored for portfolio drift.

This project builds a practical workflow:

```text
Data checks -> feature engineering -> out-of-time split -> baseline model -> challenger model
-> pre-OOT calibration holdout model selection -> logistic PD recalibration
-> fixed lending approval cutoff scenarios -> WOE/IV screening -> permutation importance
-> PSI monitoring -> report outputs
```

## Why This Project Fits Risk Analytics

This is positioned for roles such as:

- Credit Risk Analyst
- Risk Analytics Analyst
- Model Validation Analyst
- Lending Data Analyst
- FinTech Decision Science Analyst

It demonstrates:

- PD modelling rather than generic classification
- Logistic regression as an interpretable baseline
- Random forest as a challenger model
- Leakage-safe model selection on a later pre-OOT calibration holdout
- Out-of-time validation to mimic model performance after economic change
- Logistic recalibration and OOT calibration diagnostics for predicted PD accuracy
- Fixed max-PD lending approval scenario analysis without optimising on OOT
- Scorecard-style Weight of Evidence and Information Value variable screening
- Model-agnostic permutation importance evaluated on the out-of-time sample
- Population Stability Index for monitoring drift
- SQL schema design for credit risk data

## Repository Structure

```text
credit-risk-pd-model/
  data/
    README.md
  models/
  notebooks/
    README.md
  reports/
  scripts/
    prepare_lendingclub_data.py
    run_pipeline.py
  sql/
    schema.sql
    example_queries.sql
  src/
    credit_risk_pd/
  tests/
  requirements.txt
  pyproject.toml
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Run

Use synthetic data:

```powershell
python scripts/run_pipeline.py
```

Prepare the user-downloaded LendingClub accepted-loans file:

```powershell
python scripts/prepare_lendingclub_data.py `
  --input data/raw/accepted_2007_to_2018Q4.csv.gz `
  --output data/processed/lendingclub_pd.csv `
  --audit data/processed/lendingclub_ingestion_audit.csv
```

Run with a public-data out-of-time cutoff:

```powershell
python scripts/run_pipeline.py --input data/processed/lendingclub_pd.csv --oot-cutoff 2017-01-01
```

Adjust the calibration holdout, strategy, or fixed classification settings:

```powershell
python scripts/run_pipeline.py `
  --calibration-fraction 0.25 `
  --lgd 0.45 `
  --approval-thresholds 0.10 0.15 0.20 0.25 `
  --classification-threshold 0.15
```

Use any other canonical CSV:

```powershell
python scripts/run_pipeline.py --input data/raw/credit_data.csv
```

## Verify

```powershell
ruff check src tests scripts
pytest
```

## Outputs

The pipeline writes:

- `reports/model_metrics.csv`: ROC-AUC, Gini, KS, Brier score, and threshold-based metrics with the fixed classification threshold recorded on every row
- `reports/model_selection_audit.csv`: model-development/calibration-holdout dates, counts, and holdout ROC-AUC used for selection
- `reports/recalibration_summary.csv`: fitted pre-OOT recalibration parameters plus raw vs recalibrated OOT calibration diagnostics
- `reports/approval_strategy.csv`: fixed max-PD approval scenarios with LGD, approval rate, observed defaults, approved exposure, expected loss, and rejected-default capture; `loan_amount` is the EAD proxy
- `reports/calibration_table.csv`: decile-level predicted PD vs observed default rate
- `reports/woe_bins.csv`: Weight of Evidence bin detail for numeric quantile bins and categorical category bins
- `reports/woe_summary.csv`: feature-level Information Value ranking for development-sample variable screening
- `reports/feature_importance.csv`: model-agnostic permutation importance for the selected model on the out-of-time sample
- `reports/psi_report.csv`: population drift indicators
- `reports/model_report.md`: markdown summary of model performance, recalibration, strategy scenarios, Information Value, feature importance, and PSI monitoring
- `reports/oot_predictions.csv`: account-level out-of-time actuals, selected raw PD, and recalibrated PD; Project 2's ECL bridge uses only `customer_id`, `observation_date`, and `recalibrated_pd`
- `models/<selected_model>_recalibrated.joblib`: selected base model plus fitted logistic recalibrator with `predict_proba`

## Model Evaluation

The project intentionally separates:

- Discrimination: ROC-AUC, Gini, KS
- Selection: candidate base models train on the earlier pre-OOT sample and are selected by ROC-AUC on a later pre-OOT calibration holdout, not by OOT performance
- Calibration: logistic recalibration is fitted on the pre-OOT holdout; raw and recalibrated PDs are then evaluated only on the untouched OOT sample
- Lending strategy: fixed approval cutoffs are scenario rows, not OOT-optimised recommendations
- Classification: precision, recall, accuracy, and confusion counts use a fixed 15% threshold that is disclosed in the output and never tuned on OOT outcomes
- Scorecard screening: WOE is calculated as `ln(% good / % bad)`, so positive WOE means lower observed default risk and negative WOE means higher observed default risk; Information Value ranks variables by development-sample separation
- Explainability: permutation importance measured by out-of-time ROC-AUC drop
- Stability: PSI across development and out-of-time samples

That framing is closer to how banks and fintech lenders assess risk models.

## Data Source

The code runs without external data by generating synthetic credit data, and the committed
demo reports remain synthetic. For public-data runs, the project includes a LendingClub
accepted-loans adapter for
[All Lending Club loan data](https://www.kaggle.com/datasets/wordsforthewise/lending-club).
Download `accepted_2007_to_2018Q4.csv.gz` yourself, keep it under `data/raw/`, and review
the dataset terms before use.

Leakage policy: the LendingClub adapter reads only origination-time predictors plus
`loan_status` for target construction. It maps resolved terminal outcomes only:
`Fully Paid` and the legacy fully-paid policy status to non-default; `Charged Off`,
`Default`, and the legacy charged-off policy status to default. `Current`, `Issued`,
`In Grace Period`, late, and other unresolved rows are excluded rather than mislabelled.
Borrower age is not disclosed by LendingClub, so `age` is retained as missing.

Target limitation: this mapping is a terminal-outcome PD proxy, not a Basel or IFRS 9
fixed-horizon default definition. Excluding unresolved loans prevents active accounts from
being labelled non-default, but recent vintages can still have right-censoring and selection
bias. Treat public-data results as exploratory unless vintage and maturity controls are added.

Project 2 can consume the committed synthetic `reports/oot_predictions.csv` through a
separate PD-to-ECL bridge. That bridge treats `recalibrated_pd` as a 12-month cumulative PD
and does not use `actual_default` when constructing ECL inputs. Its constant-hazard lifetime
extrapolation is an educational portfolio assumption, not an IFRS 9 compliance claim.

Do not commit raw datasets or borrower-level processed data to GitHub. Store raw files
under `data/raw/` and processed files under `data/processed/`, both of which are ignored.

## Resume Bullets

- Built an end-to-end credit risk PD modelling workflow in Python, including LendingClub raw-data ingestion, feature engineering, leakage-safe pre-OOT model selection, logistic recalibration, fixed approval cutoff scenarios, scorecard-style WOE/IV screening, permutation importance, and PSI-based monitoring.
- Compared interpretable logistic regression against a tree-based challenger model using ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix diagnostics.
- Designed SQL schemas and analytics queries for loan, customer, and performance data to support credit risk reporting and model development.

## Interview Talking Points

- Why calibration matters more in credit risk than ordinary classification accuracy
- Why model selection should happen before OOT evaluation
- How recalibrated PDs can feed fixed lending strategy scenarios without optimising on OOT
- Why an out-of-time split is more realistic than a random train-test split
- How WOE sign convention and Information Value support scorecard-style variable screening
- How permutation importance supports model-agnostic validation review
- How PSI can detect portfolio drift before model performance deteriorates
- Why logistic regression is still common in regulated risk modelling
- How this project's recalibrated synthetic OOT PD outputs can feed an educational ECL
  bridge without leaking future outcomes
