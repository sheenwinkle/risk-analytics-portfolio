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
- Project 1 synthetic recalibrated PD output bridge using a latest or requested reporting
  date cohort
- Constant-hazard conversion from 12-month cumulative recalibrated PD to monthly marginal
  PD term structures with explicit scenario hazard multipliers
- Explicit synthetic account assumptions for EAD, LGD, maturity, EIR, DPD, SICR,
  credit-impaired/defaulted flags, and prior stage
- Deterministic synthetic demo pipeline and committed report outputs
- SQL schema and example portfolio, stage migration, and scenario queries

Implemented outputs:

- Account-level ECL table
- Stage migration summary
- Scenario-weighted portfolio ECL
- Scenario-level account ECL table
- Markdown demo report
- PD integration lineage, account, scenario, portfolio, migration, and Markdown reports

Still planned:

- Add documented SICR rebuttal and management-overlay examples
- Add macroeconomic sensitivity and stress reporting
- Add model validation and governance artefacts around ECL inputs

Resume angle:

> Built a runnable IFRS 9 ECL foundation calculating account-level and portfolio-level expected credit loss using configurable staging policy, monthly PD/LGD/EAD term structures, discounting, explicit scenario weights, stage migration reporting, and a validated bridge from synthetic Project 1 recalibrated PD outputs.

## Project 3: Model Validation Framework

Goal: create a reusable validation toolkit for credit risk models.

Implemented foundation:

- Strict Project 1 OOT score and selected-model lineage adapter
- Independent tie-safe AUC, Gini, KS, Brier, and portfolio calibration metrics
- Deterministic low-to-high PD deciles and monthly performance diagnostics
- Chronological reference/current PSI using reference-derived midpoint bins
- Selected recalibrated incumbent versus unselected raw challenger comparison
- Selected raw versus recalibrated impact comparison
- Frozen, validated traffic-light policy for discrimination, calibration, PSI, and challenger tests
- Warning/fail findings with recommended actions and a model limitation register
- Deterministic CSV evidence and recruiter-readable Markdown validation report
- PostgreSQL validation-run, metric, finding, benchmark, and limitation schemas
- Behavioural, lineage, edge-case, real-contract, and byte-reproducibility tests

Implemented outputs:

- Validation report for the PD model from Project 1
- Model limitation register
- Monitoring dashboard-ready CSVs
- Challenger benchmark analysis

Current candidate opinion:

- Overall illustrative policy outcome: fail
- AUC, KS, PSI, and challenger checks: pass
- Absolute calibration gap: fail because mean recalibrated PD materially understates the
  stressed OOT observed default rate

Still planned:

- Segment and vintage-level backtesting
- Bootstrap confidence intervals and uncertainty reporting
- Feature-level replication, CSI, and characteristic drift analysis
- Persisted validation-run loader for the PostgreSQL governance schema
- Formal issue tracking and closure evidence around validation findings

Resume angle:

> Developed a reusable credit risk model validation framework covering independent discrimination and calibration reperformance, deterministic backtesting, PSI stability, challenger benchmarking, explicit governance thresholds, actionable findings, and a documented fail opinion for material PD underestimation.

