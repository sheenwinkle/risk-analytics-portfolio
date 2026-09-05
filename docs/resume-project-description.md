# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and PostgreSQL credit risk analytics portfolio across 2.26 million public
LendingClub records, covering temporal PD modelling, recalibration, educational IFRS 9 ECL,
credit strategy, macro/overlay governance, independent validation, and remediation governance.

## Resume Bullets

- Processed 2.26 million public LendingClub accepted-loan records through chunked, audited ingestion, retaining 1.35 million resolved outcomes and 225,639 untouched 2017-2018 OOT observations.
- Selected a random forest challenger before OOT evaluation and achieved ROC-AUC 0.6999, Gini 0.3998, and KS 0.2925; logistic recalibration reduced OOT Brier score from 0.2085 to 0.1547.
- Quantified terminal-outcome maturity bias with quarterly unresolved-status denominators, showing resolution falling from 48.4% in 2017Q1 to 3.9% in 2018Q4 rather than misreading censored default rates as improvement.
- Built a leakage-controlled champion-challenger strategy that selected a 20% max-PD cutoff pre-OOT, then measured 35,876 incremental public OOT approvals, USD 449.4 million incremental exposure, and a USD 17.0 million realised credit-contribution proxy uplift (95% paired-bootstrap CI: 16.1-18.0 million).
- Designed PostgreSQL schemas, transactional persistence, and analytical SQL for model runs, policy metrics, confidence intervals, grouped backtests, findings, limitations, benchmarks, remediation retests, and closure decisions.
- Produced portfolio-ready model artefacts, including account-level raw and recalibrated PD predictions, calibration deciles, PSI drift reports, and a saved recalibrated model wrapper.
- Connected committed synthetic recalibrated out-of-time PD outputs to an educational IFRS 9 ECL engine through validated reporting-date cohort selection, explicit account assumptions, scenario hazard multipliers, and reproducible ECL reports.
- Quantified a 13.56% combined downside ECL sensitivity, kept the stress delta outside booked ECL, blocked a duplicate-risk overlay, and enforced trigger, approval, and 8% cap controls to reconcile 27,996.92 modelled ECL to 30,236.67 illustrative reported ECL.
- Built a reusable PD model validation framework that independently reperforms AUC, Gini, tie-safe KS, Brier score, calibration deciles, monthly/vintage/segment diagnostics, score PSI, feature CSI, and challenger comparisons, then applies explicit policy thresholds and produces actionable findings.
- Independently rebuilt the logistic and random-forest development candidates from a governed pre-OOT extract, reproducing model selection, both holdout AUCs, and 19 transformed coefficients/importances per model within a 1e-8 tolerance.
- Issued a public-data warning opinion after independently re-performing AUC 0.699887 (DeLong 95% CI 0.697369-0.702405), KS 0.292493, calibration gap 0.026335 (95% CI 0.024716-0.027955), PSI 0.016656, and maximum CSI 0.077926 on 225,639 frozen OOT scores.
- Implemented no-look-ahead rolling recalibration that reduced a synthetic adverse finding's calibration gap from 0.064441 to 0.009218, while retaining `pending_fresh_oot` status rather than overstating closure.

## LinkedIn / GitHub Summary

This portfolio demonstrates a bank-style credit risk workflow from public-data PD development
through educational ECL reporting and independent-style model validation. It includes
bounded-memory LendingClub ingestion, leakage-safe pre-OOT selection and recalibration,
champion-challenger strategy with paired uncertainty, PSI monitoring, a PD-to-ECL bridge,
separate macro-sensitivity/overlay reconciliation, and a validation package that consumes
frozen OOT scores and model inputs,
quantifies metric uncertainty, grouped
performance, and characteristic drift, records policy findings, tests sequential remediation,
and persists governance history to PostgreSQL.

## Interview Pitch

I built this portfolio to show how I think about credit risk models beyond generic machine
learning accuracy. Project 1 processes the full public LendingClub file, selects the model
before OOT evaluation, recalibrates on a pre-OOT holdout, and selects a credit-policy
challenger before measuring its incremental OOT impact. Project 2 shows
how frozen recalibrated PD can feed a simplified ECL workflow without using future outcomes
as inputs, then keeps non-booked macro sensitivities separate from approved and capped
management overlays. Project 3 independently consumes frozen scores, outcomes, and model inputs,
reconciles the derived loan-to-income feature, re-performs metrics with confidence intervals,
measures PSI/CSI drift, applies policy thresholds, tests a no-look-ahead remediation, and
preserves the distinction between a passed retest and formal closure. The ECL and validation
policies are educational assumptions, not compliance or production approval claims.

## Project 3 Standalone Bullet

> Developed a reusable Python and PostgreSQL credit risk validation framework, independently
> rebuilding two development candidates and re-performing AUC, Gini, tie-safe KS, Brier
> score, calibration, confidence intervals,
> vintage/segment backtesting, PSI/CSI, and challenger comparisons on 225,639 public OOT
> observations; implemented feature-lineage checks, policy findings, sequential remediation,
> deterministic evidence, and governance persistence.

## Project 2 Standalone Bullet

> Built an educational IFRS 9 ECL engine with configurable staging, monthly PD/LGD/EAD,
> scenario weighting, discounting, and a leakage-controlled PD bridge; added auditable macro
> sensitivities and management-overlay controls that quantified a 13.56% downside impact,
> blocked double counting, enforced approval and an 8% cap, and reconciled modelled to
> illustrative reported ECL.
