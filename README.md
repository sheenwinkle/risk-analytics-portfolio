# Risk Analytics Portfolio

Portfolio of practical risk analytics projects for credit risk, model risk, and fintech lending roles.

The repository is built around a candidate profile that combines economics, computer science, FRM knowledge, Python, SQL, PostgreSQL, and machine learning. The goal is to show bank-style risk thinking rather than generic notebook-based machine learning.

## Projects

| Project | Status | Target roles | Main evidence |
| --- | --- | --- | --- |
| [Credit Risk PD Modelling](projects/credit-risk-pd-model) | Implemented | Credit Risk Analyst, Risk Analytics Analyst, Model Validation Analyst | PD model pipeline, out-of-time validation, calibration, PSI monitoring, SQL schema |
| [IFRS 9 ECL Engine](projects/ifrs9-ecl-engine) | Planned | Credit Risk Analyst, ECL Analyst, Portfolio Risk Analyst | PD/LGD/EAD, staging, lifetime ECL, macro scenario weighting |
| [Model Validation Framework](projects/model-validation-framework) | Planned | Model Risk Analyst, Validation Analyst, Quant Risk Analyst | Backtesting, benchmarking, calibration, drift monitoring, validation report |

## Project 1: Credit Risk PD Modelling

The first project builds an end-to-end probability of default workflow:

```text
Data checks
-> feature engineering
-> out-of-time split
-> logistic regression baseline
-> random forest challenger
-> discrimination metrics
-> calibration review
-> PSI drift monitoring
-> report artefacts
```

Key outputs:

- `reports/model_metrics.csv`: ROC-AUC, Gini, KS, Brier score, precision, recall, and confusion matrix values
- `reports/calibration_table.csv`: decile-level predicted PD vs observed default rate
- `reports/psi_report.csv`: feature-level population stability monitoring
- `reports/oot_predictions.csv`: account-level out-of-time PD predictions

Example result from the synthetic development sample:

| Model | ROC-AUC | Gini | KS | Brier score |
| --- | ---: | ---: | ---: | ---: |
| Logistic regression | 0.714 | 0.429 | 0.362 | 0.197 |
| Random forest | 0.698 | 0.396 | 0.337 | 0.192 |

The synthetic data intentionally includes a stressed 2022 out-of-time period. The PSI report flags interest-rate distribution shift as material, which creates a realistic monitoring discussion for interviews.

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
codex exec --cd . --sandbox workspace-write --ask-for-approval never "Improve the Credit Risk PD project by adding one focused, tested enhancement. Keep the change small and update documentation."
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

> Built a Python and SQL credit risk analytics portfolio covering probability of default modelling, out-of-time validation, model calibration, PSI monitoring, and planned IFRS 9 ECL and model validation extensions.

Suggested bullet:

> Developed an end-to-end credit risk PD modelling workflow using Python, scikit-learn, and SQL, benchmarking interpretable and challenger models with ROC-AUC, Gini, KS, Brier score, calibration deciles, and PSI drift monitoring.

## Roadmap

Next improvements:

- Replace synthetic data with a public lending dataset transformation pipeline.
- Add scorecard-style binning and Weight of Evidence features.
- Add SHAP or permutation importance for explainability.
- Build the IFRS 9 ECL engine using Project 1 PD outputs.
- Build the reusable model validation framework and validation report.

