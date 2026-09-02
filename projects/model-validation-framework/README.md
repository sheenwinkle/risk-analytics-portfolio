# Credit Risk Model Validation Framework

Independent-style validation of the frozen out-of-time PD scores produced by
[Project 1](../credit-risk-pd-model). The validator consumes only the published
`reports/oot_predictions.csv` contract and does not import model-development code.

This is an educational portfolio case study. It demonstrates model risk methods and
governance judgement, but it is not a regulatory approval, accounting opinion, or
production-use decision.

## Candidate Opinion

The committed synthetic candidate receives an overall **fail** under the illustrative
policy because its recalibrated PD underestimates the 2022 observed default rate. The
framework deliberately preserves that adverse conclusion rather than presenting every
model as acceptable.

| Check | Result | Policy status | Interpretation |
| --- | ---: | --- | --- |
| ROC-AUC | 0.710412 | Pass | Rank ordering exceeds the 0.70 pass threshold |
| KS | 0.341611 | Pass | Default/non-default separation exceeds 0.30 |
| Absolute calibration gap | 0.077097 | **Fail** | Mean PD 9.69% versus observed default rate 17.40% |
| PSI | 0.070689 | Pass | Limited score-distribution movement between 2022 halves |
| Challenger AUC margin | -0.023896 | Pass | Random forest challenger does not outperform the incumbent |

The result supports a clear validation judgement: discrimination and score stability are
acceptable under the configured policy, but calibration requires investigation and fresh
recalibration before any production-use consideration.

## Validation Workflow

```text
Project 1 frozen OOT predictions
-> schema and model-lineage audit
-> independent discrimination and calibration metrics
-> low-to-high PD calibration deciles
-> monthly performance diagnostics
-> reference-period PSI stability analysis
-> incumbent/challenger and recalibration comparisons
-> configurable traffic-light policy
-> findings, limitations, CSV evidence, and Markdown report
```

The implementation includes:

- tie-safe rank AUC and KS calculations implemented independently of Project 1
- Brier score, mean PD, observed default rate, signed and absolute calibration gaps
- deterministic rank deciles with `customer_id` tie-breaking
- monthly AUC and KS reported as unavailable when a month contains only one outcome class
- chronological reference/current score samples split by distinct observation dates
- PSI bins derived only from the reference sample, with midpoint boundaries that do not
  split tied reference scores
- selected-model lineage checks covering both logistic regression and random forest
- incumbent versus challenger benchmarking and raw versus recalibrated impact analysis
- immutable, validated policy thresholds with pass, warning, and fail findings
- deterministic CSV and Markdown outputs with fixed precision and LF line endings

## Input Contract

The default input is `../credit-risk-pd-model/reports/oot_predictions.csv`.

| Column | Validation rule |
| --- | --- |
| `customer_id` | Unique, non-empty string |
| `observation_date` | Parseable date with at least two distinct dates |
| `actual_default` | Binary 0/1 outcome with both classes represented |
| `selected_model` | Exactly one supported model across the file |
| `selected_model_raw_pd` | Row-level match to the selected model's raw PD |
| `logistic_regression_pd` | Finite value in [0, 1] |
| `recalibrated_pd` | Finite value in [0, 1] |
| `random_forest_pd` | Finite value in [0, 1] |

See [data/README.md](data/README.md) for lineage, privacy, and replacement-data guidance.

## Illustrative Policy

Thresholds are explicit and configurable through the frozen `ValidationPolicy` dataclass.
They are portfolio assumptions for this case study, not universal regulatory cutoffs.

| Check | Pass | Warning | Fail |
| --- | --- | --- | --- |
| AUC | >= 0.70 | >= 0.60 and < 0.70 | < 0.60 |
| KS | >= 0.30 | >= 0.20 and < 0.30 | < 0.20 |
| Absolute calibration gap | <= 0.01 | > 0.01 and <= 0.03 | > 0.03 |
| PSI | <= 0.10 | > 0.10 and <= 0.25 | > 0.25 |
| Challenger AUC margin | <= 0.01 | > 0.01 and <= 0.03 | > 0.03 |

The challenger margin is challenger raw AUC minus selected recalibrated incumbent AUC.

## Repository Structure

```text
model-validation-framework/
  data/                  input lineage and privacy notes
  reports/               committed validation evidence
  scripts/               command-line pipeline
  sql/                   PostgreSQL governance schema and queries
  src/model_validation/  validation package
  tests/                 behavioural and reproducibility tests
```

Core modules separate validation responsibilities:

- `validation.py`: adapter, input contract, orchestration, and public result dataclass
- `metrics.py`: discrimination and portfolio calibration metrics
- `calibration.py`: deterministic deciles and monthly backtesting
- `stability.py`: chronological reference/current PSI
- `benchmarking.py`: incumbent, challenger, and recalibration comparisons
- `policy.py`: immutable traffic-light thresholds
- `reporting.py`: policy findings, limitations, CSVs, and Markdown report

## Quickstart

From the repository root:

```powershell
cd projects\model-validation-framework
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
python scripts\run_validation.py
```

Use another compatible score file or output directory:

```powershell
python scripts\run_validation.py `
  --prediction-path C:\path\to\oot_predictions.csv `
  --output-dir C:\path\to\validation-reports
```

Run the self-test gate:

```powershell
ruff check src tests scripts
python -m pytest -p no:cacheprovider
python -m compileall -q src tests scripts
python scripts\run_validation.py
```

## Report Outputs

| File | Purpose |
| --- | --- |
| `reports/input_audit.csv` | Input and model-lineage checks |
| `reports/model_metrics.csv` | AUC, Gini, KS, Brier, and portfolio calibration |
| `reports/calibration_by_decile.csv` | Low-to-high PD decile backtest |
| `reports/monthly_performance.csv` | Monthly calibration and discrimination diagnostics |
| `reports/stability_summary.csv` | Period definitions, bin method, and total PSI |
| `reports/stability_bins.csv` | Reference/current distribution and PSI contribution by bin |
| `reports/benchmark_comparison.csv` | Challenger and recalibration deltas |
| `reports/validation_summary.csv` | Policy thresholds, values, and statuses |
| `reports/validation_findings.csv` | Warning/fail findings and recommended actions |
| `reports/model_limitations.csv` | Limitation and mitigation register |
| `reports/validation_report.md` | Recruiter-readable validation case study |

The PostgreSQL examples under `sql/` show how validation runs, policy metrics, findings,
limitations, and challenger results could be retained for governance reporting.

## Limitations

- Project 1 uses synthetic data, so results do not establish live portfolio performance.
- `actual_default` is a terminal-outcome proxy, not a fully serviced default-window label.
- The OOT sample covers one calendar year and does not span a full credit cycle.
- Validation starts from frozen scores and outcomes; it does not independently rebuild
  features or replicate model estimation.
- Policy thresholds are illustrative and require institution-specific governance approval.

## Resume Description

> Built a reusable Python model validation framework for credit risk PD models, independently
> reperformance-testing AUC, Gini, tie-safe KS, Brier score, calibration deciles, monthly
> backtesting, PSI stability, and incumbent/challenger performance; implemented explicit
> governance thresholds, actionable findings, PostgreSQL reporting schemas, deterministic
> evidence files, and a documented fail opinion for material PD underestimation.

## Interview Discussion

The strongest discussion point is not the AUC. The candidate retains useful rank ordering,
but recalibrated mean PD is materially below the stressed OOT default rate. A validator should
raise that finding, investigate portfolio mix and calibration-window representativeness, and
require fresh calibration evidence rather than approving the model because discrimination is
acceptable.
