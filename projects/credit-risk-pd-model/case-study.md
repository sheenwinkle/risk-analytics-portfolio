# Credit Risk PD Modelling Case Study

## Interview Positioning

This project is designed to signal the intersection of Economics + CS + FRM:
credit risk modelling, production-style scoring, and governance evidence rather
than a generic machine-learning notebook.

The business question is:

> Can a lender deploy a calibrated PD model and controlled growth policy while
> keeping the evidence reproducible, privacy-safe, and clear about model-risk
> limitations?

## My contribution

I built the end-to-end PD workflow:

- Transformed accepted-loan data into a time-aware modelling dataset with
  feature engineering, WOE/IV diagnostics, model training, calibration, and
  out-of-time testing.
- Compared a logistic baseline with a random-forest challenger and selected the
  challenger before OOT evaluation.
- Recalibrated the selected challenger on a pre-OOT holdout, reducing public OOT
  Brier 0.2085 to 0.1547 while preserving ROC-AUC 0.6999.
- Designed a retrospective champion-challenger backtest for a 15% incumbent
  cutoff versus a controlled 20% max-PD growth challenger.
- Added a governed scoring service with strict schema validation, derived
  features, risk bands, cutoff outcomes, batch audit output, artifact integrity
  checks, and deterministic replay evidence.
- Published only privacy-safe aggregate evidence; application_id is not published
  in public reports, row-level scores are excluded, and model artifacts remain
  uncommitted.

## Quantified Output

On the published LendingClub public OOT sample:

| Evidence item | Result |
| --- | ---: |
| Scoring volume | 225,639 public OOT applications |
| Governed replay size | 226 governed scoring batches |
| Selected model | Random forest, recalibrated |
| Discrimination | ROC-AUC 0.6999 |
| Calibration | Brier 0.2085 to 0.1547 |
| Incremental approvals | 35,876 incremental approvals |
| Incremental exposure | USD 449.4m incremental exposure |
| Realised contribution proxy | USD 17.0m realised contribution proxy uplift |
| Paired bootstrap interval | 16.1m-18.0m |
| Governance decision | advance_challenger |

The contribution proxy is a simplified one-year calculation: gross coupon income
less default loss proxy. It is deliberately not a full profitability model; it
excludes funding cost, operating cost, prepayment, collections timing, and
capital usage.

## A/B Framing

This is not a randomized A/B test. The right interview framing is:

- It is a retrospective champion-challenger backtest with paired OOT comparison.
- The incumbent and challenger are evaluated on the same accepted-loan outcomes.
- The challenger cutoff is selected on pre-OOT evidence and frozen before OOT
  measurement.
- The paired bootstrap interval quantifies uncertainty in the historical
  marginal cohort, not causal uplift from a live experiment.

If asked how to productionize it as a real A/B test, the next step would be a
controlled challenger rollout with randomized eligible applications, fixed
treatment assignment, pre-defined guardrails, and live monitoring of approval
rate, delinquency, loss, complaint, and adverse-action metrics.

## Governance And Risk Controls

The scoring layer adds controls that turn the model into a risk-analytics
delivery artifact:

- Deployment manifest records the contract version, model version, feature
  contract, risk bands, cutoff, policy decision, model artifact name, and
  contract hash.
- Model artifact integrity is checked before loading; serving refuses tampered
  or mismatched artifacts.
- Batch inputs are validated for required fields, numeric bounds, categorical
  values, unique application IDs, and maximum batch size.
- Data quality output reports missing inputs and unseen categories at scoring
  time.
- The explanation method is explicitly
  policy_input_flags_not_model_attribution; flags are input risk indicators, not
  SHAP values, local model attribution, adverse-action reasons, or legal decline
  explanations.

## What This Proves

For Credit Risk, Risk Analytics, Lending Data Science, or Model Validation roles,
this project demonstrates that I can:

- Build and evaluate PD models using financial-risk metrics rather than generic
  ML accuracy only.
- Translate model performance into lending policy impact with clear assumptions.
- Separate challenger evidence from causal A/B claims.
- Package a model behind a strict scoring contract.
- Produce reproducible, privacy-safe public evidence that a reviewer can run.

## Resume bullet

Built an end-to-end public-data credit risk PD platform with temporal validation,
recalibration, champion-challenger policy backtesting, and governed FastAPI
scoring; on 225,639 public OOT applications, replayed 226 governed scoring
batches and quantified 35,876 incremental approvals, USD 449.4m incremental
exposure, and USD 17.0m realised contribution proxy uplift
(95% paired-bootstrap interval: 16.1m-18.0m), while publishing only aggregate
privacy-safe evidence and clearly separating retrospective impact from causal
A/B claims.
