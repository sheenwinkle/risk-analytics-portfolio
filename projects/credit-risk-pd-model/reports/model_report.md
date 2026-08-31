# Credit Risk PD Model Report

## Executive Summary

- Selected model by pre-OOT calibration holdout ROC-AUC: `logistic_regression`.
- Discrimination: OOT recalibrated ROC-AUC 0.710, Gini 0.421, KS 0.342.
- PD recalibration: OOT recalibrated Brier score 0.141; largest absolute decile gap 17.2%.
- Stability: 1 material shift feature(s), 0 moderate shift feature(s); top PSI feature `interest_rate` (0.347).
- Explainability: top out-of-time permutation importance feature `credit_utilisation` (0.090 mean ROC-AUC decrease after permutation).
- Scorecard diagnostics: top development-sample Information Value feature `credit_utilisation` (0.213, medium).

## Model Performance

Model selection occurred before OOT evaluation: candidates were trained on the earlier model-development sample and selected by ROC-AUC on the later pre-OOT calibration holdout.
Precision, recall, accuracy, and confusion counts use the fixed configured threshold of 15.0%; it is not tuned on OOT outcomes.

| Model | Dev Accounts | Holdout Accounts | Dev End | Holdout Start | Holdout ROC-AUC | Selected |
| --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 3032 | 974 | 2020-12-01 | 2021-01-01 | 0.670 | yes |
| random_forest | 3032 | 974 | 2020-12-01 | 2021-01-01 | 0.642 | no |

| Model | Score | Threshold | ROC-AUC | Gini | KS | Brier | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | raw | 15.0% | 0.710 | 0.421 | 0.342 | 0.194 | 18.0% | 99.4% |
| logistic_regression | recalibrated | 15.0% | 0.710 | 0.421 | 0.342 | 0.141 | 37.9% | 33.5% |
| random_forest | raw | 15.0% | 0.687 | 0.373 | 0.303 | 0.188 | 17.8% | 99.4% |

## PD Recalibration

Logistic recalibration is fitted only on the pre-OOT calibration holdout. Raw and recalibrated PD diagnostics below are calculated on the untouched OOT sample.
Fitted transform: logit(PD_recalibrated) = -2.068 + 0.795 x logit(PD_raw).

| Score | Intercept | Slope | Brier | Log Loss | Mean PD | Observed Default Rate |
| --- | --- | --- | --- | --- | --- | --- |
| raw | -1.344 | 1.087 | 0.194 | 0.571 | 41.6% | 17.4% |
| recalibrated | 1.482 | 1.367 | 0.141 | 0.452 | 9.7% | 17.4% |

## Calibration Review

Decile calibration runs from D01 (lowest predicted PD) to D10 (highest). Positive gaps indicate predicted PD is above the realised default rate.

| PD Bucket | Accounts | Predicted PD | Observed Default Rate | Defaults | Gap |
| --- | --- | --- | --- | --- | --- |
| D01 | 100 | 3.2% | 2.0% | 2 | 1.2% |
| D02 | 99 | 4.8% | 10.1% | 10 | -5.4% |
| D03 | 99 | 5.8% | 10.1% | 10 | -4.3% |
| D04 | 100 | 6.8% | 8.0% | 8 | -1.2% |
| D05 | 99 | 7.9% | 11.1% | 11 | -3.2% |
| D06 | 99 | 9.3% | 17.2% | 17 | -7.9% |
| D07 | 100 | 10.8% | 17.0% | 17 | -6.2% |
| D08 | 99 | 12.5% | 29.3% | 29 | -16.8% |
| D09 | 99 | 15.1% | 32.3% | 32 | -17.2% |
| D10 | 100 | 21.0% | 37.0% | 37 | -16.0% |

## Lending Strategy

Approval cutoffs are fixed scenario rows, not recommendations. Expected loss is calculated as the sum of recalibrated PD x LGD x EAD for approved accounts, using loan_amount as an EAD proxy.

| Max PD | LGD | Approved | Approval Rate | Approved Default Rate | Approved Exposure | Expected Loss | Expected Loss Rate | Rejected Default Capture |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10.0% | 45.0% | 593 | 59.7% | 9.8% | 10260703 | 293936 | 2.9% | 66.5% |
| 15.0% | 45.0% | 841 | 84.6% | 13.7% | 15700049 | 588971 | 3.8% | 33.5% |
| 20.0% | 45.0% | 948 | 95.4% | 16.1% | 18608894 | 811795 | 4.4% | 11.6% |
| 25.0% | 45.0% | 977 | 98.3% | 16.8% | 19635333 | 914081 | 4.7% | 5.2% |

## Feature Importance

Permutation importance measures the drop in out-of-time ROC-AUC when each input feature is shuffled, giving model-agnostic evidence for validation review.

| Feature | Mean ROC-AUC Drop | Std Dev |
| --- | --- | --- |
| credit_utilisation | 0.090 | 0.015 |
| debt_to_income | 0.053 | 0.013 |
| home_ownership | 0.046 | 0.006 |
| annual_income | 0.044 | 0.011 |
| loan_amount | 0.042 | 0.013 |
| delinquencies_2y | 0.031 | 0.006 |
| loan_to_income | 0.014 | 0.007 |
| purpose | 0.010 | 0.006 |
| employment_length | 0.007 | 0.002 |
| age | -0.001 | 0.000 |
| interest_rate | -0.003 | 0.005 |

## Information Value

Weight of Evidence and Information Value are calculated on the development sample for scorecard-style variable screening. WOE is ln(% good / % bad), where good is non-default and bad is default. Positive WOE indicates lower observed default risk than the development sample mix.

| Rank | Feature | Type | Bins | IV | Band |
| --- | --- | --- | --- | --- | --- |
| 1 | credit_utilisation | numeric | 5 | 0.213 | medium |
| 2 | interest_rate | numeric | 5 | 0.156 | medium |
| 3 | debt_to_income | numeric | 5 | 0.115 | medium |
| 4 | delinquencies_2y | numeric | 3 | 0.103 | medium |
| 5 | loan_amount | numeric | 5 | 0.089 | weak |
| 6 | loan_to_income | numeric | 5 | 0.085 | weak |
| 7 | home_ownership | categorical | 4 | 0.082 | weak |
| 8 | annual_income | numeric | 5 | 0.051 | weak |
| 9 | purpose | categorical | 6 | 0.024 | weak |
| 10 | age | numeric | 5 | 0.019 | not_predictive |
| 11 | employment_length | numeric | 5 | 0.010 | not_predictive |

## Population Stability

PSI highlights feature drift between the development and out-of-time samples, supporting model monitoring and validation review.

| Feature | PSI | Status |
| --- | --- | --- |
| interest_rate | 0.347 | material_shift |
| credit_utilisation | 0.023 | stable |
| annual_income | 0.017 | stable |
| employment_length | 0.013 | stable |
| loan_amount | 0.011 | stable |
| delinquencies_2y | 0.009 | stable |
| debt_to_income | 0.009 | stable |
| age | 0.008 | stable |
| loan_to_income | 0.008 | stable |
