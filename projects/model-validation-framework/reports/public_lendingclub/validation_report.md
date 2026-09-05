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
- Quantified uncertainty with DeLong, Wilson score, normal-mean, and paired intervals.
- Reviewed rank-based calibration deciles and monthly performance.
- Backtested calibration and discrimination by origination quarter and business segment.
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

## Metric Uncertainty

| model_name | score_version | metric | estimate | lower_bound | upper_bound | confidence_level | method | observations | defaults |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest | recalibrated | roc_auc | 0.699887 | 0.697369 | 0.702405 | 0.950000 | delong | 225639 | 48043 |
| random_forest | recalibrated | observed_default_rate | 0.212920 | 0.211236 | 0.214614 | 0.950000 | wilson_score | 225639 | 48043 |
| random_forest | recalibrated | mean_predicted_pd | 0.239255 | 0.238715 | 0.239795 | 0.950000 | normal_mean | 225639 | 48043 |
| random_forest | recalibrated | calibration_gap | 0.026335 | 0.024716 | 0.027955 | 0.950000 | paired_normal | 225639 | 48043 |
| random_forest | recalibrated | brier_score | 0.154725 | 0.153889 | 0.155561 | 0.950000 | normal_mean | 225639 | 48043 |

## Vintage Performance

| model_name | score_version | vintage_quarter | observations | portfolio_share | defaults | non_defaults | expected_defaults | mean_pd | observed_default_rate | observed_default_rate_lower | observed_default_rate_upper | calibration_gap | calibration_gap_lower | calibration_gap_upper | expected_to_observed_ratio | roc_auc | roc_auc_lower | roc_auc_upper | ks | discrimination_status | reliability_status | calibration_signal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest | recalibrated | 2017Q1 | 46874 | 0.207739 | 10751 | 36123 | 11448.642944 | 0.244243 | 0.229360 | 0.225576 | 0.233188 | 0.014883 | 0.011233 | 0.018534 | 1.064891 | 0.693807 | 0.688384 | 0.699229 | 0.286454 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | 2017Q2 | 44492 | 0.197182 | 10591 | 33901 | 10710.107929 | 0.240720 | 0.238043 | 0.234108 | 0.242023 | 0.002677 | -0.001110 | 0.006464 | 1.011246 | 0.693281 | 0.687733 | 0.698828 | 0.276806 | available | sufficient | not_statistically_distinct |
| random_forest | recalibrated | 2017Q3 | 43854 | 0.194355 | 10498 | 33356 | 10790.464999 | 0.246054 | 0.239385 | 0.235414 | 0.243402 | 0.006669 | 0.002863 | 0.010475 | 1.027859 | 0.702792 | 0.697286 | 0.708298 | 0.298379 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | 2017Q4 | 34101 | 0.151131 | 7329 | 26772 | 8056.472721 | 0.236253 | 0.214920 | 0.210593 | 0.219312 | 0.021333 | 0.017170 | 0.025496 | 1.099259 | 0.707526 | 0.701117 | 0.713936 | 0.306180 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | 2018Q1 | 22530 | 0.099850 | 4387 | 18143 | 5196.679213 | 0.230656 | 0.194718 | 0.189600 | 0.199941 | 0.035938 | 0.030973 | 0.040902 | 1.184563 | 0.706791 | 0.698701 | 0.714880 | 0.314126 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | 2018Q2 | 18449 | 0.081763 | 3347 | 15102 | 4215.249106 | 0.228481 | 0.181419 | 0.175925 | 0.187046 | 0.047062 | 0.041716 | 0.052408 | 1.259411 | 0.709727 | 0.700533 | 0.718921 | 0.319513 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | 2018Q3 | 10309 | 0.045688 | 1018 | 9291 | 2422.485591 | 0.234987 | 0.098749 | 0.093139 | 0.104658 | 0.136239 | 0.130465 | 0.142013 | 2.379652 | 0.704183 | 0.688574 | 0.719792 | 0.310595 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | 2018Q4 | 5030 | 0.022292 | 122 | 4908 | 1145.197590 | 0.227673 | 0.024254 | 0.020352 | 0.028883 | 0.203419 | 0.198000 | 0.208838 | 9.386865 | 0.575502 | 0.528439 | 0.622566 | 0.186050 | available | sufficient | pd_overprediction |

## Segment Performance

| model_name | score_version | segment_dimension | segment_value | observations | portfolio_share | defaults | non_defaults | expected_defaults | mean_pd | observed_default_rate | observed_default_rate_lower | observed_default_rate_upper | calibration_gap | calibration_gap_lower | calibration_gap_upper | expected_to_observed_ratio | roc_auc | roc_auc_lower | roc_auc_upper | ks | discrimination_status | reliability_status | calibration_signal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest | recalibrated | home_ownership | mortgage | 113335 | 0.502285 | 19695 | 93640 | 24340.018143 | 0.214762 | 0.173777 | 0.171582 | 0.175994 | 0.040985 | 0.038848 | 0.043121 | 1.235848 | 0.694489 | 0.690645 | 0.698332 | 0.286284 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | home_ownership | other | 223 | 0.000988 | 40 | 183 | 54.763014 | 0.245574 | 0.179372 | 0.134580 | 0.235024 | 0.066202 | 0.017934 | 0.114470 | 1.369075 | 0.715301 | 0.628243 | 0.802359 | 0.365164 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | home_ownership | own | 27785 | 0.123139 | 6070 | 21715 | 6782.101036 | 0.244092 | 0.218463 | 0.213644 | 0.223360 | 0.025629 | 0.020927 | 0.030331 | 1.117315 | 0.678653 | 0.671381 | 0.685924 | 0.267469 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | home_ownership | rent | 84296 | 0.373588 | 22238 | 62058 | 22808.417901 | 0.270575 | 0.263808 | 0.260844 | 0.266794 | 0.006767 | 0.003923 | 0.009611 | 1.025651 | 0.693148 | 0.689264 | 0.697032 | 0.286367 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | purpose | car | 2881 | 0.012768 | 449 | 2432 | 553.306748 | 0.192054 | 0.155849 | 0.143063 | 0.169551 | 0.036205 | 0.023613 | 0.048797 | 1.232309 | 0.731349 | 0.707137 | 0.755561 | 0.345128 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | purpose | credit_card | 43673 | 0.193553 | 8053 | 35620 | 9274.782003 | 0.212369 | 0.184393 | 0.180784 | 0.188058 | 0.027976 | 0.024462 | 0.031489 | 1.151718 | 0.694094 | 0.688039 | 0.700150 | 0.283821 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | purpose | debt_consolidation | 123790 | 0.548620 | 27584 | 96206 | 32041.227732 | 0.258835 | 0.222829 | 0.220519 | 0.225156 | 0.036006 | 0.033780 | 0.038233 | 1.161587 | 0.693530 | 0.690153 | 0.696907 | 0.281196 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | purpose | home_improvement | 18273 | 0.080983 | 3370 | 14903 | 3725.919674 | 0.203903 | 0.184425 | 0.178868 | 0.190114 | 0.019478 | 0.014075 | 0.024881 | 1.105614 | 0.704221 | 0.694961 | 0.713480 | 0.301097 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | purpose | house | 2279 | 0.010100 | 471 | 1808 | 531.255902 | 0.233109 | 0.206670 | 0.190546 | 0.223781 | 0.026440 | 0.010583 | 0.042296 | 1.127932 | 0.707980 | 0.682849 | 0.733110 | 0.308669 | available | sufficient | pd_overprediction |
| random_forest | recalibrated | purpose | major_purchase | 6097 | 0.027021 | 1325 | 4772 | 1331.982035 | 0.218465 | 0.217320 | 0.207148 | 0.227848 | 0.001145 | -0.008626 | 0.010916 | 1.005269 | 0.727878 | 0.713286 | 0.742470 | 0.330626 | available | sufficient | not_statistically_distinct |
| random_forest | recalibrated | purpose | medical | 3742 | 0.016584 | 883 | 2859 | 813.196429 | 0.217316 | 0.235970 | 0.222641 | 0.249841 | -0.018654 | -0.031701 | -0.005608 | 0.920947 | 0.695094 | 0.676139 | 0.714048 | 0.295912 | available | sufficient | pd_underprediction |
| random_forest | recalibrated | purpose | moving | 1994 | 0.008837 | 523 | 1471 | 457.942157 | 0.229660 | 0.262287 | 0.243450 | 0.282038 | -0.032627 | -0.050982 | -0.014271 | 0.875606 | 0.706925 | 0.681847 | 0.732003 | 0.315755 | available | sufficient | pd_underprediction |
| random_forest | recalibrated | purpose | other | 18135 | 0.080372 | 4041 | 14094 | 4114.403844 | 0.226876 | 0.222829 | 0.216831 | 0.228944 | 0.004048 | -0.001698 | 0.009794 | 1.018165 | 0.716828 | 0.708197 | 0.725460 | 0.325415 | available | sufficient | not_statistically_distinct |
| random_forest | recalibrated | purpose | renewable_energy | 166 | 0.000736 | 41 | 125 | 38.421655 | 0.231456 | 0.246988 | 0.187600 | 0.317821 | -0.015532 | -0.079407 | 0.048342 | 0.937114 | 0.694634 | 0.611037 | 0.778231 | 0.446049 | available | sufficient | not_statistically_distinct |
| random_forest | recalibrated | purpose | small_business | 2368 | 0.010495 | 856 | 1512 | 685.361255 | 0.289426 | 0.361486 | 0.342375 | 0.381047 | -0.072060 | -0.090543 | -0.053578 | 0.800656 | 0.681962 | 0.660224 | 0.703700 | 0.287637 | available | sufficient | pd_underprediction |
| random_forest | recalibrated | purpose | vacation | 2239 | 0.009923 | 446 | 1793 | 417.038861 | 0.186261 | 0.199196 | 0.183174 | 0.216249 | -0.012935 | -0.028514 | 0.002644 | 0.935065 | 0.738037 | 0.712845 | 0.763229 | 0.357091 | available | sufficient | not_statistically_distinct |
| random_forest | recalibrated | purpose | wedding | 2 | 0.000009 | 1 | 1 | 0.461798 | 0.230899 | 0.500000 | 0.094531 | 0.905469 | -0.269101 | -1.000000 | 0.703394 | 0.461798 | 1.000000 | N/A | N/A | 1.000000 | available | limited_sample | not_statistically_distinct |

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
| limited_feature_replication | medium | Independent validation consumes frozen scores, outcomes, and two business segmentation fields rather than the full development feature set. | Add feature-level replication and challenger rebuild testing in a later slice. |
