# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and PostgreSQL credit risk analytics portfolio across 2.26 million public
LendingClub records, covering temporal PD modelling, recalibration, educational IFRS 9 ECL,
credit strategy, contractual cash-flow/recovery sensitivity, SICR and macro/overlay
governance, an Australian macro-credit satellite, validation-only remediation, independent
validation, and PostgreSQL finding lifecycles.

## Resume Bullets

- Processed 2.26 million public LendingClub accepted-loan records through chunked, audited ingestion, retaining 1.35 million resolved outcomes and 225,639 untouched 2017-2018 OOT observations.
- Selected a random forest challenger before OOT evaluation and achieved ROC-AUC 0.6999, Gini 0.3998, and KS 0.2925; logistic recalibration reduced OOT Brier score from 0.2085 to 0.1547.
- Quantified terminal-outcome maturity bias with quarterly unresolved-status denominators, showing resolution falling from 48.4% in 2017Q1 to 3.9% in 2018Q4 rather than misreading censored default rates as improvement.
- Built a leakage-controlled champion-challenger strategy that selected a 20% max-PD cutoff pre-OOT, then measured 35,876 incremental public OOT approvals, USD 449.4 million incremental exposure, and a USD 17.0 million realised credit-contribution proxy uplift (95% paired-bootstrap CI: 16.1-18.0 million).
- Designed PostgreSQL schemas, transactional persistence, and analytical SQL for model runs, policy metrics, confidence intervals, grouped backtests, findings, limitations, benchmarks, remediation retests, and closure decisions.
- Produced portfolio-ready model artefacts, including account-level raw and recalibrated PD predictions, calibration deciles, PSI drift reports, and a saved recalibrated model wrapper.
- Connected committed synthetic recalibrated out-of-time PD outputs to an educational IFRS 9 ECL engine through validated reporting-date cohort selection, explicit account assumptions, scenario hazard multipliers, and reproducible ECL reports.
- Built an attributed APRA/RBA macro-credit satellite on 70 quarterly observations with development, tuning, and frozen 2019-2021 OOT windows; reported 17.7% worse MAE than persistence and restricted the model to sensitivity use rather than overstating performance.
- Pre-registered four lag-compatible macro remediation candidates and seven Ridge penalties, selected one of 28 combinations using only 2016-2018 validation data, and reduced reused-OOT MAE/RMSE versus the incumbent by 14.73%/24.61% while retaining restricted use.
- Held accounts, LGD, EAD, staging, scenario weights, and engine logic fixed in an A/B-style ECL comparison, quantifying a -9.87% manual-versus-empirical multiplier sensitivity as model risk rather than savings.
- Quantified a 16.54% combined downside ECL sensitivity, kept the stress delta outside booked ECL, blocked a duplicate-risk overlay, and enforced trigger, approval, and 8% cap controls to reconcile 27,996.92 modelled ECL to 30,236.67 illustrative reported ECL.
- Implemented governed 30 DPD rebuttal decisions with evidence, forward-looking, DPD/date, approval, and precedence controls; on a synthetic case, one of three requests moved Stage 2 to Stage 1 and produced a reconciled 2,163.00 (7.40%) ECL impact without treating the reduction as business value.
- Built a contractual cash-flow adapter with CPR-driven EAD roll-forward, discounted cure and collateral recovery, integral/separate-recognition eligibility, and six controlled cases; quantified isolated ECL impacts of 4.91%-34.14% and a combined 13,112.07 (72.43%) downside increase with zero-difference account-to-portfolio reconciliation.
- Built a reusable PD model validation framework that independently reperforms AUC, Gini, tie-safe KS, Brier score, calibration deciles, monthly/vintage/segment diagnostics, score PSI, feature CSI, and challenger comparisons, then applies explicit policy thresholds and produces actionable findings.
- Independently rebuilt the logistic and random-forest development candidates from a governed pre-OOT extract, reproducing model selection, both holdout AUCs, and 19 transformed coefficients/importances per model within a 1e-8 tolerance.
- Issued a public-data warning opinion after independently re-performing AUC 0.699887 (DeLong 95% CI 0.697369-0.702405), KS 0.292493, calibration gap 0.026335 (95% CI 0.024716-0.027955), PSI 0.016656, and maximum CSI 0.077926 on 225,639 frozen OOT scores.
- Implemented no-look-ahead rolling recalibration that reduced a synthetic adverse finding's calibration gap from 0.064441 to 0.009218, while retaining `pending_fresh_oot` status rather than overstating closure.
- Independently recomputed macro-satellite residuals, persistence benchmarks, scenario direction, coefficient constraints, and developer metrics without importing development code; issued a restricted opinion with three open findings, including real-time data-vintage risk.
- Re-performed macro remediation through 13 independent controls and six append-only PostgreSQL finding events; kept MSV-001/MSV-003 open, moved MSV-002 only to `pending_fresh_oot`, and closed zero findings because the OOT window was already observed.

## LinkedIn / GitHub Summary

This portfolio demonstrates a bank-style credit risk workflow from public-data PD development
through educational ECL reporting and independent-style model validation. It includes
bounded-memory LendingClub ingestion, leakage-safe pre-OOT selection and recalibration,
champion-challenger strategy with paired uncertainty, PSI monitoring, a PD-to-ECL bridge,
governed 30 DPD rebuttals, separate macro-sensitivity/overlay reconciliation, and a
public Australian macro satellite with fixed-input ECL A/B sensitivity and validation-only
remediation, a six-case contractual cash-flow/recovery sensitivity with account attribution,
and a
validation package that consumes
frozen OOT scores and model inputs,
quantifies metric uncertainty, grouped
performance, and characteristic drift, records policy findings, tests sequential and macro
remediation, and persists append-only governance history to PostgreSQL.

## Interview Pitch

I built this portfolio to show how I think about credit risk models beyond generic machine
learning accuracy. Project 1 processes the full public LendingClub file, selects the model
before OOT evaluation, recalibrates on a pre-OOT holdout, and selects a credit-policy
challenger before measuring its incremental OOT impact. Project 2 shows
how frozen recalibrated PD can feed a simplified ECL workflow without using future outcomes
as inputs, then keeps non-booked macro sensitivities separate from approved and capped
management overlays. Its APRA/RBA satellite uses frozen OOT testing and remains restricted
after it underperforms persistence; the resulting ECL difference is reported as model-choice
sensitivity rather than savings. It also records SICR rebuttal evidence, approval, expiry, and precedence,
then reconciles the stage and ECL impact without presenting lower ECL as a success metric.
Its contractual cash-flow adapter isolates how prepayment, cure, collateral value/haircut,
and recovery timing affect EAD, effective LGD, and portfolio ECL while leaving staging fixed.
Project 3 independently consumes frozen scores, outcomes, and model inputs,
reconciles the derived loan-to-income feature, re-performs metrics with confidence intervals,
measures PSI/CSI drift, applies policy thresholds, tests a no-look-ahead remediation, and
independently challenges the macro satellite. It preserves the distinction between a passed
retest and formal closure. The macro remediation evaluates 28 pre-registered combinations on
validation data only, materially reduces incumbent error on reused OOT evidence, and still
closes zero findings because one benchmark and release-vintage evidence remain unresolved.
The ECL and validation
policies are educational assumptions, not compliance or production approval claims.

## Project 3 Standalone Bullet

> Developed a reusable Python and PostgreSQL credit risk validation framework, independently
> rebuilding two development candidates and re-performing AUC, Gini, tie-safe KS, Brier
> score, calibration, confidence intervals,
> vintage/segment backtesting, PSI/CSI, and challenger comparisons on 225,639 public OOT
> observations; implemented feature-lineage checks, policy findings, sequential remediation,
> deterministic evidence, and governance persistence; re-performed 28 validation-only macro
> remediation combinations through 13 controls and six finding events, reducing reused-OOT
> incumbent MAE/RMSE by 14.73%/24.61% while closing zero findings and retaining the
> release-vintage limitation.

## Project 2 Standalone Bullet

> Built an educational IFRS 9 ECL engine with configurable staging, monthly PD/LGD/EAD,
> scenario weighting, discounting, and a leakage-controlled PD bridge; developed an attributed
> APRA/RBA macro satellite on 70 quarters and a fixed-input ECL A/B comparison that quantified
> -9.87% model-choice sensitivity while retaining a sensitivity-only restriction after OOT
> benchmark failure; tested 28 lag-compatible remediation combinations without OOT selection
> and reduced reused-OOT incumbent MAE/RMSE by 14.73%/24.61% without claiming closure; added
> macro and management-overlay controls that quantified a 16.54% downside impact,
> blocked double counting, enforced approval and an 8% cap, and reconciled modelled to
> illustrative reported ECL; governed the 30 DPD rebuttable presumption through evidence,
> validity, approval, and precedence controls, quantifying a reconciled 2,163.00 (7.40%)
> synthetic ECL impact for one effective request out of three; implemented CPR-driven EAD
> and discounted cure/collateral recovery sensitivities, quantifying a 13,112.07 (72.43%)
> combined downside ECL increase with exact account-to-portfolio reconciliation.
