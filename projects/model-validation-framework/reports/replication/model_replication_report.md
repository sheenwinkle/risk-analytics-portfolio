# Independent Model Replication

## Scope

Project 3 independently rebuilds both Project 1 candidates from the governed pre-OOT development extract. It does not import Project 1 model code.

## Outcome

- Replicated selected model: `logistic_regression`.
- Selection and AUC replication outcome: **PASS**.
- Parameter and importance replication outcome: **PASS**.
- Maximum absolute AUC delta: 0.0000000000.
- Maximum absolute parameter delta: 0.0000000000.

## Model Replication

| model | reference_calibration_auc | replicated_calibration_auc | auc_absolute_delta | auc_tolerance | reference_selected | replicated_selected | selection_matches | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 0.6700044209 | 0.6700044209 | 0.0000000000 | 0.0000000100 | True | True | True | pass |
| random_forest | 0.6424071618 | 0.6424071618 | 0.0000000000 | 0.0000000100 | False | False | True | pass |

## Parameter Stability

| model | parameter_type | reference_features | replicated_features | feature_set_matches | mean_absolute_delta | max_absolute_delta | absolute_rank_correlation | coefficient_sign_agreement_rate | parameter_tolerance | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | standardized_coefficient | 19 | 19 | True | 0.0000000000 | 0.0000000000 | 1.0000000000 | 1.0000000000 | 0.0000000100 | pass |
| random_forest | impurity_importance | 19 | 19 | True | 0.0000000000 | 0.0000000000 | 1.0000000000 | N/A | 0.0000000100 | pass |

## Governance Notes

- Development and calibration roles are temporally separated before fitting.
- AUC is recomputed on the frozen pre-OOT calibration holdout.
- Standardized logistic coefficients and random-forest impurity importances are reconciled.
- Borrower-level development records remain local and are not written to this report directory.
