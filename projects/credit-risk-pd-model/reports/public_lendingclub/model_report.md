# Credit Risk PD Model Report

## Executive Summary

- Selected model by pre-OOT calibration holdout ROC-AUC: `random_forest`.
- Discrimination: OOT recalibrated ROC-AUC 0.700, Gini 0.400, KS 0.292.
- PD recalibration: OOT recalibrated Brier score 0.155; largest absolute decile gap 7.1%.
- Stability: 0 material shift feature(s), 1 moderate shift feature(s); top PSI feature `credit_utilisation` (0.188).
- Explainability: top out-of-time permutation importance feature `interest_rate` (0.137 mean ROC-AUC decrease after permutation).
- Scorecard diagnostics: top development-sample Information Value feature `interest_rate` (0.422, strong).
- Credit decision strategy: `advance_challenger` after a pre-OOT selected 20.0% challenger was evaluated on untouched OOT outcomes.

## Model Performance

Model selection occurred before OOT evaluation: candidates were trained on the earlier model-development sample and selected by ROC-AUC on the later pre-OOT calibration holdout.
Precision, recall, accuracy, and confusion counts use the fixed configured threshold of 15.0%; it is not tuned on OOT outcomes.

| Model | Dev Accounts | Holdout Accounts | Dev End | Holdout Start | Holdout ROC-AUC | Selected |
| --- | --- | --- | --- | --- | --- | --- |
| random_forest | 829355 | 293105 | 2015-12-01 | 2016-01-01 | 0.702 | yes |
| logistic_regression | 829355 | 293105 | 2015-12-01 | 2016-01-01 | 0.699 | no |

| Model | Score | Threshold | ROC-AUC | Gini | KS | Brier | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | raw | 15.0% | 0.690 | 0.381 | 0.280 | 0.234 | 21.4% | 99.9% |
| random_forest | raw | 15.0% | 0.700 | 0.400 | 0.292 | 0.208 | 22.2% | 99.4% |
| random_forest | recalibrated | 15.0% | 0.700 | 0.400 | 0.292 | 0.155 | 26.8% | 89.2% |

## PD Recalibration

Logistic recalibration is fitted only on the pre-OOT calibration holdout. Raw and recalibrated PD diagnostics below are calculated on the untouched OOT sample.
Fitted transform: logit(PD_recalibrated) = -1.027 + 0.980 x logit(PD_raw).

| Score | Intercept | Slope | Brier | Log Loss | Mean PD | Observed Default Rate |
| --- | --- | --- | --- | --- | --- | --- |
| raw | -1.192 | 0.966 | 0.208 | 0.602 | 43.9% | 21.3% |
| recalibrated | -0.180 | 0.985 | 0.155 | 0.477 | 23.9% | 21.3% |

## Calibration Review

Decile calibration runs from D01 (lowest predicted PD) to D10 (highest). Positive gaps indicate predicted PD is above the realised default rate.

| PD Bucket | Accounts | Predicted PD | Observed Default Rate | Defaults | Gap |
| --- | --- | --- | --- | --- | --- |
| D01 | 22564 | 6.0% | 4.0% | 902 | 2.0% |
| D02 | 22564 | 10.4% | 8.3% | 1865 | 2.1% |
| D03 | 22564 | 13.7% | 11.7% | 2650 | 2.0% |
| D04 | 22564 | 16.8% | 15.5% | 3493 | 1.3% |
| D05 | 22564 | 20.0% | 18.2% | 4109 | 1.8% |
| D06 | 22563 | 23.6% | 21.8% | 4918 | 1.8% |
| D07 | 22564 | 27.6% | 25.8% | 5812 | 1.8% |
| D08 | 22564 | 32.3% | 30.1% | 6790 | 2.2% |
| D09 | 22564 | 38.8% | 34.5% | 7779 | 4.3% |
| D10 | 22564 | 50.2% | 43.1% | 9725 | 7.1% |

## Lending Strategy

Approval cutoffs are fixed scenario rows, not recommendations. Expected loss is calculated as the sum of recalibrated PD x LGD x EAD for approved accounts, using loan_amount as an EAD proxy.

| Max PD | LGD | Approved | Approval Rate | Approved Default Rate | Approved Exposure | Expected Loss | Expected Loss Rate | Rejected Default Capture |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10.0% | 45.0% | 31344 | 13.9% | 4.8% | 399178175 | 12496463 | 3.1% | 96.9% |
| 15.0% | 45.0% | 65820 | 29.2% | 7.9% | 800339550 | 35205067 | 4.4% | 89.2% |
| 20.0% | 45.0% | 101696 | 45.1% | 10.7% | 1249726975 | 70570585 | 5.6% | 77.3% |
| 25.0% | 45.0% | 132575 | 58.8% | 13.0% | 1671065875 | 113188261 | 6.8% | 64.0% |

## Pre-OOT Champion-Challenger Strategy

The growth challenger is selected only on the pre-OOT calibration holdout by maximising approval rate subject to observed bad-rate and expected-loss-rate constraints. The cutoff is then frozen before OOT evaluation.
The same pre-OOT holdout supports recalibration and policy development; this can make selection evidence optimistic, but it does not contaminate the frozen OOT acceptance decision.
This is a retrospective paired champion-challenger backtest, not a randomized A/B test, so it quantifies historical policy impact without making a causal claim.
Decision: **ADVANCE CHALLENGER**.
The challenger produced 35876 incremental approvals and 449387425 incremental exposure. Expected credit contribution changed by 14651204, while the realised contribution proxy changed by 17032983 (95.0% paired bootstrap interval 16062200 to 18019470).
Credit contribution is a deliberately simplified one-year proxy: interest income less PD x LGD x EAD for expected results, and interest income less observed-default x LGD x EAD for realised results. It excludes funding, operating costs, prepayment, and timing.

### Pre-OOT Selection

| Max PD | Incumbent | Approval Rate | Observed Bad Rate | Expected Loss Rate | Eligible | Selected |
| --- | --- | --- | --- | --- | --- | --- |
| 10.0% | no | 13.7% | 6.1% | 3.2% | no | no |
| 15.0% | yes | 31.0% | 9.7% | 4.5% | no | no |
| 20.0% | no | 48.6% | 12.7% | 5.7% | yes | yes |
| 25.0% | no | 62.1% | 15.0% | 6.7% | no | no |

### OOT Policy Comparison

| Policy | Max PD | Approved | Approval Rate | Observed Bad Rate | Approved Exposure | Expected Contribution | Realised Contribution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| incumbent | 15.0% | 65820 | 29.2% | 7.9% | 800339550 | 30110272 | 34785775 |
| challenger | 20.0% | 101696 | 45.1% | 10.7% | 1249726975 | 44761476 | 51818757 |

### Acceptance Checks

| Check | Value | Threshold | CI Lower | CI Upper | Status |
| --- | --- | --- | --- | --- | --- |
| pre_oot_selection_constraints | 1.000 | 1.000 | N/A | N/A | pass |
| oot_approval_uplift | 0.159 | 0.000 | N/A | N/A | pass |
| oot_expected_credit_contribution | 14651204.194 | 0.000 | N/A | N/A | pass |
| oot_bad_rate_increase | 0.029 | 0.030 | N/A | N/A | pass |
| oot_realized_credit_contribution | 17032982.820 | 0.000 | 16062199.822 | 18019469.559 | pass |

## Feature Importance

Permutation importance measures the drop in out-of-time ROC-AUC when each input feature is shuffled, giving model-agnostic evidence for validation review.

| Feature | Mean ROC-AUC Drop | Std Dev |
| --- | --- | --- |
| interest_rate | 0.137 | 0.002 |
| home_ownership | 0.009 | 0.000 |
| loan_to_income | 0.008 | 0.000 |
| debt_to_income | 0.006 | 0.000 |
| loan_amount | 0.004 | 0.000 |
| purpose | 0.002 | 0.000 |
| employment_length | 0.001 | 0.000 |
| annual_income | 0.001 | 0.000 |
| credit_utilisation | 0.001 | 0.000 |
| delinquencies_2y | 0.000 | 0.000 |
| age | 0.000 | 0.000 |

## Information Value

Weight of Evidence and Information Value are calculated on the development sample for scorecard-style variable screening. WOE is ln(% good / % bad), where good is non-default and bad is default. Positive WOE indicates lower observed default risk than the development sample mix.

| Rank | Feature | Type | Bins | IV | Band |
| --- | --- | --- | --- | --- | --- |
| 1 | interest_rate | numeric | 5 | 0.422 | strong |
| 2 | loan_to_income | numeric | 6 | 0.120 | medium |
| 3 | debt_to_income | numeric | 6 | 0.070 | weak |
| 4 | loan_amount | numeric | 5 | 0.035 | weak |
| 5 | annual_income | numeric | 6 | 0.030 | weak |
| 6 | purpose | categorical | 14 | 0.021 | weak |
| 7 | home_ownership | categorical | 4 | 0.021 | weak |
| 8 | credit_utilisation | numeric | 6 | 0.021 | weak |
| 9 | employment_length | numeric | 5 | 0.006 | not_predictive |
| 10 | delinquencies_2y | numeric | 2 | 0.000 | not_predictive |
| 11 | age | numeric | 1 | 0.000 | not_predictive |

## Population Stability

PSI highlights feature drift between the development and out-of-time samples, supporting model monitoring and validation review.

| Feature | PSI | Status |
| --- | --- | --- |
| credit_utilisation | 0.188 | moderate_shift |
| interest_rate | 0.097 | stable |
| loan_to_income | 0.048 | stable |
| loan_amount | 0.040 | stable |
| employment_length | 0.015 | stable |
| annual_income | 0.010 | stable |
| debt_to_income | 0.009 | stable |
| delinquencies_2y | 0.000 | stable |
| age | N/A | not_available |
