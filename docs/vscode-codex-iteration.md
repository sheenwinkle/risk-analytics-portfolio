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
codex exec -C . -s workspace-write "Improve the Credit Risk PD project with one focused enhancement. Run the baseline suite first; add focused tests; then run the full suite, pipeline, and git diff --check. Update docs, but do not commit or push."
```

Good prompts:

```text
Add PD recalibration diagnostics and compare calibration intercept and slope on the out-of-time sample. Include tests, report outputs, and README documentation.
```

```text
Add a lending approval threshold strategy that reports approval rate, default rate, and expected loss trade-offs. Include tests and a report artefact.
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
$pytestTemp = ".pytest-tmp-$([guid]::NewGuid().ToString('N'))"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp=$pytestTemp
.\.venv\Scripts\python.exe scripts\run_pipeline.py
git diff --check
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
- Scorecard-style binning, Weight of Evidence, and Information Value screening.

High-impact next tasks:

1. Add a public lending dataset raw-to-model-schema transformation script.
2. Add PD recalibration and lending threshold strategy analysis.
3. Add an IFRS 9 ECL account-level calculation module.
4. Add a model validation framework that consumes Project 1 outputs.

Work on one task per branch. The GitHub history should look deliberate and professional.
