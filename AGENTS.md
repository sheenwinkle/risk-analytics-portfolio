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

Run these from `projects/credit-risk-pd-model`:

```powershell
pytest
python scripts/run_pipeline.py
```

## Roadmap Order

1. Improve Project 1 until it is strong enough to show recruiters.
2. Add real public dataset ingestion.
3. Add scorecard/WOE or explainability.
4. Build Project 2: IFRS 9 ECL Engine.
5. Build Project 3: Model Validation Framework.

## Resume Audience

Assume the reader is a hiring manager or recruiter for roles such as:

- Credit Risk Analyst
- Risk Analytics Analyst
- Model Validation Analyst
- Lending Data Analyst
- FinTech Decision Science Analyst

Every public-facing document should make the risk analytics relevance explicit.

