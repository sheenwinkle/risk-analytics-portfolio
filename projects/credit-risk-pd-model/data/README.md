# Data Guide

The project can run with synthetic data, so no external dataset is required for the first commit.

## Expected CSV Schema

If you use a real public dataset, transform it into this schema:

| Column | Type | Description |
| --- | --- | --- |
| `customer_id` | string | Unique borrower identifier |
| `observation_date` | date | Month or date of model observation |
| `age` | integer | Borrower age |
| `annual_income` | numeric | Annual income |
| `debt_to_income` | numeric | Debt-to-income ratio |
| `credit_utilisation` | numeric | Revolving credit utilisation |
| `delinquencies_2y` | integer | Number of delinquencies in prior two years |
| `loan_amount` | numeric | Loan principal |
| `interest_rate` | numeric | Contract interest rate |
| `employment_length` | integer | Years of employment |
| `home_ownership` | string | Rent, mortgage, own, or other |
| `purpose` | string | Loan purpose |
| `default` | integer | Binary target: 1 default, 0 non-default |

## GitHub Rule

Keep raw data out of the repository. Commit only:

- Data dictionaries
- Small sample files if legally allowed
- Transformation scripts
- Aggregate reports

