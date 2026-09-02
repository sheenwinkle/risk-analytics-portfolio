# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and SQL credit risk PD modelling workflow with LendingClub ingestion, leakage-safe model selection, PD recalibration, approval strategy scenarios, and PSI monitoring for lending portfolio risk.

## Resume Bullets

- Built an end-to-end credit risk probability of default workflow in Python, covering LendingClub accepted-loans ingestion, data validation, feature engineering, pre-OOT model selection, out-of-time testing, logistic recalibration, and monitoring outputs.
- Benchmarked logistic regression against a random forest challenger model using ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix diagnostics, with selection performed before OOT evaluation.
- Produced fixed max-PD approval cutoff scenario outputs showing approval rate, observed default rate, exposure, expected loss, and rejected-default capture without optimising thresholds on OOT.
- Designed PostgreSQL schemas and analytical SQL queries for customer, loan, and monthly performance data to support credit risk reporting and model development.
- Produced portfolio-ready model artefacts, including account-level raw and recalibrated PD predictions, calibration deciles, PSI drift reports, and a saved recalibrated model wrapper.

## LinkedIn / GitHub Summary

This project demonstrates a bank-style credit risk modelling workflow for probability of default estimation. It includes a LendingClub raw-data adapter, synthetic demo reports, and Python, scikit-learn, and SQL components to build interpretable and challenger PD models, select candidates on a pre-OOT calibration holdout, evaluate raw and recalibrated PDs on an untouched out-of-time sample, run fixed lending strategy scenarios, and monitor feature drift with Population Stability Index.

## Interview Pitch

I built this project to show how I think about credit risk models beyond generic machine learning accuracy. The workflow estimates borrower-level probability of default, evaluates whether the model ranks risk correctly using AUC, Gini, and KS, selects the candidate before OOT evaluation, recalibrates PDs on a later pre-OOT holdout, and monitors population drift using PSI. I also added fixed approval cutoff scenario outputs to show how calibrated PDs can support portfolio risk analysis without presenting the synthetic results as lending recommendations.

