# Independent Australian Macro Satellite Validation

## Opinion: RESTRICTED

The satellite is restricted to sensitivity evidence and is not approved for point forecasting or accounting calibration.

## Independent Backtest

- OOT period: 2019-03-31 to 2021-12-31
- Observations: 12
- Satellite MAE: 0.000601
- Persistence MAE: 0.000511
- MAE improvement versus persistence: -17.7%
- RMSE improvement versus persistence: -30.6%

## Control Results

- Failed checks: 2
- Warning checks: 3
- Open findings: 3

| check | metric_value | threshold | direction | status |
| --- | --- | --- | --- | --- |
| oot_observations | 12.000000 | 12.000000 | greater_than_or_equal | pass |
| oot_mae_vs_persistence | -0.176947 | 0.000000 | greater_than_or_equal | fail |
| oot_rmse_vs_persistence | -0.305651 | 0.000000 | greater_than_or_equal | fail |
| scenario_directionality | 0.046191 | 0.000000 | greater_than | pass |
| coefficient_constraints | 0.000000 | 0.000000 | greater_than_or_equal | pass |
| active_macro_drivers | 1.000000 | 2.000000 | greater_than_or_equal | warning |
| alpha_search_interior | 0.000000 | 1.000000 | equal | warning |
| real_time_data_vintage | 0.000000 | 1.000000 | equal | warning |
| developer_metric_reconciliation | 0.000000 | 0.000000 | less_than_or_equal | pass |

## Findings

| finding_id | severity | title | status | use_restriction | required_action |
| --- | --- | --- | --- | --- | --- |
| MSV-001 | high | Satellite underperforms persistence benchmark | open | sensitivity_only | Test alternative horizons, targets, and dynamic specifications; repeat frozen OOT validation before point-forecast use. |
| MSV-002 | moderate | Pre-specified unemployment factor is inactive | open | sensitivity_only | Investigate factor form, lags, collinearity, and segment-level targets without forcing a non-zero coefficient. |
| MSV-003 | moderate | Real-time macro data availability is not evidenced | open | sensitivity_only | Reconstruct release-date vintages or lag macro factors; test data revision sensitivity before operational forecasting. |

## Required Decision

Retain the incumbent for the educational ECL baseline. Use the empirical challenger only to quantify sensitivity until alternative specifications pass a new frozen OOT benchmark comparison.
