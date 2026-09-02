# Credit Risk Model Validation Framework

Independent-style validation of the frozen out-of-time PD scores produced by
[Project 1](../credit-risk-pd-model). The validator consumes only the published
`reports/oot_predictions.csv` contract and does not import model-development code.

This is an educational portfolio case study. It demonstrates model risk methods and
governance judgement, but it is not a regulatory approval, accounting opinion, or
production-use decision.

Status: complete scoped case study with public-data validation, a synthetic adverse-finding
remediation exercise, and tested PostgreSQL governance persistence.

## Public LendingClub Opinion

The independently re-performed public-data checks produce an overall **warning** opinion.
The framework consumes the frozen 225,639-row OOT score contract without importing Project
1's development code.

| Check | Result | Policy status |
| --- | ---: | --- |
| ROC-AUC | 0.699887 | Warning |
| KS | 0.292493 | Warning |
| Absolute calibration gap | 0.026335 | Warning |
| PSI | 0.016656 | Pass |
| Challenger AUC margin | -0.009411 | Pass |

Review the [public validation report](reports/public_lendingclub/validation_report.md) and
[source lineage](reports/public_lendingclub/data_lineage.json). The opinion is explicitly
limited by the accepted-loan population and terminal-outcome target definition.

## Synthetic Governance Candidate

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

## Remediation and Finding Lifecycle

The committed synthetic failure is carried into a sequential remediation exercise rather
than overwritten. A fixed three-month rolling logistic recalibrator uses only prior matured
months for each July-December 2022 validation cohort.

| Evidence | Before | After |
| --- | ---: | ---: |
| Absolute calibration gap | 0.064441 (fail) | 0.009218 (pass) |
| Brier score | 0.130625 | 0.125430 |
| ROC-AUC | 0.685203 | 0.683521 |

The finding remains `pending_fresh_oot`: passing the sequential retest is remediation
evidence, but it is not treated as independent closure evidence. See the
[remediation report](reports/remediation/remediation_report.md).

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
-> sequential calibration remediation and closure decision
-> PostgreSQL governance history
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
- context-specific limitations for synthetic and public LendingClub evidence
- no-look-ahead rolling remediation with explicit closure status
- PostgreSQL persistence for runs, metrics, findings, benchmarks, limitations, and finding events

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
    public_lendingclub/   safe aggregate public-data validation
    remediation/         synthetic finding lifecycle evidence
  scripts/               validation, publication, remediation, and database loaders
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
- `remediation.py`: sequential rolling recalibration and closure decision
- `publication.py`: privacy-safe public aggregate publisher
- `postgres.py`: transactional governance persistence

## Quickstart

The preferred portfolio-wide run from the repository root is:

```powershell
.\scripts\setup_and_run.ps1
```

For a standalone Project 3 environment:

```powershell
cd projects\model-validation-framework
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
python scripts\run_validation.py
python scripts\run_remediation.py
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
python scripts\run_remediation.py
```

Persist a validation run and remediation lifecycle to PostgreSQL:

```powershell
$env:MODEL_VALIDATION_DATABASE_URL = "postgresql://user:password@localhost:5432/risk_portfolio"
python scripts\load_validation_run.py --apply-schema --persist-remediation
```

The integration test runs against PostgreSQL 16 in GitHub Actions and verifies the inserted
run, metric, finding, benchmark, limitation, and three finding-event records.

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

`reports/public_lendingclub/` contains the same aggregate validation contract for the full
public-data run. `reports/remediation/` contains monthly sequential retest evidence, a
summary, finding lifecycle events, and a reviewer-readable report.

The PostgreSQL schema and loader under `sql/` and `scripts/` retain validation runs, policy
metrics, findings, limitations, challenger results, remediation retests, and closure decisions
for governance reporting.

## Limitations

- The public run is an accepted-loan sample and does not represent rejected applicants.
- `actual_default` is a terminal-outcome proxy, not a fully serviced default-window label.
- Neither the public nor synthetic OOT evidence spans a full credit cycle.
- Validation starts from frozen scores and outcomes; it does not independently rebuild
  features or replicate model estimation.
- Policy thresholds are illustrative and require institution-specific governance approval.
- The sequential remediation retest shares historical data with development and therefore
  cannot close the finding without a fresh independent OOT window.

## Resume Description

> Built a reusable Python and PostgreSQL model validation framework that independently
> re-performed AUC, Gini, tie-safe KS, Brier score, calibration, monthly backtesting, PSI,
> and challenger analysis on 225,639 public OOT observations; implemented policy opinions,
> no-look-ahead remediation testing, finding lifecycle persistence, and deterministic evidence.

## Interview Discussion

The strongest discussion point is not the AUC. The candidate retains useful rank ordering,
but recalibrated mean PD is materially below the stressed OOT default rate. A validator should
raise that finding, investigate portfolio mix and calibration-window representativeness, and
require fresh calibration evidence rather than approving the model because discrimination is
acceptable.
