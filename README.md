# Risk Analytics Portfolio

Portfolio of practical risk analytics projects for credit risk, model risk, and fintech lending roles.

The repository is built around a candidate profile that combines economics, computer science, FRM knowledge, Python, SQL, PostgreSQL, and machine learning. The goal is to show bank-style risk thinking rather than generic notebook-based machine learning.

## Projects

| Project | Status | Target roles | Main evidence |
| --- | --- | --- | --- |
| [Credit Risk PD Modelling](projects/credit-risk-pd-model) | Implemented | Credit Risk Analyst, Risk Analytics Analyst, Model Validation Analyst | PD model pipeline, pre-OOT model selection, PD recalibration, approval strategy scenarios, WOE/IV screening, permutation importance, PSI monitoring, SQL schema |
| [IFRS 9 ECL Engine](projects/ifrs9-ecl-engine) | Planned | Credit Risk Analyst, ECL Analyst, Portfolio Risk Analyst | PD/LGD/EAD, staging, lifetime ECL, macro scenario weighting |
| [Model Validation Framework](projects/model-validation-framework) | Planned | Model Risk Analyst, Validation Analyst, Quant Risk Analyst | Backtesting, benchmarking, calibration, drift monitoring, validation report |

## Project 1: Credit Risk PD Modelling

The first project builds an end-to-end probability of default workflow:

```text
LendingClub raw-data ingestion
-> data checks
-> feature engineering
-> out-of-time split
-> logistic regression baseline
-> random forest challenger
-> pre-OOT calibration holdout model selection
-> discrimination metrics
-> logistic PD recalibration
-> fixed lending approval cutoff scenarios
-> calibration review on untouched OOT data
-> scorecard-style WOE/IV screening
-> permutation importance
-> PSI drift monitoring
-> report artefacts
```

Key outputs:

- `reports/model_metrics.csv`: ROC-AUC, Gini, KS, Brier score, and threshold-based metrics with the fixed evaluation threshold recorded
- `reports/model_selection_audit.csv`: pre-OOT model-development and calibration-holdout split audit
- `reports/recalibration_summary.csv`: fitted pre-OOT recalibration parameters and raw vs recalibrated OOT diagnostics
- `reports/approval_strategy.csv`: fixed max-PD approval scenarios using disclosed LGD and `loan_amount` as the EAD proxy
- `reports/calibration_table.csv`: decile-level predicted PD vs observed default rate
- `reports/woe_bins.csv`: scorecard-style Weight of Evidence bins on the development sample
- `reports/woe_summary.csv`: feature-level Information Value ranking for variable screening
- `reports/feature_importance.csv`: selected-model permutation importance on the out-of-time sample
- `reports/psi_report.csv`: feature-level population stability monitoring
- `reports/oot_predictions.csv`: account-level out-of-time PD predictions

Example result from the synthetic development sample:

| Model | ROC-AUC | Gini | KS | Brier score |
| --- | ---: | ---: | ---: | ---: |
| Logistic regression raw | 0.710 | 0.421 | 0.342 | 0.194 |
| Logistic regression recalibrated | 0.710 | 0.421 | 0.342 | 0.141 |
| Random forest raw | 0.687 | 0.373 | 0.303 | 0.188 |

The synthetic data intentionally includes a stressed 2022 out-of-time period. The PSI report flags interest-rate distribution shift as material, which creates a realistic monitoring discussion for interviews.

Project 1 also includes an auditable adapter for the user-downloaded
[LendingClub accepted-loans dataset](https://www.kaggle.com/datasets/wordsforthewise/lending-club).
It prepares `accepted_2007_to_2018Q4.csv.gz` into the canonical PD schema, writes an
ingestion audit, and keeps the committed demo reports synthetic. Public-data outputs should
remain local unless they are reviewed and intentionally added without raw or borrower-level
processed data.

## Repository Layout

```text
risk-analytics-portfolio/
  .github/workflows/
  .vscode/
  docs/
  projects/
    credit-risk-pd-model/
      data/
      reports/
      scripts/
      sql/
      src/credit_risk_pd/
      tests/
    ifrs9-ecl-engine/
    model-validation-framework/
```

## Quickstart

Clone and open the repository:

```powershell
git clone https://github.com/sheenwinkle/risk-analytics-portfolio.git
cd risk-analytics-portfolio
code .
```

Create the Python environment for Project 1:

```powershell
cd projects/credit-risk-pd-model
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

Run the pipeline:

```powershell
python scripts/run_pipeline.py
```

Run the tests:

```powershell
ruff check src tests scripts
pytest
```

## VS Code and Codex Workflow

This repository is intended to be developed iteratively with VS Code and Codex CLI:

```powershell
codex exec -C . -s workspace-write "Improve the Credit Risk PD project by adding one focused, tested enhancement. Keep the change small and update documentation."
```

Recommended iteration cycle:

1. Create a GitHub issue or short local task.
2. Ask Codex CLI to implement one focused enhancement.
3. Run `ruff check src tests scripts` and `pytest` from `projects/credit-risk-pd-model`.
4. Review the diff in VS Code.
5. Commit and push to a feature branch.
6. Open or update a pull request.

Detailed instructions are in [docs/vscode-codex-iteration.md](docs/vscode-codex-iteration.md).

## Resume Positioning

Suggested one-line project description:

> Built a Python and SQL credit risk analytics portfolio covering LendingClub ingestion, probability of default modelling, out-of-time validation, model calibration, scorecard-style WOE/IV screening, permutation importance, PSI monitoring, and planned IFRS 9 ECL and model validation extensions.

Suggested bullet:

> Developed an end-to-end credit risk PD modelling workflow using Python, scikit-learn, and SQL, including LendingClub raw-data preparation, leakage-safe pre-OOT model selection, logistic PD recalibration, fixed approval cutoff scenario analysis, WOE/IV variable screening, permutation importance, and PSI drift monitoring.

## Roadmap

Next improvements:

- Run the LendingClub accepted-loans adapter on the user-downloaded public dataset and compare diagnostics with the committed synthetic demo reports.
- Add public-data WOE/IV interpretation notes once prepared LendingClub reports are generated locally.
- Build the IFRS 9 ECL engine using Project 1 PD outputs.
- Build the reusable model validation framework and validation report.

