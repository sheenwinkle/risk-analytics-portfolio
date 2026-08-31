# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and SQL credit risk PD modelling workflow with LendingClub ingestion, out-of-time validation, calibration analysis, and PSI monitoring for lending portfolio risk.

## Resume Bullets

- Built an end-to-end credit risk probability of default workflow in Python, covering LendingClub accepted-loans ingestion, data validation, feature engineering, out-of-time testing, model comparison, calibration review, and monitoring outputs.
- Benchmarked logistic regression against a random forest challenger model using ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix diagnostics.
- Designed PostgreSQL schemas and analytical SQL queries for customer, loan, and monthly performance data to support credit risk reporting and model development.
- Produced portfolio-ready model artefacts, including account-level PD predictions, calibration deciles, PSI drift reports, and a saved trained model.

## LinkedIn / GitHub Summary

This project demonstrates a bank-style credit risk modelling workflow for probability of default estimation. It includes a LendingClub raw-data adapter, synthetic demo reports, and Python, scikit-learn, and SQL components to build interpretable and challenger PD models, evaluate discrimination and calibration, validate model performance on an out-of-time sample, and monitor feature drift with Population Stability Index.

## Interview Pitch

I built this project to show how I think about credit risk models beyond generic machine learning accuracy. The workflow estimates borrower-level probability of default, evaluates whether the model ranks risk correctly using AUC, Gini, and KS, checks whether predicted PDs are calibrated against observed defaults, and monitors population drift using PSI. I used logistic regression as an interpretable baseline and a random forest as a challenger model, which mirrors how a model development or validation team might compare incumbent and alternative models.

