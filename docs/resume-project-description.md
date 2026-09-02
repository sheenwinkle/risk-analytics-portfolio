# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and SQL credit risk analytics portfolio with LendingClub ingestion, leakage-safe PD model selection, PD recalibration, approval strategy scenarios, an educational ECL engine, and an independent-style model validation framework.

## Resume Bullets

- Built an end-to-end credit risk probability of default workflow in Python, covering LendingClub accepted-loans ingestion, data validation, feature engineering, pre-OOT model selection, out-of-time testing, logistic recalibration, and monitoring outputs.
- Benchmarked logistic regression against a random forest challenger model using ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix diagnostics, with selection performed before OOT evaluation.
- Produced fixed max-PD approval cutoff scenario outputs showing approval rate, observed default rate, exposure, expected loss, and rejected-default capture without optimising thresholds on OOT.
- Designed PostgreSQL schemas and analytical SQL queries for customer, loan, and monthly performance data to support credit risk reporting and model development.
- Produced portfolio-ready model artefacts, including account-level raw and recalibrated PD predictions, calibration deciles, PSI drift reports, and a saved recalibrated model wrapper.
- Connected committed synthetic recalibrated out-of-time PD outputs to an educational IFRS 9 ECL engine through validated reporting-date cohort selection, explicit account assumptions, scenario hazard multipliers, and reproducible ECL reports.
- Built a reusable PD model validation framework that independently reperforms AUC, Gini, tie-safe KS, Brier score, calibration deciles, monthly diagnostics, PSI, and challenger comparisons, then applies explicit policy thresholds and produces actionable findings.
- Documented an overall fail validation opinion when mean recalibrated PD of 9.69% materially understated the stressed OOT observed default rate of 17.40%, while discrimination, stability, and challenger checks passed.
- Designed PostgreSQL governance tables and analytical queries for validation runs, policy metrics, findings, limitations, challenger deltas, and metric trends.

## LinkedIn / GitHub Summary

This portfolio demonstrates a bank-style credit risk workflow from PD development through educational ECL reporting and independent-style model validation. It includes a LendingClub raw-data adapter, leakage-safe pre-OOT selection and recalibration, fixed lending strategy scenarios, PSI monitoring, a synthetic PD-to-ECL bridge, and a separate validation package that consumes frozen OOT scores, reperforms model metrics, tests calibration and stability, benchmarks the challenger, and records policy findings and limitations.

## Interview Pitch

I built this portfolio to show how I think about credit risk models beyond generic machine learning accuracy. Project 1 estimates borrower-level PD, selects the candidate before OOT evaluation, recalibrates on a pre-OOT holdout, and monitors drift. Project 2 demonstrates how frozen recalibrated PD can feed a simplified ECL workflow without using future outcomes as inputs. Project 3 then acts as a separate validator: it consumes only frozen scores and outcomes, reperforms metrics, tests calibration and PSI, benchmarks the challenger, and raises a fail opinion because stressed-period default rates materially exceed mean recalibrated PD. The ECL and validation policies are educational assumptions, not compliance or production approval claims.

## Project 3 Standalone Bullet

> Developed a reusable credit risk model validation framework in Python, independently reperforming AUC, Gini, tie-safe KS, Brier score, calibration deciles, monthly backtesting, PSI, and challenger comparisons; implemented explicit governance thresholds, deterministic evidence files, PostgreSQL reporting schemas, and a documented fail opinion for material PD underestimation.

