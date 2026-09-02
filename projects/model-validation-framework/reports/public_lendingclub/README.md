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

## Scope

- OOT cohort: 225,639 resolved accepted loans from 2017-2018
- Selected model: recalibrated random forest
- Validation starts from frozen scores and outcomes rather than rebuilding development features
- Public accepted-loan selection bias and terminal-outcome target limitations remain explicit
- Thresholds are illustrative portfolio policy, not regulatory cutoffs

See `data_lineage.json` for the source file checksum and Project 1 evidence path.
