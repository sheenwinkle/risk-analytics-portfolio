# Agent Instructions

This repository is a public GitHub portfolio for Australian banking and fintech risk analytics roles.

## Positioning

Keep the project focused on:

- Credit risk analytics
- Probability of default modelling
- IFRS 9 expected credit loss
- Model validation
- SQL-backed portfolio risk reporting
- Recruiter-readable documentation

Do not turn the repository into a generic machine learning demo.

## Development Rules

- Prefer small, reviewable changes.
- Keep production-style logic in `src/`, not notebooks.
- Keep notebooks exploratory and documented.
- Add or update tests for code changes.
- Keep raw datasets out of Git.
- Commit small sample reports only when they help GitHub readers understand the project.
- Maintain Windows-friendly setup commands in documentation.

## Validation Commands

Run each project's checks from its own directory:

```powershell
# Project 1
pytest
python scripts/run_pipeline.py

# Project 2
pytest
python scripts/run_pipeline.py
python scripts/run_pd_integration.py

# Project 3
pytest
python scripts/run_validation.py
```

## Mandatory Self-Test Gate

Every implementation iteration must complete this loop before it is committed or pushed:

1. Run the existing test suite before editing to establish a clean baseline.
2. Add or update focused tests for every behavioural code change.
3. Run the focused tests while iterating.
4. Run the complete test suite after implementation.
5. Run every pipeline affected by the change and inspect the generated artefacts.
6. Run `git diff --check` and review the final diff for unrelated changes.

On Windows, prefer the project interpreter explicitly:

```powershell
$pytestTemp = ".pytest-tmp-$([guid]::NewGuid().ToString('N'))"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp=$pytestTemp
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

Projects 2 and 3 can use their own virtual environments or the Project 1 interpreter when
all requirements are installed:

```powershell
# From projects/ifrs9-ecl-engine
..\credit-risk-pd-model\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp=$pytestTemp
..\credit-risk-pd-model\.venv\Scripts\python.exe scripts\run_pipeline.py
..\credit-risk-pd-model\.venv\Scripts\python.exe scripts\run_pd_integration.py

# From projects/model-validation-framework
..\credit-risk-pd-model\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp=$pytestTemp
..\credit-risk-pd-model\.venv\Scripts\python.exe scripts\run_validation.py
```

Do not commit or push when any required check fails. Fix the failure, rerun the full gate, and report the final test and pipeline results.

## Roadmap Order

1. Improve Project 1 until it is strong enough to show recruiters.
2. Validate the LendingClub adapter on locally downloaded public data.
3. Add PD recalibration and lending threshold strategy analysis.
4. Build Project 2: IFRS 9 ECL Engine.
5. Build Project 3: Model Validation Framework.
6. Extend validation with segment, uncertainty, and feature-level review evidence.

## Resume Audience

Assume the reader is a hiring manager or recruiter for roles such as:

- Credit Risk Analyst
- Risk Analytics Analyst
- Model Validation Analyst
- Lending Data Analyst
- FinTech Decision Science Analyst

Every public-facing document should make the risk analytics relevance explicit.
