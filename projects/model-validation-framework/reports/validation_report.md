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
- Quantified uncertainty with DeLong, Wilson score, normal-mean, and paired intervals.
- Reviewed rank-based calibration deciles and monthly performance.
- Backtested calibration and discrimination by origination quarter and business segment.
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

## Metric Uncertainty

| model_name | score_version | metric | estimate | lower_bound | upper_bound | confidence_level | method | observations | defaults |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | recalibrated | roc_auc | 0.710412 | 0.668892 | 0.751933 | 0.950000 | delong | 994 | 173 |
| logistic_regression | recalibrated | observed_default_rate | 0.174044 | 0.151741 | 0.198857 | 0.950000 | wilson_score | 994 | 173 |
| logistic_regression | recalibrated | mean_predicted_pd | 0.096947 | 0.093646 | 0.100247 | 0.950000 | normal_mean | 994 | 173 |
| logistic_regression | recalibrated | calibration_gap | -0.077097 | -0.099930 | -0.054265 | 0.950000 | paired_normal | 994 | 173 |
| logistic_regression | recalibrated | brier_score | 0.140704 | 0.122818 | 0.158591 | 0.950000 | normal_mean | 994 | 173 |

## Vintage Performance

| model_name | score_version | vintage_quarter | observations | portfolio_share | defaults | non_defaults | expected_defaults | mean_pd | observed_default_rate | observed_default_rate_lower | observed_default_rate_upper | calibration_gap | calibration_gap_lower | calibration_gap_upper | expected_to_observed_ratio | roc_auc | roc_auc_lower | roc_auc_upper | ks | discrimination_status | reliability_status | calibration_signal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | recalibrated | 2022Q1 | 243 | 0.244467 | 48 | 195 | 24.663133 | 0.101494 | 0.197531 | 0.152348 | 0.252128 | -0.096036 | -0.144367 | -0.047706 | 0.513815 | 0.730342 | 0.652024 | 0.808660 | 0.407692 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | 2022Q2 | 231 | 0.232394 | 42 | 189 | 22.211076 | 0.096152 | 0.181818 | 0.137420 | 0.236626 | -0.085666 | -0.133948 | -0.037384 | 0.528835 | 0.729655 | 0.645693 | 0.813616 | 0.402116 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | 2022Q3 | 258 | 0.259557 | 40 | 218 | 23.677848 | 0.091775 | 0.155039 | 0.115969 | 0.204230 | -0.063264 | -0.105685 | -0.020843 | 0.591946 | 0.726032 | 0.636388 | 0.815676 | 0.380963 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | 2022Q4 | 262 | 0.263581 | 43 | 219 | 25.813053 | 0.098523 | 0.164122 | 0.124188 | 0.213763 | -0.065599 | -0.109753 | -0.021446 | 0.600304 | 0.644685 | 0.560427 | 0.728943 | 0.233514 | available | sufficient | pd_underprediction |

## Segment Performance

| model_name | score_version | segment_dimension | segment_value | observations | portfolio_share | defaults | non_defaults | expected_defaults | mean_pd | observed_default_rate | observed_default_rate_lower | observed_default_rate_upper | calibration_gap | calibration_gap_lower | calibration_gap_upper | expected_to_observed_ratio | roc_auc | roc_auc_lower | roc_auc_upper | ks | discrimination_status | reliability_status | calibration_signal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | recalibrated | home_ownership | mortgage | 374 | 0.376258 | 49 | 325 | 29.205146 | 0.078089 | 0.131016 | 0.100539 | 0.168996 | -0.052927 | -0.086251 | -0.019604 | 0.596023 | 0.698776 | 0.613426 | 0.784125 | 0.367724 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | home_ownership | other | 28 | 0.028169 | 6 | 22 | 2.079739 | 0.074276 | 0.214286 | 0.102125 | 0.395386 | -0.140009 | -0.291136 | 0.011117 | 0.346623 | 0.803030 | 0.614856 | 0.991204 | 0.530303 | available | limited_sample | not_statistically_distinct |
| logistic_regression | recalibrated | home_ownership | own | 149 | 0.149899 | 17 | 132 | 13.357194 | 0.089646 | 0.114094 | 0.072466 | 0.175120 | -0.024448 | -0.074421 | 0.025524 | 0.785717 | 0.690731 | 0.558493 | 0.822969 | 0.359180 | available | sufficient | not_statistically_distinct |
| logistic_regression | recalibrated | home_ownership | rent | 443 | 0.445674 | 101 | 342 | 51.723031 | 0.116756 | 0.227991 | 0.191360 | 0.269299 | -0.111235 | -0.149217 | -0.073252 | 0.512109 | 0.680186 | 0.622891 | 0.737482 | 0.283249 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | purpose | car | 155 | 0.155936 | 27 | 128 | 14.782678 | 0.095372 | 0.174194 | 0.122567 | 0.241579 | -0.078821 | -0.138135 | -0.019508 | 0.547507 | 0.621528 | 0.502913 | 0.740142 | 0.254919 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | purpose | debt_consolidation | 461 | 0.463783 | 82 | 379 | 45.265393 | 0.098190 | 0.177874 | 0.145671 | 0.215401 | -0.079685 | -0.113222 | -0.046147 | 0.552017 | 0.746959 | 0.688904 | 0.805014 | 0.407877 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | purpose | home_improvement | 140 | 0.140845 | 19 | 121 | 12.387882 | 0.088485 | 0.135714 | 0.088635 | 0.202251 | -0.047229 | -0.102297 | 0.007838 | 0.651994 | 0.724663 | 0.597578 | 0.851748 | 0.452806 | available | sufficient | not_statistically_distinct |
| logistic_regression | recalibrated | purpose | medical | 56 | 0.056338 | 13 | 43 | 4.794743 | 0.085620 | 0.232143 | 0.140994 | 0.357682 | -0.146522 | -0.255499 | -0.037546 | 0.368826 | 0.738819 | 0.604490 | 0.873149 | 0.450805 | available | sufficient | pd_underprediction |
| logistic_regression | recalibrated | purpose | other | 112 | 0.112676 | 15 | 97 | 10.225256 | 0.091297 | 0.133929 | 0.082871 | 0.209265 | -0.042632 | -0.104031 | 0.018768 | 0.681684 | 0.650859 | 0.498572 | 0.803146 | 0.321649 | available | sufficient | not_statistically_distinct |
| logistic_regression | recalibrated | purpose | small_business | 70 | 0.070423 | 17 | 53 | 8.909159 | 0.127274 | 0.242857 | 0.157519 | 0.354950 | -0.115583 | -0.214417 | -0.016750 | 0.524068 | 0.655938 | 0.513693 | 0.798183 | 0.394007 | available | sufficient | pd_underprediction |

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
| limited_feature_replication | medium | Independent validation consumes frozen scores, outcomes, and two business segmentation fields rather than the full development feature set. | Add feature-level replication and challenger rebuild testing in a later slice. |
