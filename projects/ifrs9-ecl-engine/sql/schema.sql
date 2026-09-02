CREATE TABLE ecl_account_snapshot (
    account_id TEXT PRIMARY KEY,
    reporting_date DATE NOT NULL,
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    sicr BOOLEAN NOT NULL,
    credit_impaired BOOLEAN NOT NULL,
    defaulted BOOLEAN NOT NULL DEFAULT FALSE,
    prior_stage INTEGER NOT NULL CHECK (prior_stage IN (1, 2, 3)),
    effective_interest_rate NUMERIC NOT NULL CHECK (effective_interest_rate > -1),
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0)
);

CREATE TABLE ecl_term_structure (
    account_id TEXT NOT NULL REFERENCES ecl_account_snapshot(account_id),
    scenario TEXT NOT NULL,
    month INTEGER NOT NULL CHECK (month > 0),
    marginal_pd NUMERIC NOT NULL CHECK (marginal_pd BETWEEN 0 AND 1),
    lgd NUMERIC NOT NULL CHECK (lgd BETWEEN 0 AND 1),
    ead NUMERIC NOT NULL CHECK (ead >= 0),
    PRIMARY KEY (account_id, scenario, month)
);

CREATE TABLE ecl_scenario_weight (
    scenario TEXT PRIMARY KEY,
    scenario_weight NUMERIC NOT NULL CHECK (scenario_weight >= 0)
);

CREATE TABLE ecl_account_result (
    account_id TEXT PRIMARY KEY,
    days_past_due INTEGER NOT NULL,
    sicr BOOLEAN NOT NULL,
    credit_impaired BOOLEAN NOT NULL,
    defaulted BOOLEAN NOT NULL,
    effective_interest_rate NUMERIC NOT NULL,
    stage INTEGER NOT NULL CHECK (stage IN (1, 2, 3)),
    stage_reason TEXT NOT NULL,
    prior_stage INTEGER NOT NULL CHECK (prior_stage IN (1, 2, 3)),
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    weighted_ecl NUMERIC NOT NULL CHECK (weighted_ecl >= 0),
    coverage_ratio NUMERIC NOT NULL CHECK (coverage_ratio >= 0)
);

CREATE TABLE ecl_scenario_result (
    account_id TEXT NOT NULL REFERENCES ecl_account_result(account_id),
    scenario TEXT NOT NULL,
    stage INTEGER NOT NULL CHECK (stage IN (1, 2, 3)),
    stage_reason TEXT NOT NULL,
    ecl_horizon TEXT NOT NULL,
    months_included INTEGER NOT NULL CHECK (months_included > 0),
    first_month INTEGER NOT NULL CHECK (first_month > 0),
    last_month INTEGER NOT NULL CHECK (last_month >= first_month),
    effective_interest_rate NUMERIC NOT NULL,
    scenario_weight NUMERIC NOT NULL CHECK (scenario_weight >= 0),
    scenario_ecl NUMERIC NOT NULL CHECK (scenario_ecl >= 0),
    weighted_scenario_ecl NUMERIC NOT NULL CHECK (weighted_scenario_ecl >= 0),
    PRIMARY KEY (account_id, scenario)
);
