# Risk Analytics Portfolio Roadmap

## Project 1: Credit Risk PD Modelling

Goal: build a bank-style probability of default workflow.

Core deliverables:

- Data loading and schema checks
- LendingClub accepted-loans ingestion adapter for user-downloaded public data
- SQL schema for customer, loan, and performance tables
- Feature engineering for affordability, utilisation, delinquency, and loan terms
- Logistic regression baseline
- Tree-based challenger model
- ROC-AUC, Gini, KS, Brier score, confusion matrix
- Calibration table
- Out-of-time split
- Population Stability Index monitoring
- Clean README and resume bullets

## Project 2: IFRS 9 ECL Engine

Goal: calculate expected credit loss using PD, LGD, EAD, staging, and macro scenario weights.

Planned modules:

- `staging.py`: Stage 1, Stage 2, Stage 3 classification logic
- `ecl.py`: 12-month and lifetime ECL calculations
- `scenarios.py`: base, upside, downside macro scenario weighting
- `portfolio.py`: account-level and portfolio-level aggregation
- `reports.py`: waterfall and sensitivity outputs

Suggested outputs:

- Account-level ECL table
- Stage migration summary
- Scenario-weighted portfolio ECL
- Sensitivity to unemployment and interest-rate stress

Resume angle:

> Built an IFRS 9 expected credit loss engine calculating account-level and portfolio-level ECL using PD, LGD, EAD, staging rules, and macroeconomic scenario weights.

## Project 3: Model Validation Framework

Goal: create a reusable validation toolkit for credit risk models.

Planned modules:

- `performance.py`: AUC, Gini, KS, precision, recall
- `calibration.py`: calibration curves, Brier score, bin-level observed default rates
- `stability.py`: PSI, CSI, drift reports
- `benchmarking.py`: incumbent vs challenger model comparisons
- `reporting.py`: validation summary tables

Suggested outputs:

- Validation report for the PD model from Project 1
- Model limitation register
- Monitoring dashboard-ready CSVs
- Challenger benchmark analysis

Resume angle:

> Developed a model validation framework for credit risk models, covering discrimination, calibration, stability, challenger benchmarking, and monitoring thresholds.

