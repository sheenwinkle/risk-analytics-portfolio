# Risk Analytics Portfolio Roadmap

## Project 1: Credit Risk PD Modelling

Goal: build a bank-style probability of default workflow.

Core deliverables:

- Data loading and schema checks
- Anonymous public-data download, chunked LendingClub ingestion, and cross-chunk deduplication
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
- Privacy-safe publication of aggregate public-data evidence and lineage metadata
- Raw-status vintage resolution denominators for maturity and right-censoring review
- Clean README and resume bullets

Current evidence:

- 2,260,701 raw accepted-loan rows audited and 1,348,099 resolved outcomes retained
- 225,639 untouched 2017-2018 OOT observations
- Selected random forest ROC-AUC 0.6999; recalibration reduced Brier score from 0.2085 to 0.1547
- Status resolution falls from 48.4% in 2017Q1 to 3.9% in 2018Q4, exposing recent-vintage censoring

## Project 2: IFRS 9 ECL Engine

Goal: calculate expected credit loss using PD, LGD, EAD, staging, and macro scenario weights.

Complete scoped case study:

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
- Independent weight, severity, and combined macro-sensitivity cases
- Overlay trigger, model-overlap, approval, cap, and duplicate-risk controls
- SQL governance tables and model-to-illustrative-reported ECL reconciliation
- SQL schema and example portfolio, stage migration, and scenario queries

Implemented outputs:

- Account-level ECL table
- Stage migration summary
- Scenario-weighted portfolio ECL
- Scenario-level account ECL table
- Markdown demo report
- PD integration lineage, account, scenario, portfolio, migration, and Markdown reports
- Macro-sensitivity detail/summary, overlay register, ECL reconciliation, and governance report

Potential extensions:

- Add documented SICR rebuttal decisions
- Add contractual cash-flow, collateral, cure, and prepayment sensitivity
- Add empirical macroeconomic model estimation and independent validation evidence

Resume angle:

> Built a runnable IFRS 9 ECL engine calculating account-level and portfolio-level expected credit loss using configurable staging policy, monthly PD/LGD/EAD term structures, discounting, explicit scenario weights, stage migration, and a validated Project 1 PD bridge; added separate macro sensitivity and governed overlay reconciliation with trigger, overlap, approval, and cap controls.

## Project 3: Model Validation Framework

Goal: create a reusable validation toolkit for credit risk models.

Complete scoped case study:

- Strict Project 1 OOT score, full feature, derived-ratio, and selected-model lineage adapter
- Independent tie-safe AUC, Gini, KS, Brier, and portfolio calibration metrics
- Deterministic low-to-high PD deciles and monthly performance diagnostics
- DeLong, Wilson, normal-mean, and paired calibration-gap confidence intervals
- Quarterly vintage and home-ownership/purpose segment backtests with reliability flags
- Chronological reference/current PSI using reference-derived midpoint bins
- Numeric/categorical CSI with missingness drift and explicit unavailable-feature handling
- Selected recalibrated incumbent versus unselected raw challenger comparison
- Selected raw versus recalibrated impact comparison
- Frozen, validated traffic-light policy for discrimination, calibration, PSI, CSI, and challenger tests
- Warning/fail findings with recommended actions and a model limitation register
- Deterministic CSV evidence and recruiter-readable Markdown validation report
- PostgreSQL validation-run, metric, uncertainty, grouped-performance, characteristic,
  finding, benchmark, and limitation schemas
- Transactional PostgreSQL loader and PostgreSQL 16 integration test
- Full public LendingClub OOT validation with context-specific limitations
- No-look-ahead rolling calibration remediation and finding lifecycle events
- Behavioural, lineage, edge-case, real-contract, and byte-reproducibility tests

Implemented outputs:

- Validation report for the PD model from Project 1
- Model limitation register
- Monitoring dashboard-ready CSVs
- Challenger benchmark analysis
- Public-data warning opinion and safe aggregate publication
- Sequential remediation retest and pending-fresh-OOT closure decision
- Public vintage maturity, segment performance, and statistical uncertainty evidence
- Public feature-stability summary, bin drivers, and recruiter-facing CSI chart

Current candidate opinion:

- Overall illustrative policy outcome: fail
- AUC, KS, PSI, CSI, and challenger checks: pass
- Absolute calibration gap: fail because mean recalibrated PD materially understates the
  stressed OOT observed default rate

Public LendingClub opinion:

- Overall illustrative policy outcome: warning
- AUC 0.699887, KS 0.292493, and absolute calibration gap 0.026335: warning
- PSI 0.016656 and challenger margin -0.009411: pass
- Maximum available CSI 0.077926 (`credit_utilisation`): pass; source-missing `age` unavailable
- AUC 95% CI 0.697369-0.702405; calibration-gap 95% CI 0.024716-0.027955
- 2017Q1 to 2018Q4 raw status resolution declines from 48.4% to 3.9%

Remediation evidence:

- Synthetic sequential retest reduced absolute calibration gap from 0.064441 to 0.009218
- Closure remains `pending_fresh_oot` because the retest is not an independent OOT window

Independent replication evidence:

- Both candidate holdout AUCs reproduce with zero reported delta
- Logistic regression remains selected on the frozen pre-OOT holdout
- Nineteen transformed coefficients/importances per model reconcile within `1e-8`
- Borrower-level development rows remain local; committed evidence is aggregate only

Decision-strategy evidence:

- Controlled 20% max-PD challenger selected only on the pre-OOT calibration holdout
- Public OOT: 35,876 incremental approvals and USD 17.0m realised contribution proxy uplift
- Synthetic stress OOT: 107 incremental approvals but 0.14m realised contribution decline
- Paired marginal-cohort bootstrap intervals drive advance/retain governance decisions

Potential extensions:

- Production scoring-service implementation testing beyond analytical candidate replication
- Formal fixed-horizon label construction or survival analysis for unresolved outcomes
- Reject-inference sensitivity for the accepted-only applicant population
- ECL model validation and overlay governance

Resume angle:

> Developed a reusable Python and PostgreSQL credit risk model validation framework covering independent discrimination and calibration reperformance, statistical uncertainty, vintage and segment backtesting, PSI/CSI stability, challenger benchmarking, explicit governance thresholds, public-data validation, and no-look-ahead remediation lifecycle evidence.
