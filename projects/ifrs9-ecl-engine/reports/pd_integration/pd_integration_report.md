# Project 1 PD to Project 2 ECL Bridge

This deterministic report connects committed Project 1 synthetic out-of-time recalibrated PD outputs to the Project 2 educational ECL engine.

## Lineage

- Reporting date: 2022-12-01
- Account count: 8
- Recalibrated 12-month PD range: 1.1506% to 23.5883%
- Source columns used by the bridge: `customer_id`, `observation_date`, and `recalibrated_pd` only.
- `actual_default` and other future outcome fields are not used in ECL input construction.

## Methodology

Project 1's synthetic target is a terminal-outcome proxy. The bridge treats `recalibrated_pd` as a 12-month cumulative PD, converts it to a constant annual hazard `h = -log(1 - p)`, applies explicit scenario hazard multipliers, and derives monthly marginal PD from conditional monthly `q = 1 - exp(-h_scenario / 12)` and survival to the previous month.

The lifetime extrapolation uses that constant-hazard assumption for education and interview discussion. It is not an IFRS 9 compliance claim.

## Account Assumptions

EAD, LGD, remaining maturity, EIR, DPD, SICR, credit-impaired/defaulted flags, and prior stage are explicit synthetic assumptions. They are illustrative and independent of Project 1 outcomes.

Reporting-date gross exposure is kept independent from forward EAD paths. The forward EAD path is a transparent straight-line fully amortising proxy: month 1 starts at reporting-date gross exposure and declines to one final monthly instalment by maturity. No detailed contractual cash-flow model is claimed.

## Portfolio Summary

- Gross exposure: 710,000.00
- Probability-weighted ECL: 62,102.72
- Coverage ratio: 8.7469%

## Stage Summary

| stage | account_count | gross_exposure | weighted_ecl | coverage_ratio |
| --- | --- | --- | --- | --- |
| 1 | 4 | 292500.000000 | 10796.189205 | 0.036910 |
| 2 | 3 | 310000.000000 | 39985.994141 | 0.128987 |
| 3 | 1 | 107500.000000 | 11320.538294 | 0.105307 |
| Total | 8 | 710000.000000 | 62102.721641 | 0.087469 |

## Scenario Contribution

| scenario | scenario_weight | hazard_multiplier | lgd_addon | scenario_ecl | weighted_scenario_ecl |
| --- | --- | --- | --- | --- | --- |
| base | 0.600000 | 1.000000 | 0.000000 | 54614.018902 | 32768.411341 |
| downside | 0.250000 | 1.650000 | 0.080000 | 93054.219686 | 23263.554921 |
| upside | 0.150000 | 0.750000 | -0.030000 | 40471.702520 | 6070.755378 |

## Stage Migration

| prior_stage | stage | account_count | gross_exposure | weighted_ecl |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 292500.000000 | 10796.189205 |
| 1 | 2 | 1 | 82500.000000 | 3883.482921 |
| 2 | 2 | 2 | 227500.000000 | 36102.511220 |
| 2 | 3 | 1 | 107500.000000 | 11320.538294 |

## Limitation

This is a synthetic educational bridge between portfolio projects, not a production ECL model, not accounting advice, and not evidence of IFRS 9 compliance.
