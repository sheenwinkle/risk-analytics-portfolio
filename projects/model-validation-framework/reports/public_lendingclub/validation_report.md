# PD Model Validation Case Study

## Scope and Disclaimer

Educational portfolio case study. This report is not a regulatory approval, accounting opinion, or production-use decision.

## Executive Summary

- Selected model: random_forest (recalibrated score `recalibrated_pd`).
- Observations: 225639. Defaults: 48043.
- Mean predicted PD: 0.239255. Observed default rate: 0.212920.
- AUC: 0.699887. KS: 0.292493.
- Absolute calibration gap: 0.026335.
- PSI period split: 2017-01-01 to 2017-12-01 versus 2018-01-01 to 2018-12-01.
- PSI: 0.016656.
- Overall policy outcome: **WARNING**.

## Methodology

- Reperformed AUC, Gini, tie-safe KS, Brier score, and portfolio calibration.
- Reviewed rank-based calibration deciles and monthly performance.
- Measured score drift with reference-period quantile midpoint PSI bins.
- Compared the selected recalibrated incumbent with the unselected raw challenger.

## Policy Checks

| check | metric_value | direction | green_threshold | warning_threshold | status | detail |
| --- | --- | --- | --- | --- | --- | --- |
| auc | 0.699887 | higher_is_better | 0.700000 | 0.600000 | warning | Selected recalibrated model discrimination by ROC AUC. |
| ks | 0.292493 | higher_is_better | 0.300000 | 0.200000 | warning | Selected recalibrated model separation by KS statistic. |
| absolute_calibration_gap | 0.026335 | lower_is_better | 0.010000 | 0.030000 | warning | Absolute gap between observed default rate and mean recalibrated PD. |
| population_stability_index | 0.016656 | lower_is_better | 0.100000 | 0.250000 | pass | PSI comparing current score distribution with the reference period. |
| challenger_auc_margin | -0.009411 | lower_is_better | 0.010000 | 0.030000 | pass | Unselected raw challenger AUC minus selected recalibrated incumbent AUC. |

## Calibration by Decile

| model_name | score_version | decile | observations | defaults | expected_defaults | mean_pd | observed_default_rate | calibration_gap | expected_to_observed_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest | recalibrated | 1 | 22564 | 902 | 1353.862632 | 0.060001 | 0.039975 | 0.020026 | 1.500956 |
| random_forest | recalibrated | 2 | 22564 | 1865 | 2339.564112 | 0.103686 | 0.082654 | 0.021032 | 1.254458 |
| random_forest | recalibrated | 3 | 22564 | 2650 | 3092.666298 | 0.137062 | 0.117444 | 0.019618 | 1.167044 |
| random_forest | recalibrated | 4 | 22564 | 3493 | 3788.828772 | 0.167915 | 0.154804 | 0.013111 | 1.084692 |
| random_forest | recalibrated | 5 | 22564 | 4109 | 4513.342194 | 0.200024 | 0.182104 | 0.017920 | 1.098404 |
| random_forest | recalibrated | 6 | 22564 | 4919 | 5317.348773 | 0.235656 | 0.218002 | 0.017654 | 1.080982 |
| random_forest | recalibrated | 7 | 22564 | 5811 | 6219.486097 | 0.275638 | 0.257534 | 0.018103 | 1.070295 |
| random_forest | recalibrated | 8 | 22564 | 6790 | 7280.942166 | 0.322680 | 0.300922 | 0.021758 | 1.072304 |
| random_forest | recalibrated | 9 | 22564 | 7780 | 8750.092326 | 0.387790 | 0.344797 | 0.042993 | 1.124691 |
| random_forest | recalibrated | 10 | 22563 | 9724 | 11329.166724 | 0.502113 | 0.430971 | 0.071142 | 1.165073 |

## Stability Summary

| model_name | score_version | reference_start | reference_end | current_start | current_end | reference_observations | current_observations | requested_bins | effective_bins | binning_method | population_stability_index |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest | recalibrated | 2017-01-01 | 2017-12-01 | 2018-01-01 | 2018-12-01 | 169321 | 56318 | 10 | 10 | reference_quantile_midpoint | 0.016656 |

## Benchmark Comparison

| comparison | baseline_model | baseline_score_version | baseline_score_column | benchmark_model | benchmark_score_version | benchmark_score_column | baseline_auc | benchmark_auc | auc_delta | baseline_ks | benchmark_ks | ks_delta | baseline_absolute_calibration_gap | benchmark_absolute_calibration_gap | absolute_calibration_gap_delta | baseline_brier_score | benchmark_brier_score | brier_score_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| selected_recalibrated_vs_unselected_raw_challenger | random_forest | recalibrated | recalibrated_pd | logistic_regression | raw | logistic_regression_pd | 0.699887 | 0.690475 | -0.009411 | 0.292493 | 0.279524 | -0.012969 | 0.026335 | 0.268691 | 0.242355 | 0.154725 | 0.234099 | 0.079373 |
| selected_raw_vs_selected_recalibrated | random_forest | raw | random_forest_pd | random_forest | recalibrated | recalibrated_pd | 0.699887 | 0.699887 | 0.000000 | 0.292493 | 0.292493 | 0.000000 | 0.225792 | 0.026335 | -0.199456 | 0.208470 | 0.154725 | -0.053745 |

## Findings

| status | check | finding | recommended_action |
| --- | --- | --- | --- |
| warning | auc | ROC-AUC reached warning status at 0.699887. | Review rank ordering, reject-inference assumptions, and candidate segmentation. |
| warning | ks | KS statistic reached warning status at 0.292493. | Inspect score distribution overlap and consider model redevelopment triggers. |
| warning | absolute_calibration_gap | Absolute calibration gap reached warning status at 0.026335. | Re-estimate calibration on a fresh holdout and review portfolio mix shift. |

## Limitations

| limitation | severity | description | mitigation |
| --- | --- | --- | --- |
| accepted_loan_selection_bias | medium | Public LendingClub data contains accepted loans rather than all applications. | Do not generalise approval-strategy results to the full applicant population. |
| terminal_outcome_proxy | medium | Observed defaults use a terminal-outcome proxy rather than serviced account history. | Replace with contractual default definitions and observation windows. |
| limited_oot_horizon | medium | Out-of-time validation covers 2017-01-01 to 2018-12-01. | Extend monitoring across additional vintages when data is available. |
| score_only_independent_validation | medium | Independent validation consumes scores and outcomes, not full development features. | Add feature-level replication and challenger rebuild testing in a later slice. |
