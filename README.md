# Risk Analytics Portfolio

This portfolio is designed for Australian credit risk, model risk, and fintech risk analytics roles.

Candidate profile:

- Economics undergraduate background
- Computer Science master's background
- FRM candidate / holder
- Python, SQL, PostgreSQL, machine learning, data structures and algorithms

## Portfolio Projects

| Project | Status | Target roles | Core skills |
| --- | --- | --- | --- |
| [Credit Risk PD Modelling](projects/credit-risk-pd-model) | Implemented | Credit Risk Analyst, Risk Analytics Analyst, Model Validation Analyst | PD modelling, calibration, KS, Gini, PSI, SQL |
| [IFRS 9 ECL Engine](projects/ifrs9-ecl-engine) | Planned | Credit Risk, ECL Analyst, Portfolio Risk | PD/LGD/EAD, staging, lifetime ECL, scenario weighting |
| [Model Validation Framework](projects/model-validation-framework) | Planned | Model Risk, Validation Analyst, Quant Risk | Backtesting, benchmarking, drift monitoring, validation reporting |

## Recommended GitHub Layout

Keep this as one portfolio repository first:

```text
risk-analytics-portfolio/
  projects/
    credit-risk-pd-model/
    ifrs9-ecl-engine/
    model-validation-framework/
  docs/
```

After the first project is polished, you can either keep the monorepo or split each project into its own public GitHub repository.

## VS Code Setup

Open this folder in VS Code:

```powershell
cd risk-analytics-portfolio
code .
```

Then create a virtual environment inside the first project:

```powershell
cd projects/credit-risk-pd-model
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the project:

```powershell
python scripts/run_pipeline.py
```

Run tests:

```powershell
pytest
```

## Resume Positioning

This portfolio should communicate:

> Built production-style credit risk analytics workflows using Python, SQL, machine learning, calibration, and model monitoring methods aligned with banking and fintech risk practice.

