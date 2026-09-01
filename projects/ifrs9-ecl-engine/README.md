# IFRS 9 ECL Engine Foundation

Status: implemented foundation with a synthetic Project 1 PD integration bridge.

This project is a runnable, educational expected credit loss engine for credit risk
analytics portfolio discussion. It calculates account-level and portfolio-level ECL from
reporting-date account snapshots, monthly PD/LGD/EAD term structures, staging rules, and
explicit macro scenario weights.

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

## Quickstart

Create or reuse a Python environment, then run from this project directory:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
ruff check src tests scripts
pytest
python scripts\run_pipeline.py
```

The default CLI writes:

- `reports/account_ecl.csv`
- `reports/scenario_ecl.csv`
- `reports/portfolio_summary.csv`
- `reports/stage_migration.csv`
- `reports/ecl_report.md`

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

## Output Schema

`account_ecl.csv` includes relevant staging inputs, the normalized `defaulted` flag,
assigned stage, stage reason, reporting-date gross exposure, weighted ECL, and coverage
ratio.

`scenario_ecl.csv` includes account/scenario rows, stage reason, ECL horizon, months
included, effective interest rate, scenario weight, scenario ECL, and weighted scenario ECL.

`portfolio_summary.csv` aggregates account count, gross exposure, weighted ECL, and
coverage ratio by stage and total.

`stage_migration.csv` aggregates prior-stage to current-stage movement.

## Committed Synthetic Results

The committed report artefacts are generated from deterministic synthetic accounts whose
IDs begin with `SYN-ECL-`. They include Stage 1, Stage 2, and Stage 3 examples across base,
upside, and downside scenarios. The term structures are generated from assumed marginal PD,
LGD, and amortising EAD paths. They do not use observed future defaults.

The outputs are intended to support interview discussion about staging, 12-month vs
lifetime ECL, discounting, scenario weighting, coverage ratios, and portfolio migration.

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

## Limitations

This is deliberately small and transparent. It does not implement financial asset
classification, contractual cash flow modelling, prepayment, cures, collateral valuation,
write-offs, overlays, macroeconomic model estimation, SICR rebuttal documentation, audit
workflow, disclosure production, or institution-specific IFRS 9 policy.

Stage 3 uses the same transparent marginal-PD/LGD/EAD proxy as the other stages. It does
not implement a production credit-impaired cash-shortfall methodology or interest-revenue
recognition treatment.

The Project 1 integration bridge assumes a constant annual hazard to extrapolate a
12-month cumulative recalibrated PD into monthly lifetime marginal PDs. This is suitable for
an auditable portfolio demonstration, but not sufficient for IFRS 9 compliance, macroeconomic
model governance, SICR policy approval, or audited financial reporting.

## IFRS Foundation References

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

