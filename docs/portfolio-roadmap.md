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
- Out-of-time split
- Leakage-safe model selection on a later pre-OOT calibration holdout
- Logistic PD recalibration with OOT calibration diagnostics
- Fixed max-PD approval cutoff strategy scenarios
- Calibration table
- Population Stability Index monitoring
- Clean README and resume bullets

## Project 2: IFRS 9 ECL Engine

Goal: calculate expected credit loss using PD, LGD, EAD, staging, and macro scenario weights.

Implemented foundation:

- `run_ecl_engine(...)`: public API returning an `ECLResult` dataclass
- Configurable Stage 1, Stage 2, and Stage 3 policy with DPD backstops
- Monthly scenario term structures for marginal PD, LGD, and EAD
- 12-month ECL for Stage 1 and lifetime ECL for Stage 2 and Stage 3
- Explicit base, upside, and downside scenario weighting
- Deterministic synthetic demo pipeline and committed report outputs
- SQL schema and example portfolio, stage migration, and scenario queries

Implemented outputs:

- Account-level ECL table
- Stage migration summary
- Scenario-weighted portfolio ECL
- Scenario-level account ECL table
- Markdown demo report

Still planned:

- Connect Project 1 PD outputs to ECL term-structure generation
- Add documented SICR rebuttal and management-overlay examples
- Add macroeconomic sensitivity and stress reporting
- Add model validation and governance artefacts around ECL inputs

Resume angle:

> Built a runnable IFRS 9 ECL foundation calculating account-level and portfolio-level expected credit loss using configurable staging policy, monthly PD/LGD/EAD term structures, discounting, explicit scenario weights, and stage migration reporting.

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

