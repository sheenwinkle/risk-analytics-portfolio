# VS Code and Codex CLI Iteration Guide

This guide keeps local development, self-testing, and GitHub review consistent across all
three portfolio projects.

## 1. Clone and Open in VS Code

```powershell
git clone https://github.com/sheenwinkle/risk-analytics-portfolio.git
cd risk-analytics-portfolio
code .
```

VS Code's GitHub Repositories extension is useful for browsing, but use a local clone for
Python environments, pipelines, tests, Codex CLI, commits, and public-data processing.

## 2. Create the Shared Environment

From the repository root:

```powershell
.\scripts\setup_and_run.ps1
```

This creates `.venv`, installs all three packages and development dependencies, and regenerates
the deterministic synthetic evidence. The full VS Code self-test task adds tests and committed
evidence verification. VS Code is configured to discover the shared interpreter and all project
test directories.

Useful Command Palette tasks:

- `Portfolio: Full Self-Test and Reproduction`
- `Portfolio: Reproduce Committed Evidence`
- `Build Public LendingClub Evidence`
- each project's focused test task

## 3. Run One Focused Codex Iteration

Start Codex CLI from the repository root so it can see the cross-project contracts:

```powershell
codex exec -C . -s workspace-write "Improve one documented risk-analytics limitation. Run the relevant baseline tests first, add focused tests, reproduce affected reports, run the full portfolio gate, and review privacy before stopping. Do not commit or push."
```

High-signal prompts are specific about the risk question and evidence contract:

```text
Evaluate a fixed 12-month outcome label or survival-analysis extension. Preserve unresolved
loans without leakage, publish aggregates only, and test maturity-window edge cases.
```

```text
Add a pre-OOT credit decision strategy backtest. Compare fixed incumbent and challenger
policies on untouched holdout data, include bootstrap uncertainty, and avoid OOT optimisation.
```

```text
Add an ECL macro sensitivity example with explicit scenario assumptions and governed
management overlays. Test accounting identities, regenerate deterministic evidence, and
document limitations.
```

Avoid prompts such as `make the project better`; they do not define a risk decision,
acceptance criteria, or evidence boundary.

## 4. Self-Test Before Every Commit

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\run_portfolio.py --with-tests --verify-committed
.\.venv\Scripts\python.exe -m compileall -q `
  projects\credit-risk-pd-model\src `
  projects\ifrs9-ecl-engine\src `
  projects\model-validation-framework\src `
  scripts
git diff --check
git status --short
```

The root runner checks all Ruff and pytest suites, regenerates all deterministic synthetic,
ECL-integration, macro/overlay governance, model-replication, validation, and remediation
reports, then compares them with the committed evidence. GitHub Actions repeats this gate on
Linux and runs the database integration test against PostgreSQL 16.

Review the diff for unrelated files, machine-local paths, credentials, and borrower-level
records before staging.

## 5. Rebuild the Public Evidence

The complete public workflow is one command:

```powershell
.\scripts\run_public_lendingclub.ps1
```

It downloads or reuses the ignored LendingClub accepted-loans file, performs chunked
ingestion, runs the PD model and independent validation, publishes allow-listed aggregate
reports, and rebuilds the showcase charts. Expect model fitting to take several minutes.

Never stage files under `data/raw/` or `data/processed/`. The publishers reject CSV files
with `customer_id`, and borrower-level OOT predictions stay local.

## 6. Pull Request Workflow

Use one branch per coherent evidence improvement:

```powershell
git switch -c add-vintage-backtesting
git add <reviewed-files>
git commit -m "Add vintage backtesting evidence"
git push -u origin add-vintage-backtesting
gh pr create --base main --head add-vintage-backtesting
```

Wait for the Python matrix, portfolio reproduction, and PostgreSQL integration checks. Fix
failures on the branch and push again; do not merge a red PR.

## 7. Next High-Impact Iterations

1. Add documented SICR rebuttal decisions and contractual cash-flow sensitivity.
2. Evaluate survival methods or a fixed-horizon label for unresolved public outcomes.
3. Add reject-inference sensitivity for the accepted-only population.
4. Add a fresh OOT closure window when a defensible later-period dataset is available.

Each iteration should improve a hiring manager's ability to inspect a concrete risk decision,
not merely increase code volume.
