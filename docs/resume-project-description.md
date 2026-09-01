# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and SQL credit risk analytics portfolio with LendingClub ingestion, leakage-safe PD model selection, PD recalibration, approval strategy scenarios, PSI monitoring, and a synthetic recalibrated-PD bridge into an educational ECL engine.

## Resume Bullets

- Built an end-to-end credit risk probability of default workflow in Python, covering LendingClub accepted-loans ingestion, data validation, feature engineering, pre-OOT model selection, out-of-time testing, logistic recalibration, and monitoring outputs.
- Benchmarked logistic regression against a random forest challenger model using ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix diagnostics, with selection performed before OOT evaluation.
- Produced fixed max-PD approval cutoff scenario outputs showing approval rate, observed default rate, exposure, expected loss, and rejected-default capture without optimising thresholds on OOT.
- Designed PostgreSQL schemas and analytical SQL queries for customer, loan, and monthly performance data to support credit risk reporting and model development.
- Produced portfolio-ready model artefacts, including account-level raw and recalibrated PD predictions, calibration deciles, PSI drift reports, and a saved recalibrated model wrapper.
- Connected committed synthetic recalibrated out-of-time PD outputs to an educational IFRS 9 ECL engine through validated reporting-date cohort selection, explicit account assumptions, scenario hazard multipliers, and reproducible ECL reports.

## LinkedIn / GitHub Summary

This project demonstrates a bank-style credit risk analytics workflow for probability of default estimation and educational ECL reporting. It includes a LendingClub raw-data adapter, synthetic demo reports, and Python, scikit-learn, and SQL components to build interpretable and challenger PD models, select candidates on a pre-OOT calibration holdout, evaluate raw and recalibrated PDs on an untouched out-of-time sample, run fixed lending strategy scenarios, monitor feature drift with Population Stability Index, and feed synthetic recalibrated PD outputs into a simplified ECL engine without using future outcomes.

## Interview Pitch

I built this project to show how I think about credit risk models beyond generic machine learning accuracy. The workflow estimates borrower-level probability of default, evaluates whether the model ranks risk correctly using AUC, Gini, and KS, selects the candidate before OOT evaluation, recalibrates PDs on a later pre-OOT holdout, and monitors population drift using PSI. I also added fixed approval cutoff scenarios and a synthetic PD-to-ECL bridge to show how calibrated PD outputs can feed portfolio risk reporting while keeping future outcomes out of ECL input construction. The ECL bridge uses a constant-hazard lifetime extrapolation for education, not as an IFRS 9 compliance claim.

