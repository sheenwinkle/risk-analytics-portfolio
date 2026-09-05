# Public LendingClub Validation Evidence

This directory contains aggregate-only validation evidence for the full public LendingClub
model run documented in Project 1. Borrower-level predictions remain local and Git-ignored.

## Validation Opinion

The illustrative policy outcome is **warning**:

| Check | Observed | Status |
| --- | ---: | --- |
| ROC-AUC | 0.699887 | warning |
| KS | 0.292493 | warning |
| Absolute calibration gap | 0.026335 | warning |
| PSI | 0.016656 | pass |
| Challenger AUC margin | -0.009411 | pass |

The model retains useful rank ordering and stable score distributions, but its AUC, KS, and
portfolio calibration sit close to or within warning thresholds. The appropriate opinion is
continued monitoring and calibration review rather than unconditional approval.

## Statistical and Grouped Evidence

- AUC: `0.699887`, DeLong 95% CI `0.697369-0.702405`
- Observed default rate: `21.292%`, Wilson 95% CI `21.124%-21.461%`
- Mean recalibrated PD: `23.926%`, 95% CI `23.872%-23.980%`
- Calibration gap: `2.634%`, paired 95% CI `2.472%-2.796%`
- `small_business` calibration gap: `-7.206%`, statistically material under-prediction
- `wedding`: two observations and explicitly marked `limited_sample`

Project 1's raw-status denominator audit shows resolution falling from `48.4%` in 2017Q1 to
`3.9%` in 2018Q4. The apparent resolved-sample default-rate decline to `2.4%` in 2018Q4 is
therefore treated as right-censoring evidence, not an improvement conclusion. Review
`metric_uncertainty.csv`, `vintage_performance.csv`, and `segment_performance.csv` for the
aggregate details.

## Scope

- OOT cohort: 225,639 resolved accepted loans from 2017-2018
- Selected model: recalibrated random forest
- Validation starts from frozen scores, outcomes, and two non-sensitive segments rather than
  rebuilding development features
- Public accepted-loan selection bias and terminal-outcome target limitations remain explicit
- Thresholds are illustrative portfolio policy, not regulatory cutoffs

See `data_lineage.json` for the source file checksum and Project 1 evidence path.
