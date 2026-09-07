# IFRS 9 ECL Engine

Status: complete scoped case study with deterministic standalone, Project 1 PD-integration,
contractual cash-flow/recovery sensitivity, macro-sensitivity/management-overlay, and SICR
rebuttal governance evidence.

This project is a runnable, educational expected credit loss engine for credit risk
analytics portfolio discussion. It calculates account-level and portfolio-level ECL from
reporting-date account snapshots, monthly PD/LGD/EAD term structures, staging rules, and
explicit macro scenario weights.

An optional pre-engine adapter converts contractual principal, prepayment, cure timing, and
eligible collateral assumptions into auditable monthly EAD and effective LGD term structures.
It then calls the same `run_ecl_engine(...)` entry point; there is no second ECL calculator.

It is not a production IFRS 9 implementation, not an assertion of IFRS compliance, and not
accounting advice. A real implementation would require institution-specific accounting
policy, governance, controls, model validation, audit review, and fuller IFRS 9 scoping.

The committed `reports/pd_integration/` artefacts show a professional vertical slice from
Project 1's synthetic out-of-time recalibrated PD outputs into this ECL engine. That bridge
is still educational: Project 1's target is a terminal-outcome proxy, and the bridge's
constant-hazard lifetime extrapolation is not an IFRS 9 compliance methodology.

## Methodology

Public API:

```python
from ifrs9_ecl_engine import run_ecl_engine

result = run_ecl_engine(accounts, term_structures, scenario_weights)
```

`run_ecl_engine` returns an `ECLResult` dataclass with:

- `account_ecl`: probability-weighted ECL by account
- `scenario_ecl`: scenario-level ECL by account
- `portfolio_summary`: stage-level and total portfolio summary
- `stage_migration`: prior-stage to current-stage movement table
- `sicr_rebuttal_register`: decision evidence and stage impact for every rebuttal request

For each account/scenario/month:

```text
discounted expected loss =
  marginal_pd * lgd * ead / (1 + annual_effective_interest_rate) ** (month / 12)
```

Stage 1 uses a 12-month ECL horizon, capped by the available remaining monthly term.
In IFRS 9 language, 12-month ECL is the portion of lifetime expected credit losses that
results from default events possible within 12 months after the reporting date. It is not
limited to cash shortfalls expected only during the next 12 months.

Stage 2 and Stage 3 use the available lifetime monthly term structure.

`gross_exposure` is supplied independently in the reporting-date account snapshot and is
used as the coverage-ratio denominator. It is not inferred from a particular scenario's
forecast EAD path. Scenario EAD paths may therefore differ without changing the reporting-
date exposure measure.

Scenario weights are explicit, nonnegative, and must sum to 1. The engine does not infer,
choose, optimize, or backfit scenario weights from outcomes.

## Contractual Cash-flow and Recovery Sensitivity

Public API:

```python
from ifrs9_ecl_engine import (
    CashFlowSensitivityCase,
    analyse_cashflow_sensitivity,
    build_cashflow_ecl_terms,
)

projection = build_cashflow_ecl_terms(
    accounts,
    marginal_pd_curves,
    contractual_schedule,
    recovery_assumptions,
)
analysis = analyse_cashflow_sensitivity(
    accounts,
    marginal_pd_curves,
    contractual_schedule,
    recovery_assumptions,
    scenario_weights,
    cases=(
        CashFlowSensitivityCase(case_id="baseline", is_baseline=True),
        CashFlowSensitivityCase(
            case_id="lower_cure",
            cure_rate_multiplier=0.65,
        ),
    ),
)
```

The adapter converts annual conditional prepayment rate (CPR) to a monthly rate before the
balance roll-forward:

```text
monthly prepayment rate = 1 - (1 - annual CPR) ** (1 / 12)
closing balance = opening balance - applied contractual principal - expected prepayment
effective LGD = 1 - discounted expected recovery at default / opening EAD
```

Cure cash flows and collateral proceeds are discounted from their expected recovery dates
using the account effective interest rate. Collateral is included only when it is integral to
the contractual terms and not recognized separately, and is reduced for haircut and recovery
cost before being capped at the non-cure exposure. Every excluded record retains an auditable
eligibility reason.

The deterministic demo compares one neutral baseline with lower prepayment, lower cure,
collateral downturn, delayed recovery, and combined-downside cases. On `554,000.00` synthetic
gross exposure, baseline ECL is `18,103.39`; the single-factor cases add `4.91%` to `34.14%`,
and the combined case adds `13,112.07` or `72.43%`. These are sensitivities, not booked
adjustments or empirical forecasts.

This component supplies cash-flow-informed EAD and LGD assumptions to the portfolio engine.
It is not a full direct comparison of all contractual versus expected cash flows and is not
an IFRS 9 compliance conclusion.

## Macro Sensitivity and Management Overlays

The separate governance layer consumes frozen scenario-level model output. It never mutates
account ECL, scenario ECL, PD, LGD, EAD, or staging results.

`analyse_macro_sensitivity(...)` compares controlled scenario-weight and scenario-ECL
severity assumptions. Every case must cover exactly the modelled scenarios with weights
summing to 1, and exactly one baseline must reconcile to the engine's original weights.
The committed cases isolate:

- A 10 percentage-point shift from base to downside weight
- A 10% increase in downside scenario ECL severity
- The combined weight and severity sensitivity

Sensitivity deltas are explicitly labelled `not_booked`. They show exposure to assumptions;
they do not automatically change reported ECL.

`evaluate_management_overlays(...)` applies four independent controls to every request:

- Objective trigger comparison against a documented threshold
- Model-overlap assessment and double-counting check
- Approval status with a named approver required for approved requests
- A request-level cap expressed as a share of baseline modelled ECL

Every request remains in `management_overlay_register.csv`, including blocked, pending, and
rejected items. Only a triggered, distinct, approved, within-cap amount enters
`illustrative_reported_ecl`. Duplicate overlay IDs and duplicate risk-driver/scope pairs are
rejected. The workflow therefore preserves separate model, sensitivity, overlay, and final
reporting layers.

## Project 1 PD Integration Bridge

Public bridge API:

```python
from ifrs9_ecl_engine import (
    build_ecl_inputs_from_pd_snapshot,
    run_pd_ecl_integration,
    select_pd_reporting_cohort,
)

cohort = select_pd_reporting_cohort(predictions, reporting_date=None)
bridge_inputs, result = run_pd_ecl_integration(cohort, account_assumptions)
```

The bridge reads Project 1 `reports/oot_predictions.csv` and uses only:

- `customer_id`
- `observation_date`
- `recalibrated_pd`

It intentionally ignores `actual_default` and other future-outcome columns when constructing
ECL inputs. A requested reporting date must exist in the PD output; otherwise the adapter
fails with the available dates. The CLI default selects the latest `observation_date`.

`recalibrated_pd` is treated as a 12-month cumulative PD. For each account:

```text
annual hazard h = -log(1 - recalibrated_pd)
scenario hazard h_s = h * scenario_hazard_multiplier
monthly conditional q = 1 - exp(-h_s / 12)
monthly marginal PD_t = survival_(t-1) * q
```

The generated marginal PD term structure is validated so term cumulative PD remains no
greater than 1. The default upside/base/downside hazard multipliers and LGD add-ons are
ordered coherently for risk economics. Scenario weights, hazard multipliers, and LGD add-ons
are carried into the scenario-level report for result-level auditability.

EAD, LGD, remaining maturity, effective interest rate, DPD, SICR, credit-impaired/defaulted
flags, and prior stage remain explicit account assumptions. They are not inferred from
Project 1 outcomes. The committed demo samples eight synthetic accounts evenly across the
latest PD cohort's recalibrated-PD distribution, assigns `SYN-PD-ECL-` account IDs, and adds
illustrative non-PD assumptions that are independent of `actual_default`.

Reporting-date `gross_exposure` stays independent from the forward EAD path. The bridge uses
a transparent straight-line fully amortising EAD proxy for monthly ECL calculation; it is a
teaching simplification, not a contractual cash-flow engine.

## Staging Policy

Staging is configurable through `StagingPolicy`.

Default policy:

- Stage 3 has precedence for `credit_impaired=True`, optional `defaulted=True`, or the
  configurable 90-days-past-due backstop.
- Stage 2 applies for `sicr=True` or the configurable 30-days-past-due backstop.
- Stage 1 applies otherwise.

The 30/90 DPD settings are model policy backstops/rebuttable presumptions for this demo,
not universal automatic accounting conclusions.

## SICR Rebuttal Governance

IFRS 9 treats payments more than 30 days past due as a rebuttable SICR presumption. The
presumption can be rebutted only when reasonable and supportable evidence shows that a
significant increase in credit risk has not occurred. This project implements that narrow
governance decision; it does not allow a rebuttal to override an explicit SICR indicator,
credit-impaired/default status, or the Stage 3 DPD backstop.

```python
from ifrs9_ecl_engine import SICRRebuttal, run_ecl_engine

decision = SICRRebuttal(
    rebuttal_id="SICR-REB-001",
    account_id="SYN-ECL-003",
    observed_days_past_due=36,
    evidence_reference="SYN-EVIDENCE-001",
    evidence_summary="Administrative delay with unchanged forward risk",
    reasonable_and_supportable=True,
    forward_looking_review_completed=True,
    other_sicr_indicators_present=False,
    decision_date="2023-12-20",
    valid_until="2024-03-31",
    approval_status="approved",
    approved_by="Synthetic ECL Committee",
)

result = run_ecl_engine(
    accounts,
    term_structures,
    scenario_weights,
    reporting_date="2023-12-31",
    sicr_rebuttals=(decision,),
)
```

The engine checks unique decision and account scope, current DPD against observed evidence,
reasonable-and-supportable and forward-looking flags, decision validity dates, approval
status, and named approver. Approved evidence bypasses only the 30 DPD Stage 2 backstop.
Pending, rejected, expired, stale, incomplete, inapplicable, and precedence-blocked requests
remain visible in the decision register without changing stage.

## Quickstart

Create or reuse a Python environment, then run from this project directory:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
ruff check src tests scripts
pytest
python scripts\run_pipeline.py
python scripts\run_macro_overlay.py
python scripts\run_sicr_rebuttal.py
python scripts\run_cashflow_sensitivity.py
```

The default CLI writes:

- `reports/account_ecl.csv`
- `reports/scenario_ecl.csv`
- `reports/portfolio_summary.csv`
- `reports/stage_migration.csv`
- `reports/ecl_report.md`

The macro/overlay governance CLI writes:

- `reports/macro_overlay/macro_sensitivity_summary.csv`
- `reports/macro_overlay/macro_sensitivity_detail.csv`
- `reports/macro_overlay/management_overlay_register.csv`
- `reports/macro_overlay/ecl_reconciliation.csv`
- `reports/macro_overlay/macro_overlay_report.md`

The SICR rebuttal governance CLI writes:

- `reports/sicr_rebuttal/sicr_rebuttal_register.csv`
- `reports/sicr_rebuttal/account_stage_comparison.csv`
- `reports/sicr_rebuttal/ecl_impact_reconciliation.csv`
- `reports/sicr_rebuttal/sicr_rebuttal_report.md`

The contractual cash-flow sensitivity CLI writes:

- `reports/cashflow_sensitivity/contractual_schedule.csv`
- `reports/cashflow_sensitivity/recovery_assumptions.csv`
- `reports/cashflow_sensitivity/monthly_portfolio_projection.csv`
- `reports/cashflow_sensitivity/account_ecl_sensitivity.csv`
- `reports/cashflow_sensitivity/cashflow_sensitivity_summary.csv`
- `reports/cashflow_sensitivity/cashflow_reconciliation.csv`
- `reports/cashflow_sensitivity/cashflow_sensitivity_report.md`

Run the Project 1 PD integration bridge:

```powershell
python scripts\run_pd_integration.py
```

The PD integration CLI writes:

- `reports/pd_integration/input_audit.csv`
- `reports/pd_integration/account_ecl.csv`
- `reports/pd_integration/scenario_ecl.csv`
- `reports/pd_integration/portfolio_summary.csv`
- `reports/pd_integration/stage_migration.csv`
- `reports/pd_integration/pd_integration_report.md`

The six text artefacts use stable ordering, fixed float formatting, and LF line endings so
repeated runs are byte-reproducible across Windows and Linux.

You can override the source, reporting date, sample size, or output location:

```powershell
python scripts\run_pd_integration.py `
  --prediction-path ..\credit-risk-pd-model\reports\oot_predictions.csv `
  --reporting-date 2022-12-01 `
  --sample-size 8 `
  --output-dir reports\pd_integration
```

You can redirect output:

```powershell
python scripts\run_pipeline.py --output-dir reports\scratch
```

## Input Schema

`accounts` contains one row per reporting-date account snapshot:

| Column | Meaning |
| --- | --- |
| `account_id` | Unique account identifier |
| `days_past_due` | Reporting-date DPD, nonnegative integer |
| `sicr` | Boolean significant-increase-in-credit-risk indicator |
| `credit_impaired` | Boolean credit-impaired indicator |
| `defaulted` | Optional boolean default indicator; defaults to `False` when omitted |
| `prior_stage` | Prior reporting stage, one of 1, 2, or 3 |
| `effective_interest_rate` | Annual effective interest rate, greater than -1 |
| `gross_exposure` | Reporting-date gross exposure, nonnegative |

`term_structures` contains one row per account/scenario/month:

| Column | Meaning |
| --- | --- |
| `account_id` | Account identifier present in `accounts` |
| `scenario` | Scenario name with an explicit weight |
| `month` | Positive integer month |
| `marginal_pd` | Marginal monthly PD in `[0, 1]` |
| `lgd` | LGD in `[0, 1]` |
| `ead` | Exposure at default, nonnegative |

The cash-flow adapter replaces supplied LGD/EAD paths with two governed inputs:

- `contractual_schedule`: one unique positive month per account with nonnegative contractual
  principal; each account schedule must be contiguous, share the PD horizon, and fully
  amortise reporting-date gross exposure.
- `recovery_assumptions`: exactly one row per account/scenario with annual CPR, cure rate and
  delay, collateral value/haircut/recovery cost and delay, plus strict integral/separate-
  recognition eligibility flags.

Sensitivity definitions require unique non-empty case IDs, exactly one neutral baseline,
finite nonnegative multipliers/add-ons, nonnegative integer delays, and adjusted CPR, cure,
and haircut rates that remain in `[0, 1]`.

## Output Schema

`account_ecl.csv` includes relevant staging inputs, the normalized `defaulted` flag,
assigned stage, stage reason, reporting-date gross exposure, weighted ECL, and coverage
ratio.

`scenario_ecl.csv` includes account/scenario rows, stage reason, ECL horizon, months
included, effective interest rate, scenario weight, scenario ECL, and weighted scenario ECL.

`portfolio_summary.csv` aggregates account count, gross exposure, weighted ECL, and
coverage ratio by stage and total.

`stage_migration.csv` aggregates prior-stage to current-stage movement.

`macro_sensitivity_summary.csv` reports modelled ECL, baseline change, and coverage by
controlled case. `macro_sensitivity_detail.csv` discloses every scenario weight, ECL
multiplier, original scenario ECL, stressed ECL, and weighted contribution.

`management_overlay_register.csv` retains trigger evidence, amount requested, cap, overlap
assessment, approval evidence, control outcome, and recognized amount for every request.
`ecl_reconciliation.csv` bridges baseline modelled ECL to the separately recognized overlay
and illustrative reported ECL while disclosing the highest sensitivity as not booked.

`sicr_rebuttal_register.csv` preserves the evidence, approval, control outcome, and
before/after stage for every request. `account_stage_comparison.csv` isolates account-level
stage and ECL changes, while `ecl_impact_reconciliation.csv` proves the portfolio accounting
identity and reconciles stage counts before and after governed decisions.

`monthly_portfolio_projection.csv` aggregates contractual principal, prepayment, opening EAD,
closing balance, cure/collateral recovery, and EAD-weighted LGD by case/scenario/month.
`account_ecl_sensitivity.csv` attributes every case delta to accounts, while
`cashflow_reconciliation.csv` proves each portfolio ECL equals the summed account ECL.

## Committed Synthetic Results

The committed report artefacts are generated from deterministic synthetic accounts whose
IDs begin with `SYN-ECL-`. They include Stage 1, Stage 2, and Stage 3 examples across base,
upside, and downside scenarios. The term structures are generated from assumed marginal PD,
LGD, and amortising EAD paths. They do not use observed future defaults.

The outputs are intended to support interview discussion about staging, 12-month vs
lifetime ECL, discounting, scenario weighting, coverage ratios, and portfolio migration.

## Committed Macro and Overlay Results

Baseline modelled ECL is `27,996.92` on `554,000.00` synthetic gross exposure. Shifting 10
percentage points from base to downside raises ECL by `2,202.44`; increasing downside
severity by 10% raises it by `1,139.25`; combining both raises it by `3,797.39` or `13.56%`.
These sensitivities are disclosed but not booked.

Three synthetic overlay requests demonstrate distinct outcomes. The approved, triggered,
non-overlapping request is capped from `4,000.00` to `2,239.75`, equal to 8% of baseline
modelled ECL. A broad macro request is blocked as double counting, and a distinct
concentration request remains unrecognized while approval is pending. Illustrative reported
ECL is therefore `30,236.67`, with a `5.46%` coverage ratio.

## Committed PD Integration Results

The committed `reports/pd_integration/` outputs are generated from Project 1's committed
synthetic `reports/oot_predictions.csv`. The bridge selects the latest cohort by default,
samples evenly across recalibrated PD, and writes small recruiter-readable artefacts. It does
not write the full monthly term-structure table because that would add noise to the public
repository.

The lineage file documents the Project 1 customer ID, synthetic Project 2 account ID,
reporting date, recalibrated PD, annual hazard, explicit account assumptions, and EAD method.
The scenario file records the scenario weight, hazard multiplier, and LGD add-on alongside
scenario-level ECL.
No `actual_default` column is present in the PD integration input audit or account result.

## Committed SICR Rebuttal Results

The deterministic case contains three synthetic requests: one approved and effective, one
pending, and one blocked because an explicit SICR indicator takes precedence. The effective
request moves one account from Stage 2 lifetime ECL to Stage 1 12-month ECL. Modelled
portfolio ECL changes from `29,234.32` to `27,071.32`, an impact of `2,163.00` or `7.40%`.
This is a controlled synthetic accounting impact used to test staging and reconciliation;
it is not a business benefit, cost saving, or recommendation to minimize ECL.

## Committed Cash-flow Sensitivity Results

The deterministic case uses six contractual repayment profiles over a common 36-month
horizon, including level amortisation, 24-month amortisation, partial balloons, and a bullet
maturity. Recovery assumptions vary by account and base/upside/downside scenario. One
separately recognized guarantee is deliberately excluded to exercise the eligibility control.

Baseline modelled ECL is `18,103.39` with a `3.27%` coverage ratio. Halving prepayment adds
`888.06` (`4.91%`), reducing cure rates by 35% adds `2,905.48` (`16.05%`), collateral downturn
adds `6,180.36` (`34.14%`), and a six-month recovery delay adds `2,267.14` (`12.52%`). The
combined downside reaches `31,215.46`, a `13,112.07` (`72.43%`) increase. Every case preserves
staging and reconciles exactly from account ECL to portfolio ECL, isolating assumption risk
from stage migration.

## Validation

The public API validates:

- Required columns
- Non-empty inputs
- Unique account IDs
- Non-empty account IDs and scenario names
- One term row per account/scenario/month
- Finite numeric values
- Positive integer months
- PD and LGD in `[0, 1]`
- EAD nonnegative
- Reporting-date gross exposure nonnegative
- Effective interest rate greater than -1
- Strict boolean staging flags, including optional `defaulted`
- `prior_stage` in `{1, 2, 3}`
- Scenario coverage and coherent account/scenario horizons
- Contiguous monthly terms
- Cumulative marginal PD by account/scenario not greater than 1
- Nonnegative scenario weights summing to 1
- Positive policy thresholds when configured
- PD bridge reporting-date selection
- One-to-one PD snapshot to account-assumption joins
- Missing or extra account-assumption records
- Recalibrated PD range `[0, 1)`
- Positive integer remaining maturity
- Scenario hazard multipliers, weights, names, LGD add-ons, and economic ordering
- Exactly one macro-sensitivity baseline matching modelled scenario weights
- Complete scenario coverage, weights summing to 1, and nonnegative severity multipliers
- Unique overlay IDs and risk-driver/scope pairs
- Valid trigger operators, overlap assessments, approval statuses, and finite amounts
- Named approver for approved overlays and caps between 0% and 100% of modelled ECL
- Model-to-baseline ECL reconciliation and separate non-booked sensitivity disclosure
- Required reporting date, unique request/account scope, and current-DPD evidence matching
- Reasonable-and-supportable evidence, forward-looking review, validity, and approval checks
- Stage 3 and explicit-SICR precedence over a 30 DPD rebuttal
- Account-to-portfolio stage-count and ECL-impact reconciliation
- Unique contractual account/month and marginal-PD account/scenario/month keys
- Contractual schedules that fully amortise exposure over the same contiguous PD horizon
- Annual CPR, cure, haircut, cost, collateral value, and recovery-delay domains
- Integral/not-separately-recognized collateral eligibility with explicit exclusion reasons
- Exactly one neutral cash-flow baseline and adjusted sensitivity rates constrained to `[0, 1]`
- Cash-flow account-to-portfolio ECL reconciliation for every sensitivity case

## Limitations

This is deliberately small and transparent. It does not implement financial asset
classification, a full direct contractual-versus-expected cash-shortfall valuation,
behaviourally estimated prepayment/cure models, independent collateral appraisal, write-offs,
macroeconomic model estimation, real SICR evidence assessment, audit workflow, production
disclosure, or institution-specific IFRS 9 and management-overlay policy.

Contractual schedules, cure rates, collateral values, haircuts, recovery costs, and delays are
synthetic assumptions. The cash-flow adapter demonstrates balance roll-forward, recovery
discounting, eligibility, sensitivity, and reconciliation controls; it does not establish
reasonable and supportable forecasts, legal enforceability, or accounting scope for real
credit enhancements.

The overlay trigger metrics, risk assessments, committee name, requested amounts, and caps
are synthetic. The governance controls demonstrate process and reconciliation, but they do
not establish empirical risk emergence, accounting materiality, expert-judgement quality,
or approval by a real institution.

The rebuttal evidence references, explanations, committee decisions, and validity dates are
also synthetic. The workflow demonstrates enforceable controls but cannot establish that a
real 30 DPD rebuttal is reasonable and supportable under an institution's approved policy.

Stage 3 uses the same transparent marginal-PD/LGD/EAD proxy as the other stages. It does
not implement a production credit-impaired cash-shortfall methodology or interest-revenue
recognition treatment.

The Project 1 integration bridge assumes a constant annual hazard to extrapolate a
12-month cumulative recalibrated PD into monthly lifetime marginal PDs. This is suitable for
an auditable portfolio demonstration, but not sufficient for IFRS 9 compliance, macroeconomic
model governance, SICR policy approval, or audited financial reporting.

## IFRS Foundation References

- [IFRS 9 Financial Instruments, paragraph 5.5.11](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2022/issued/part-a/ifrs-9-financial-instruments.pdf?bypass=on)
- [IFRS 9 impairment staff paper: collateral and other credit enhancements](https://www.ifrs.org/content/dam/ifrs/meetings/2015/december/itg/impairment-of-financial-instruments/ap5-collateral-and-other-credit-enhancements.pdf)
- [IFRIC Update, March 2019: credit enhancement in ECL measurement](https://www.ifrs.org/news-and-events/updates/ifric/2019/ifric-update-march-2019/)
- [IFRS 9 project summary](https://www.ifrs.org/content/dam/ifrs/project/fi-hedge-accounting/ifrs-standard/project-summary.pdf)
- [IFRS 9 and coronavirus uncertainty](https://www.ifrs.org/news-and-events/news/2020/03/application-of-ifrs-9-in-the-light-of-the-coronavirus-uncertainty/)
- [Forward-looking information and multiple scenarios](https://www.ifrs.org/news-and-events/news/2016/07/25-webcast-on-ifrs-9/)

## Resume Bullets

- Built a runnable IFRS 9 ECL foundation in Python, calculating account-level and
  portfolio-level expected credit loss from staging policy, monthly PD/LGD/EAD term
  structures, discounting, and explicit scenario weights.
- Connected synthetic Project 1 recalibrated out-of-time PD outputs to Project 2 ECL inputs
  through a validated public adapter with leakage controls, explicit account assumptions,
  scenario hazard multipliers, and reproducible recruiter-readable reports.
- Added deterministic synthetic ECL reports covering Stage 1, Stage 2, Stage 3, stage
  migration, scenario-level ECL, gross exposure, weighted ECL, and coverage ratio.
- Built a separate ECL governance layer that quantified a `13.56%` combined downside
  sensitivity, blocked a duplicate macro-risk overlay, enforced approval and an 8% cap, and
  reconciled `27,996.92` modelled ECL to `30,236.67` illustrative reported ECL.
- Implemented governed 30 DPD rebuttal decisions with evidence, forward-looking, DPD/date,
  approval, and precedence controls; in a synthetic case, one of three requests moved Stage
  2 to Stage 1 and produced a reconciled `2,163.00` (`7.40%`) ECL impact.
- Built a contractual cash-flow adapter covering CPR-driven EAD roll-forward, cure timing,
  collateral eligibility/haircut/cost, and discounted recovery; quantified four isolated
  assumption shocks and a combined synthetic downside that increased ECL by `13,112.07`
  (`72.43%`), with exact account-to-portfolio reconciliation.
