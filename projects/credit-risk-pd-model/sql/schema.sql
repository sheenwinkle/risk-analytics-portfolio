CREATE SCHEMA IF NOT EXISTS credit_risk;

CREATE TABLE IF NOT EXISTS credit_risk.customers (
    customer_id TEXT PRIMARY KEY,
    age INTEGER NOT NULL,
    annual_income NUMERIC(14, 2) NOT NULL,
    employment_length INTEGER,
    home_ownership TEXT
);

CREATE TABLE IF NOT EXISTS credit_risk.loans (
    loan_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES credit_risk.customers(customer_id),
    origination_date DATE NOT NULL,
    loan_amount NUMERIC(14, 2) NOT NULL,
    interest_rate NUMERIC(8, 5) NOT NULL,
    purpose TEXT,
    term_months INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_risk.monthly_performance (
    loan_id TEXT NOT NULL REFERENCES credit_risk.loans(loan_id),
    observation_date DATE NOT NULL,
    outstanding_balance NUMERIC(14, 2) NOT NULL,
    days_past_due INTEGER NOT NULL,
    default_flag INTEGER NOT NULL CHECK (default_flag IN (0, 1)),
    PRIMARY KEY (loan_id, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_monthly_performance_observation_date
ON credit_risk.monthly_performance(observation_date);

CREATE INDEX IF NOT EXISTS idx_monthly_performance_default
ON credit_risk.monthly_performance(default_flag);

