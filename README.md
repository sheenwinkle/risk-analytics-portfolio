# Risk Analytics Portfolio

Portfolio of practical risk analytics projects for credit risk, model risk, and fintech lending roles.

The repository is built around a candidate profile that combines economics, computer science, FRM knowledge, Python, SQL, PostgreSQL, and machine learning. The goal is to show bank-style risk thinking rather than generic notebook-based machine learning.

## Projects

| Project | Status | Target roles | Main evidence |
| --- | --- | --- | --- |
| [Credit Risk PD Modelling](projects/credit-risk-pd-model) | Implemented | Credit Risk Analyst, Risk Analytics Analyst, Model Validation Analyst | PD model pipeline, out-of-time validation, calibration, WOE/IV screening, permutation importance, PSI monitoring, SQL schema |
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
-> discrimination metrics
-> calibration review
-> scorecard-style WOE/IV screening
-> permutation importance
-> PSI drift monitoring
-> report artefacts
```

Key outputs:

- `reports/model_metrics.csv`: ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix values
- `reports/calibration_table.csv`: decile-level predicted PD vs observed default rate
- `reports/woe_bins.csv`: scorecard-style Weight of Evidence bins on the development sample
- `reports/woe_summary.csv`: feature-level Information Value ranking for variable screening
- `reports/feature_importance.csv`: selected-model permutation importance on the out-of-time sample
- `reports/psi_report.csv`: feature-level population stability monitoring
- `reports/oot_predictions.csv`: account-level out-of-time PD predictions

Example result from the synthetic development sample:

| Model | ROC-AUC | Gini | KS | Brier score |
| --- | ---: | ---: | ---: | ---: |
| Logistic regression | 0.714 | 0.429 | 0.362 | 0.197 |
| Random forest | 0.698 | 0.396 | 0.337 | 0.192 |

The synthetic data intentionally includes a stressed 2022 out-of-time period. The PSI report flags interest-rate distribution shift as material, which creates a realistic monitoring discussion for interviews.

Project 1 also includes an auditable adapter for the user-downloaded
[LendingClub accepted-loans dataset](https://www.kaggle.com/datasets/wordsforthewise/lending-club).
It prepares `accepted_2007_to_2018Q4.csv.gz` into the canonical PD schema, writes an
ingestion audit, and keeps the committed demo reports synthetic.

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
3. Run `pytest` from `projects/credit-risk-pd-model`.
4. Review the diff in VS Code.
5. Commit and push to a feature branch.
6. Open or update a pull request.

Detailed instructions are in [docs/vscode-codex-iteration.md](docs/vscode-codex-iteration.md).

## Resume Positioning

Suggested one-line project description:

> Built a Python and SQL credit risk analytics portfolio covering LendingClub ingestion, probability of default modelling, out-of-time validation, model calibration, scorecard-style WOE/IV screening, permutation importance, PSI monitoring, and planned IFRS 9 ECL and model validation extensions.

Suggested bullet:

> Developed an end-to-end credit risk PD modelling workflow using Python, scikit-learn, and SQL, including LendingClub raw-data preparation and interpretable/challenger model benchmarking with ROC-AUC, Gini, KS, Brier score, calibration deciles, WOE/IV variable screening, permutation importance, and PSI drift monitoring.

## Roadmap

Next improvements:

- Add PD recalibration and lending threshold strategy analysis.
- Run the LendingClub accepted-loans adapter on the user-downloaded public dataset and compare diagnostics with the committed synthetic demo reports.
- Add public-data WOE/IV interpretation notes once prepared LendingClub reports are generated locally.
- Build the IFRS 9 ECL engine using Project 1 PD outputs.
- Build the reusable model validation framework and validation report.

