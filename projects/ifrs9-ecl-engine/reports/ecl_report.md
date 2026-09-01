# IFRS 9 ECL Demo Report

Synthetic educational demo output generated from `scripts/run_pipeline.py`.

## Portfolio Summary

- Gross exposure: 554,000.00
- Probability-weighted ECL: 27,996.92
- Coverage ratio: 5.0536%
- Account count: 6

## Stage Summary

| stage | account_count | gross_exposure | weighted_ecl | coverage_ratio |
| --- | --- | --- | --- | --- |
| 1 | 2 | 245000.000000 | 1597.197892 | 0.006519 |
| 2 | 3 | 264000.000000 | 16952.316566 | 0.064213 |
| 3 | 1 | 45000.000000 | 9447.403678 | 0.209942 |
| Total | 6 | 554000.000000 | 27996.918137 | 0.050536 |

## Scenario Contribution

| scenario | scenario_weight | scenario_ecl | weighted_scenario_ecl |
| --- | --- | --- | --- |
| base | 0.600000 | 23545.590814 | 14127.354488 |
| downside | 0.250000 | 45570.009327 | 11392.502332 |
| upside | 0.150000 | 16513.742108 | 2477.061316 |

## Stage Migration

| prior_stage | stage | account_count | gross_exposure | weighted_ecl |
| --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 245000.000000 | 1597.197892 |
| 1 | 2 | 2 | 202000.000000 | 10198.964682 |
| 2 | 2 | 1 | 62000.000000 | 6753.351884 |
| 2 | 3 | 1 | 45000.000000 | 9447.403678 |

## Caveat

This is a simplified educational PD/LGD/EAD implementation, not accounting advice.
Stage 3 uses the same proxy and is not a production credit-impaired cash-shortfall model.
