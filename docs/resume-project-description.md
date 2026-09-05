# Resume Project Description

## Project Title

Credit Risk Probability of Default Modelling

## One-Line Version

Built a Python and PostgreSQL credit risk analytics portfolio across 2.26 million public
LendingClub records, covering temporal PD modelling, recalibration, educational IFRS 9 ECL,
independent validation, and remediation governance.

## Resume Bullets

- Processed 2.26 million public LendingClub accepted-loan records through chunked, audited ingestion, retaining 1.35 million resolved outcomes and 225,639 untouched 2017-2018 OOT observations.
- Selected a random forest challenger before OOT evaluation and achieved ROC-AUC 0.6999, Gini 0.3998, and KS 0.2925; logistic recalibration reduced OOT Brier score from 0.2085 to 0.1547.
- Produced fixed max-PD approval cutoff scenario outputs showing approval rate, observed default rate, exposure, expected loss, and rejected-default capture without optimising thresholds on OOT.
- Designed PostgreSQL schemas, transactional persistence, and analytical SQL for model runs, policy metrics, findings, limitations, benchmarks, remediation retests, and closure decisions.
- Produced portfolio-ready model artefacts, including account-level raw and recalibrated PD predictions, calibration deciles, PSI drift reports, and a saved recalibrated model wrapper.
- Connected committed synthetic recalibrated out-of-time PD outputs to an educational IFRS 9 ECL engine through validated reporting-date cohort selection, explicit account assumptions, scenario hazard multipliers, and reproducible ECL reports.
- Built a reusable PD model validation framework that independently reperforms AUC, Gini, tie-safe KS, Brier score, calibration deciles, monthly diagnostics, PSI, and challenger comparisons, then applies explicit policy thresholds and produces actionable findings.
- Issued a public-data warning opinion after independently re-performing AUC 0.699887, KS 0.292493, calibration gap 0.026335, PSI 0.016656, and challenger tests on frozen OOT scores.
- Implemented no-look-ahead rolling recalibration that reduced a synthetic adverse finding's calibration gap from 0.064441 to 0.009218, while retaining `pending_fresh_oot` status rather than overstating closure.

## LinkedIn / GitHub Summary

This portfolio demonstrates a bank-style credit risk workflow from public-data PD development
through educational ECL reporting and independent-style model validation. It includes
bounded-memory LendingClub ingestion, leakage-safe pre-OOT selection and recalibration, fixed
strategy scenarios, PSI monitoring, a PD-to-ECL bridge, and a separate validation package
that consumes frozen OOT scores, records policy findings, tests sequential remediation, and
persists governance history to PostgreSQL.

## Interview Pitch

I built this portfolio to show how I think about credit risk models beyond generic machine
learning accuracy. Project 1 processes the full public LendingClub file, selects the model
before OOT evaluation, recalibrates on a pre-OOT holdout, and monitors drift. Project 2 shows
how frozen recalibrated PD can feed a simplified ECL workflow without using future outcomes
as inputs. Project 3 independently consumes frozen scores and outcomes, re-performs metrics,
applies policy thresholds, tests a no-look-ahead remediation, and preserves the distinction
between a passed retest and formal closure. The ECL and validation policies are educational
assumptions, not compliance or production approval claims.

## Project 3 Standalone Bullet

> Developed a reusable Python and PostgreSQL credit risk validation framework, independently
> re-performing AUC, Gini, tie-safe KS, Brier score, calibration, monthly backtesting, PSI,
> and challenger comparisons on 225,639 public OOT observations; implemented policy findings,
> sequential remediation, deterministic evidence, and finding lifecycle persistence.

