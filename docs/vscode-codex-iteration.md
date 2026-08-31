# VS Code and Codex CLI Iteration Guide

This guide is for developing the portfolio from a GitHub repository using VS Code and Codex CLI.

## 1. Open the GitHub Repository in VS Code

Recommended local workflow:

```powershell
git clone https://github.com/sheenwinkle/risk-analytics-portfolio.git
cd risk-analytics-portfolio
code .
```

Alternative VS Code remote repository workflow:

1. Open VS Code.
2. Install the official GitHub Repositories extension if VS Code asks for it.
3. Run `Remote Repositories: Open Remote Repository...` from the Command Palette.
4. Paste `https://github.com/sheenwinkle/risk-analytics-portfolio`.
5. When you need to run Python tests or Codex CLI locally, clone the repository instead of only browsing it remotely.

The local clone workflow is better for this project because the pipeline needs a Python environment, generated reports, tests, and Git commits.

## 2. Prepare Python

From the repository root:

```powershell
cd projects/credit-risk-pd-model
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
pytest
```

## 3. Use Codex CLI for One Focused Iteration

From the repository root:

```powershell
codex exec -C . -s workspace-write "Improve the Credit Risk PD project by adding one focused, tested enhancement. Keep the change small, update docs, and run tests."
```

Good prompts:

```text
Add a scorecard-style feature binning module for numeric credit risk variables. Include tests and README documentation.
```

```text
Add a model validation report generator that writes a Markdown summary from model_metrics.csv, calibration_table.csv, and psi_report.csv. Include tests.
```

```text
Add a public dataset ingestion plan for LendingClub data without committing raw data. Include a transformation script stub and data dictionary updates.
```

Avoid vague prompts such as:

```text
Make the project better.
```

## 4. Review Before Committing

After Codex CLI finishes:

```powershell
git status
git diff
cd projects/credit-risk-pd-model
pytest
python scripts/run_pipeline.py
```

Then commit:

```powershell
git add .
git commit -m "Add focused risk analytics enhancement"
git push
```

## 5. Pull Request Workflow

Create a branch for each enhancement:

```powershell
git switch -c add-validation-report
```

Push and open a PR:

```powershell
git push -u origin add-validation-report
gh pr create --base main --head add-validation-report --title "Add validation report generator"
```

For the current initial portfolio PR:

```powershell
gh pr view 1 --repo sheenwinkle/risk-analytics-portfolio --web
```

## 6. Suggested Iteration Backlog

Completed iterations:

- Markdown model report generator.
- Out-of-time permutation feature importance.

High-impact next tasks:

1. Add scorecard-style binning and Weight of Evidence.
2. Add a public lending dataset raw-to-model-schema transformation script.
3. Add PD recalibration and lending threshold strategy analysis.
4. Add an IFRS 9 ECL account-level calculation module.
5. Add a model validation framework that consumes Project 1 outputs.

Work on one task per branch. The GitHub history should look deliberate and professional.
