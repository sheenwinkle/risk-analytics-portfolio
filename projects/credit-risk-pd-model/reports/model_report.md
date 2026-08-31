# Credit Risk PD Model Report

## Executive Summary

- Best model by out-of-time ROC-AUC: `logistic_regression`.
- Discrimination: ROC-AUC 0.714, Gini 0.429, KS 0.362.
- Calibration: Brier score 0.197; largest absolute decile gap 32.2%.
- Stability: 1 material shift feature(s), 0 moderate shift feature(s); top PSI feature `interest_rate` (0.351).
- Explainability: top out-of-time permutation importance feature `credit_utilisation` (0.077 mean ROC-AUC decrease after permutation).
- Scorecard diagnostics: top development-sample Information Value feature `credit_utilisation` (0.179, medium).

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

## Feature Importance

Permutation importance measures the drop in out-of-time ROC-AUC when each input feature is shuffled, giving model-agnostic evidence for validation review.

| Feature | Mean ROC-AUC Drop | Std Dev |
| --- | --- | --- |
| credit_utilisation | 0.077 | 0.012 |
| debt_to_income | 0.056 | 0.014 |
| home_ownership | 0.053 | 0.007 |
| delinquencies_2y | 0.037 | 0.006 |
| annual_income | 0.022 | 0.007 |
| loan_amount | 0.016 | 0.009 |
| purpose | 0.011 | 0.006 |
| employment_length | 0.010 | 0.003 |
| loan_to_income | 0.001 | 0.001 |
| age | -0.000 | 0.000 |
| interest_rate | -0.002 | 0.004 |

## Information Value

Weight of Evidence and Information Value are calculated on the development sample for scorecard-style variable screening. WOE is ln(% good / % bad), where good is non-default and bad is default. Positive WOE indicates lower observed default risk than the development sample mix.

| Rank | Feature | Type | Bins | IV | Band |
| --- | --- | --- | --- | --- | --- |
| 1 | credit_utilisation | numeric | 5 | 0.179 | medium |
| 2 | interest_rate | numeric | 5 | 0.160 | medium |
| 3 | debt_to_income | numeric | 5 | 0.124 | medium |
| 4 | home_ownership | categorical | 4 | 0.078 | weak |
| 5 | loan_to_income | numeric | 5 | 0.065 | weak |
| 6 | loan_amount | numeric | 5 | 0.063 | weak |
| 7 | delinquencies_2y | numeric | 2 | 0.043 | weak |
| 8 | purpose | categorical | 6 | 0.034 | weak |
| 9 | age | numeric | 5 | 0.020 | weak |
| 10 | annual_income | numeric | 5 | 0.020 | not_predictive |
| 11 | employment_length | numeric | 5 | 0.015 | not_predictive |

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
