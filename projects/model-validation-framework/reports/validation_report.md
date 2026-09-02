# PD Model Validation Case Study

## Scope and Disclaimer

Educational portfolio case study. This report is not a regulatory approval, accounting opinion, or production-use decision.

## Executive Summary

- Selected model: logistic_regression (recalibrated score `recalibrated_pd`).
- Observations: 994. Defaults: 173.
- Mean predicted PD: 0.096947. Observed default rate: 0.174044.
- AUC: 0.710412. KS: 0.341611.
- Absolute calibration gap: 0.077097.
- PSI period split: 2022-01-01 to 2022-06-01 versus 2022-07-01 to 2022-12-01.
- PSI: 0.070689.
- Overall policy outcome: **FAIL**.

## Methodology

- Reperformed AUC, Gini, tie-safe KS, Brier score, and portfolio calibration.
- Reviewed rank-based calibration deciles and monthly performance.
- Measured score drift with reference-period quantile midpoint PSI bins.
- Compared the selected recalibrated incumbent with the unselected raw challenger.

## Policy Checks

| check | metric_value | direction | green_threshold | warning_threshold | status | detail |
| --- | --- | --- | --- | --- | --- | --- |
| auc | 0.710412 | higher_is_better | 0.700000 | 0.600000 | pass | Selected recalibrated model discrimination by ROC AUC. |
| ks | 0.341611 | higher_is_better | 0.300000 | 0.200000 | pass | Selected recalibrated model separation by KS statistic. |
| absolute_calibration_gap | 0.077097 | lower_is_better | 0.010000 | 0.030000 | fail | Absolute gap between observed default rate and mean recalibrated PD. |
| population_stability_index | 0.070689 | lower_is_better | 0.100000 | 0.250000 | pass | PSI comparing current score distribution with the reference period. |
| challenger_auc_margin | -0.023896 | lower_is_better | 0.010000 | 0.030000 | pass | Unselected raw challenger AUC minus selected recalibrated incumbent AUC. |

## Calibration by Decile

| model_name | score_version | decile | observations | defaults | expected_defaults | mean_pd | observed_default_rate | calibration_gap | expected_to_observed_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | recalibrated | 1 | 100 | 2 | 3.200770 | 0.032008 | 0.020000 | 0.012008 | 1.600385 |
| logistic_regression | recalibrated | 2 | 99 | 10 | 4.703400 | 0.047509 | 0.101010 | -0.053501 | 0.470340 |
| logistic_regression | recalibrated | 3 | 100 | 10 | 5.783115 | 0.057831 | 0.100000 | -0.042169 | 0.578312 |
| logistic_regression | recalibrated | 4 | 99 | 8 | 6.689084 | 0.067567 | 0.080808 | -0.013242 | 0.836136 |
| logistic_regression | recalibrated | 5 | 99 | 11 | 7.834467 | 0.079136 | 0.111111 | -0.031975 | 0.712224 |
| logistic_regression | recalibrated | 6 | 100 | 17 | 9.274181 | 0.092742 | 0.170000 | -0.077258 | 0.545540 |
| logistic_regression | recalibrated | 7 | 99 | 17 | 10.661184 | 0.107689 | 0.171717 | -0.064028 | 0.627128 |
| logistic_regression | recalibrated | 8 | 100 | 30 | 12.468729 | 0.124687 | 0.300000 | -0.175313 | 0.415624 |
| logistic_regression | recalibrated | 9 | 99 | 31 | 14.965746 | 0.151169 | 0.313131 | -0.161962 | 0.482766 |
| logistic_regression | recalibrated | 10 | 99 | 37 | 20.784434 | 0.209944 | 0.373737 | -0.163794 | 0.561741 |

## Stability Summary

| model_name | score_version | reference_start | reference_end | current_start | current_end | reference_observations | current_observations | requested_bins | effective_bins | binning_method | population_stability_index |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | recalibrated | 2022-01-01 | 2022-06-01 | 2022-07-01 | 2022-12-01 | 474 | 520 | 10 | 10 | reference_quantile_midpoint | 0.070689 |

## Benchmark Comparison

| comparison | baseline_model | baseline_score_version | baseline_score_column | benchmark_model | benchmark_score_version | benchmark_score_column | baseline_auc | benchmark_auc | auc_delta | baseline_ks | benchmark_ks | ks_delta | baseline_absolute_calibration_gap | benchmark_absolute_calibration_gap | absolute_calibration_gap_delta | baseline_brier_score | benchmark_brier_score | brier_score_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| selected_recalibrated_vs_unselected_raw_challenger | logistic_regression | recalibrated | recalibrated_pd | random_forest | raw | random_forest_pd | 0.710412 | 0.686517 | -0.023896 | 0.341611 | 0.303253 | -0.038357 | 0.077097 | 0.225330 | 0.148233 | 0.140704 | 0.188192 | 0.047488 |
| selected_raw_vs_selected_recalibrated | logistic_regression | raw | logistic_regression_pd | logistic_regression | recalibrated | recalibrated_pd | 0.710412 | 0.710412 | 0.000000 | 0.341611 | 0.341611 | 0.000000 | 0.241932 | 0.077097 | -0.164834 | 0.193814 | 0.140704 | -0.053109 |

## Findings

| status | check | finding | recommended_action |
| --- | --- | --- | --- |
| fail | absolute_calibration_gap | Absolute calibration gap reached fail status at 0.077097. | Re-estimate calibration on a fresh holdout and review portfolio mix shift. |

## Limitations

| limitation | severity | description | mitigation |
| --- | --- | --- | --- |
| synthetic_data | medium | Inputs are synthetic and cannot prove live portfolio performance. | Validate on locally downloaded public LendingClub data before production use. |
| terminal_outcome_proxy | medium | Observed defaults use a terminal-outcome proxy rather than serviced account history. | Replace with contractual default definitions and observation windows. |
| limited_oot_horizon | medium | Out-of-time validation covers 2022-01-01 to 2022-12-01. | Extend monitoring across additional vintages when data is available. |
| score_only_independent_validation | medium | Independent validation consumes scores and outcomes, not full development features. | Add feature-level replication and challenger rebuild testing in a later slice. |
