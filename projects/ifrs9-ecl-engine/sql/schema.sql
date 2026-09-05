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

CREATE TABLE ecl_macro_sensitivity_case (
    case_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    is_baseline BOOLEAN NOT NULL,
    modelled_ecl NUMERIC NOT NULL CHECK (modelled_ecl >= 0),
    change_vs_baseline NUMERIC NOT NULL,
    change_pct_vs_baseline NUMERIC NOT NULL,
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    coverage_ratio NUMERIC NOT NULL CHECK (coverage_ratio >= 0)
);

CREATE UNIQUE INDEX one_ecl_macro_baseline
ON ecl_macro_sensitivity_case(is_baseline)
WHERE is_baseline = TRUE;

CREATE TABLE ecl_management_overlay (
    overlay_id TEXT PRIMARY KEY,
    risk_driver TEXT NOT NULL,
    scope TEXT NOT NULL,
    trigger_metric TEXT NOT NULL,
    trigger_operator TEXT NOT NULL CHECK (
        trigger_operator IN ('greater_than_or_equal', 'less_than_or_equal')
    ),
    observed_value NUMERIC NOT NULL,
    trigger_threshold NUMERIC NOT NULL,
    trigger_met BOOLEAN NOT NULL,
    requested_amount NUMERIC NOT NULL CHECK (requested_amount >= 0),
    cap_ratio_of_modelled_ecl NUMERIC NOT NULL CHECK (
        cap_ratio_of_modelled_ecl BETWEEN 0 AND 1
    ),
    cap_amount NUMERIC NOT NULL CHECK (cap_amount >= 0),
    cap_binding BOOLEAN NOT NULL,
    overlap_assessment TEXT NOT NULL CHECK (
        overlap_assessment IN ('distinct', 'captured_by_model')
    ),
    modelled_risk_reference TEXT NOT NULL,
    double_counting_check TEXT NOT NULL CHECK (
        double_counting_check IN ('pass', 'fail')
    ),
    approval_status TEXT NOT NULL CHECK (
        approval_status IN ('approved', 'pending', 'rejected')
    ),
    approved_by TEXT,
    rationale TEXT NOT NULL,
    recognition_status TEXT NOT NULL CHECK (
        recognition_status IN (
            'recognized',
            'recognized_capped',
            'blocked_trigger_not_met',
            'blocked_model_overlap',
            'pending_approval',
            'rejected'
        )
    ),
    recognized_amount NUMERIC NOT NULL CHECK (recognized_amount >= 0),
    UNIQUE (risk_driver, scope),
    CHECK (
        approval_status <> 'approved'
        OR (approved_by IS NOT NULL AND LENGTH(TRIM(approved_by)) > 0)
    ),
    CHECK (
        (overlap_assessment = 'distinct' AND double_counting_check = 'pass')
        OR (overlap_assessment = 'captured_by_model' AND double_counting_check = 'fail')
    ),
    CHECK (recognized_amount <= cap_amount),
    CHECK (
        (
            recognition_status IN ('recognized', 'recognized_capped')
            AND trigger_met = TRUE
            AND overlap_assessment = 'distinct'
            AND double_counting_check = 'pass'
            AND approval_status = 'approved'
        )
        OR (
            recognition_status NOT IN ('recognized', 'recognized_capped')
            AND recognized_amount = 0
        )
    ),
    CHECK (recognition_status <> 'recognized_capped' OR cap_binding = TRUE),
    CHECK (recognition_status <> 'recognized' OR cap_binding = FALSE)
);

CREATE TABLE ecl_reporting_reconciliation (
    reporting_id TEXT PRIMARY KEY,
    baseline_modelled_ecl NUMERIC NOT NULL CHECK (baseline_modelled_ecl >= 0),
    highest_sensitivity_case_id TEXT NOT NULL REFERENCES ecl_macro_sensitivity_case(case_id),
    highest_sensitivity_ecl NUMERIC NOT NULL CHECK (highest_sensitivity_ecl >= 0),
    highest_sensitivity_delta_not_booked NUMERIC NOT NULL,
    recognized_management_overlay NUMERIC NOT NULL CHECK (
        recognized_management_overlay >= 0
    ),
    illustrative_reported_ecl NUMERIC NOT NULL CHECK (illustrative_reported_ecl >= 0),
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    modelled_coverage_ratio NUMERIC NOT NULL CHECK (modelled_coverage_ratio >= 0),
    illustrative_reported_coverage_ratio NUMERIC NOT NULL CHECK (
        illustrative_reported_coverage_ratio >= 0
    ),
    overlay_share_of_modelled_ecl NUMERIC NOT NULL CHECK (
        overlay_share_of_modelled_ecl >= 0
    ),
    CHECK (
        ABS(
            illustrative_reported_ecl
            - baseline_modelled_ecl
            - recognized_management_overlay
        ) < 0.000001
    )
);
