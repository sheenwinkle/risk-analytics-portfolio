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

The macro-sensitivity and management-overlay demo uses no additional borrower data. Its
scenario-weight shifts, downside severity multiplier, trigger observations, requested
amounts, overlap assessments, cap ratios, and approval records are deterministic synthetic
governance assumptions defined in `src/ifrs9_ecl_engine/governance_demo.py`. They are not
estimated macroeconomic relationships, observed institution events, or accounting evidence.

The SICR rebuttal demo also uses only deterministic synthetic records. Evidence references,
payment-delay explanations, observed DPD snapshots, decision dates, validity periods,
approval statuses, and the named committee are illustrative governance inputs defined in
`src/ifrs9_ecl_engine/sicr_demo.py`. They are not borrower evidence, institution decisions,
or support for a real accounting conclusion.

The contractual cash-flow demo reuses the six `SYN-ECL-` account snapshots and marginal PD
curves. It adds deterministic 36-month repayment schedules covering level amortisation,
24-month amortisation, partial balloons, and a bullet maturity. Annual CPR, cure rates,
recovery delays, collateral values, haircuts, selling/recovery costs, security type, and
integral/separate-recognition flags are synthetic scenario-policy assumptions defined in
`src/ifrs9_ecl_engine/cashflow_demo.py`.

These inputs are not observed borrower cash flows, appraisals, legal enforceability opinions,
or institution-approved forecasts. The committed outputs aggregate monthly projections at
portfolio level; the small account-level sensitivity table uses synthetic identifiers only.
No future-default outcome is used to build contractual schedules or recovery assumptions.

Any real or public-data experiment should remain local unless it has been reviewed and
intentionally anonymised, aggregated, and documented before being added to Git.
