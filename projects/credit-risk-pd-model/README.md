# Credit Risk PD Modelling

Probability of default modelling workflow for credit risk analytics and model validation roles.

## Business Problem

Credit risk teams need more than a binary classifier. A useful PD model should estimate a borrower's probability of default, remain calibrated over time, and be monitored for portfolio drift.

This project builds a practical workflow:

```text
Data checks -> feature engineering -> out-of-time split -> baseline model -> challenger model
-> model performance -> calibration -> PSI monitoring -> report outputs
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
- Out-of-time validation to mimic model performance after economic change
- Calibration review for predicted PD accuracy
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

Use your own CSV:

```powershell
python scripts/run_pipeline.py --input data/raw/credit_data.csv
```

## Outputs

The pipeline writes:

- `reports/model_metrics.csv`: ROC-AUC, Gini, KS, Brier score, precision, recall, confusion matrix values
- `reports/calibration_table.csv`: decile-level predicted PD vs observed default rate
- `reports/psi_report.csv`: population drift indicators
- `reports/oot_predictions.csv`: account-level out-of-time predicted PDs
- `models/<best_model>.joblib`: selected trained model

## Model Evaluation

The project intentionally separates:

- Discrimination: ROC-AUC, Gini, KS
- Calibration: Brier score and decile calibration table
- Stability: PSI across development and out-of-time samples

That framing is closer to how banks and fintech lenders assess risk models.

## Data Source

The code runs without external data by generating synthetic credit data. For a stronger public GitHub version, replace the synthetic data with a public lending dataset such as:

- LendingClub accepted loans
- Home Credit Default Risk
- UCI Default of Credit Card Clients

Do not commit large raw datasets to GitHub. Store raw files under `data/raw/`, which is ignored by Git.

## Resume Bullets

- Built an end-to-end credit risk PD modelling workflow in Python, including feature engineering, out-of-time validation, calibration analysis, and PSI-based monitoring.
- Compared interpretable logistic regression against a tree-based challenger model using ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix diagnostics.
- Designed SQL schemas and analytics queries for loan, customer, and performance data to support credit risk reporting and model development.

## Interview Talking Points

- Why calibration matters more in credit risk than ordinary classification accuracy
- Why an out-of-time split is more realistic than a random train-test split
- How PSI can detect portfolio drift before model performance deteriorates
- Why logistic regression is still common in regulated risk modelling
- How this project can extend into IFRS 9 ECL and model validation
