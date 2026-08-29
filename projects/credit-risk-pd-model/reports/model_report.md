# Credit Risk PD Model Report

## Executive Summary

- Best model by out-of-time ROC-AUC: `logistic_regression`.
- Discrimination: ROC-AUC 0.714, Gini 0.429, KS 0.362.
- Calibration: Brier score 0.197; largest absolute decile gap 32.2%.
- Stability: 1 material shift feature(s), 0 moderate shift feature(s); top PSI feature `interest_rate` (0.351).

## Model Performance

| Model | ROC-AUC | Gini | KS | Brier | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 0.714 | 0.429 | 0.362 | 0.197 | 31.5% | 59.0% |
| random_forest | 0.698 | 0.396 | 0.337 | 0.192 | 32.7% | 49.1% |

## Calibration Review

Decile calibration compares average predicted PD with observed default rate. Positive gaps indicate predicted PD is above the realised default rate.

| PD Bucket | Accounts | Predicted PD | Observed Default Rate | Defaults | Gap |
| --- | --- | --- | --- | --- | --- |
| (0.08549999999999999, 0.219] | 100 | 17.3% | 4.0% | 4 | 13.3% |
| (0.219, 0.276] | 99 | 24.9% | 9.1% | 9 | 15.8% |
| (0.276, 0.324] | 99 | 29.9% | 2.0% | 2 | 27.8% |
| (0.324, 0.367] | 100 | 34.5% | 15.0% | 15 | 19.5% |
| (0.367, 0.411] | 99 | 38.8% | 13.1% | 13 | 25.6% |
| (0.411, 0.461] | 99 | 43.8% | 14.1% | 14 | 29.6% |
| (0.461, 0.513] | 100 | 48.9% | 20.0% | 20 | 28.9% |
| (0.513, 0.57] | 99 | 54.3% | 28.3% | 28 | 26.0% |
| (0.57, 0.644] | 99 | 60.6% | 29.3% | 29 | 31.3% |
| (0.644, 0.937] | 100 | 71.2% | 39.0% | 39 | 32.2% |

## Population Stability

PSI highlights feature drift between the development and out-of-time samples, supporting model monitoring and validation review.

| Feature | PSI | Status |
| --- | --- | --- |
| interest_rate | 0.351 | material_shift |
| credit_utilisation | 0.016 | stable |
| age | 0.011 | stable |
| annual_income | 0.011 | stable |
| employment_length | 0.009 | stable |
| delinquencies_2y | 0.008 | stable |
| debt_to_income | 0.008 | stable |
| loan_amount | 0.008 | stable |
| loan_to_income | 0.007 | stable |
