# GitHub Setup

## Create Local Git History

From the `risk-analytics-portfolio` folder:

```powershell
git init
git add .
git commit -m "Initial risk analytics portfolio"
```

## Create a GitHub Repository

Recommended repository name:

```text
risk-analytics-portfolio
```

Recommended description:

```text
Credit risk, IFRS 9 ECL, and model validation projects for risk analytics roles.
```

Suggested topics:

```text
credit-risk, risk-analytics, probability-of-default, model-validation, ifrs9, python, sql, machine-learning
```

## Push to GitHub

If using GitHub CLI:

```powershell
gh repo create risk-analytics-portfolio --public --source=. --remote=origin --push
```

If creating the repository through the GitHub website:

```powershell
git remote add origin https://github.com/<your-username>/risk-analytics-portfolio.git
git branch -M main
git push -u origin main
```

