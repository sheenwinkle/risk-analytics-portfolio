# Calibration Remediation and Finding Lifecycle

## Decision

- Sequential remediation retest: **pass** (absolute calibration gap 0.009).
- Finding closure status: **pending_fresh_oot**.
- Closure rationale: Sequential retest passed, but closure requires an additional matured OOT horizon.

## No-Look-Ahead Design

Each validation month uses a logistic recalibrator fitted only on the prior 3 matured monthly cohorts. No validation-month outcome is used to fit its own score transformation.

## Aggregate Reperformance

| Measure | Incumbent | Remediated |
| --- | ---: | ---: |
| Mean PD | 0.095 | 0.169 |
| Absolute calibration gap | 0.064 | 0.009 |
| Brier score | 0.131 | 0.125 |

Observed default rate: 0.160.

## Monthly Evidence

| Validation month | Observations | Observed rate | Incumbent PD | Remediated PD |
| --- | ---: | ---: | ---: | ---: |
| 2022-07-01 | 65 | 0.185 | 0.098 | 0.182 |
| 2022-08-01 | 110 | 0.145 | 0.091 | 0.176 |
| 2022-09-01 | 83 | 0.145 | 0.088 | 0.153 |
| 2022-10-01 | 81 | 0.136 | 0.092 | 0.157 |
| 2022-11-01 | 86 | 0.186 | 0.108 | 0.191 |
| 2022-12-01 | 95 | 0.168 | 0.095 | 0.155 |

Educational portfolio case study; not a production model-change approval.
