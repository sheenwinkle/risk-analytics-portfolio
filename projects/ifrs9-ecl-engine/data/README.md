# Project 2 Data

No raw, private, borrower-level, or institution data is committed for this project.

The runnable demo uses deterministic synthetic account snapshots and synthetic monthly
PD/LGD/EAD term structures generated in `src/ifrs9_ecl_engine/demo.py`.

Reporting-date gross exposure is stored in the synthetic account snapshot. Forward EAD
paths are generated separately for each scenario and month.

Synthetic account identifiers must begin with `SYN-ECL-`.

The Project 1 PD integration demo uses committed synthetic
`projects/credit-risk-pd-model/reports/oot_predictions.csv` outputs. It selects one
`observation_date` cohort, uses only `customer_id`, `observation_date`, and
`recalibrated_pd`, and assigns new `SYN-PD-ECL-` account IDs for Project 2 reporting. The
synthetic non-PD assumptions for EAD, LGD, maturity, EIR, DPD, SICR, credit-impaired,
defaulted, and prior stage are illustrative and independent of Project 1 future outcomes.

The bridge does not infer account assumptions from `actual_default`. Project 1's synthetic
target is a terminal-outcome proxy, not an IFRS 9 default definition. The bridge's
constant-hazard lifetime extrapolation and straight-line fully amortising EAD proxy are
educational assumptions, not production IFRS 9 methodology.

Synthetic PD integration account identifiers must begin with `SYN-PD-ECL-`.

Any real or public-data experiment should remain local unless it has been reviewed and
intentionally anonymised, aggregated, and documented before being added to Git.
