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
    month INTEGER NOT NULL CHECK (month > 0 AND month = CAST(month AS INTEGER)),
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

CREATE TABLE ecl_sicr_rebuttal_decision (
    rebuttal_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES ecl_account_snapshot(account_id),
    reporting_date DATE NOT NULL,
    observed_days_past_due INTEGER NOT NULL CHECK (observed_days_past_due >= 0),
    current_days_past_due INTEGER NOT NULL CHECK (current_days_past_due >= 0),
    stage2_dpd_backstop INTEGER CHECK (stage2_dpd_backstop > 0),
    stage3_dpd_backstop INTEGER CHECK (stage3_dpd_backstop > 0),
    presumption_applicable BOOLEAN NOT NULL,
    evidence_reference TEXT NOT NULL CHECK (LENGTH(TRIM(evidence_reference)) > 0),
    evidence_summary TEXT NOT NULL CHECK (LENGTH(TRIM(evidence_summary)) > 0),
    reasonable_and_supportable BOOLEAN NOT NULL,
    forward_looking_review_completed BOOLEAN NOT NULL,
    other_sicr_indicators_present BOOLEAN NOT NULL,
    decision_date DATE NOT NULL,
    valid_until DATE NOT NULL CHECK (valid_until >= decision_date),
    approval_status TEXT NOT NULL CHECK (
        approval_status IN ('approved', 'pending', 'rejected')
    ),
    approved_by TEXT CHECK (approved_by IS NULL OR LENGTH(TRIM(approved_by)) > 0),
    decision_outcome TEXT NOT NULL CHECK (
        decision_outcome IN (
            'approved_effective',
            'blocked_stage3_precedence',
            'blocked_other_sicr_indicator',
            'blocked_not_applicable',
            'blocked_dpd_mismatch',
            'blocked_insufficient_evidence',
            'blocked_forward_looking_review',
            'not_yet_effective',
            'expired',
            'pending_approval',
            'rejected'
        )
    ),
    stage_without_rebuttal INTEGER NOT NULL CHECK (stage_without_rebuttal IN (1, 2, 3)),
    stage_reason_without_rebuttal TEXT NOT NULL CHECK (
        LENGTH(TRIM(stage_reason_without_rebuttal)) > 0
    ),
    stage_with_rebuttal INTEGER NOT NULL CHECK (stage_with_rebuttal IN (1, 2, 3)),
    stage_reason_with_rebuttal TEXT NOT NULL CHECK (
        LENGTH(TRIM(stage_reason_with_rebuttal)) > 0
    ),
    UNIQUE (account_id, reporting_date),
    CHECK (
        approval_status <> 'approved'
        OR (approved_by IS NOT NULL AND LENGTH(TRIM(approved_by)) > 0)
    ),
    CHECK (
        decision_outcome <> 'approved_effective'
        OR (
            presumption_applicable = TRUE
            AND observed_days_past_due = current_days_past_due
            AND reasonable_and_supportable = TRUE
            AND forward_looking_review_completed = TRUE
            AND other_sicr_indicators_present = FALSE
            AND decision_date <= reporting_date
            AND reporting_date <= valid_until
            AND approval_status = 'approved'
            AND stage_without_rebuttal = 2
            AND stage_with_rebuttal = 1
        )
    )
);

CREATE TABLE ecl_sicr_rebuttal_reconciliation (
    reporting_date DATE PRIMARY KEY,
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    baseline_modelled_ecl NUMERIC NOT NULL CHECK (baseline_modelled_ecl >= 0),
    governed_modelled_ecl NUMERIC NOT NULL CHECK (governed_modelled_ecl >= 0),
    ecl_change NUMERIC NOT NULL,
    ecl_reduction NUMERIC NOT NULL CHECK (ecl_reduction >= 0),
    ecl_reduction_pct NUMERIC NOT NULL CHECK (ecl_reduction_pct >= 0),
    baseline_stage1_accounts INTEGER NOT NULL CHECK (baseline_stage1_accounts >= 0),
    baseline_stage2_accounts INTEGER NOT NULL CHECK (baseline_stage2_accounts >= 0),
    baseline_stage3_accounts INTEGER NOT NULL CHECK (baseline_stage3_accounts >= 0),
    governed_stage1_accounts INTEGER NOT NULL CHECK (governed_stage1_accounts >= 0),
    governed_stage2_accounts INTEGER NOT NULL CHECK (governed_stage2_accounts >= 0),
    governed_stage3_accounts INTEGER NOT NULL CHECK (governed_stage3_accounts >= 0),
    rebuttal_request_count INTEGER NOT NULL CHECK (rebuttal_request_count >= 0),
    effective_rebuttal_count INTEGER NOT NULL CHECK (effective_rebuttal_count >= 0),
    pending_rebuttal_count INTEGER NOT NULL CHECK (pending_rebuttal_count >= 0),
    blocked_rebuttal_count INTEGER NOT NULL CHECK (blocked_rebuttal_count >= 0),
    CHECK (ABS(ecl_change - governed_modelled_ecl + baseline_modelled_ecl) < 0.000001),
    CHECK (ABS(ecl_reduction - baseline_modelled_ecl + governed_modelled_ecl) < 0.000001),
    CHECK (
        (baseline_modelled_ecl = 0 AND ABS(ecl_reduction_pct) < 0.000001)
        OR (
            baseline_modelled_ecl > 0
            AND ABS(ecl_reduction_pct - ecl_reduction / baseline_modelled_ecl) < 0.000001
        )
    ),
    CHECK (
        baseline_stage1_accounts + baseline_stage2_accounts + baseline_stage3_accounts
        = governed_stage1_accounts + governed_stage2_accounts + governed_stage3_accounts
    ),
    CHECK (
        effective_rebuttal_count + pending_rebuttal_count + blocked_rebuttal_count
        <= rebuttal_request_count
    )
);

CREATE TABLE ecl_contractual_cashflow (
    account_id TEXT NOT NULL REFERENCES ecl_account_snapshot(account_id),
    repayment_profile TEXT NOT NULL CHECK (LENGTH(TRIM(repayment_profile)) > 0),
    month INTEGER NOT NULL CHECK (month > 0 AND month = CAST(month AS INTEGER)),
    contractual_principal_due NUMERIC NOT NULL CHECK (contractual_principal_due >= 0),
    PRIMARY KEY (account_id, month)
);

CREATE TABLE ecl_recovery_assumption (
    account_id TEXT NOT NULL REFERENCES ecl_account_snapshot(account_id),
    scenario TEXT NOT NULL REFERENCES ecl_scenario_weight(scenario),
    security_type TEXT NOT NULL CHECK (LENGTH(TRIM(security_type)) > 0),
    assumption_basis TEXT NOT NULL CHECK (LENGTH(TRIM(assumption_basis)) > 0),
    annual_prepayment_rate NUMERIC NOT NULL CHECK (
        annual_prepayment_rate BETWEEN 0 AND 1
    ),
    cure_rate NUMERIC NOT NULL CHECK (cure_rate BETWEEN 0 AND 1),
    cure_delay_months INTEGER NOT NULL CHECK (
        cure_delay_months >= 0
        AND cure_delay_months = CAST(cure_delay_months AS INTEGER)
    ),
    collateral_value NUMERIC NOT NULL CHECK (collateral_value >= 0),
    collateral_haircut NUMERIC NOT NULL CHECK (collateral_haircut BETWEEN 0 AND 1),
    recovery_cost_rate NUMERIC NOT NULL CHECK (recovery_cost_rate BETWEEN 0 AND 1),
    collateral_recovery_delay_months INTEGER NOT NULL CHECK (
        collateral_recovery_delay_months >= 0
        AND collateral_recovery_delay_months = CAST(
            collateral_recovery_delay_months AS INTEGER
        )
    ),
    collateral_is_integral BOOLEAN NOT NULL CHECK (
        collateral_is_integral IN (FALSE, TRUE)
    ),
    collateral_recognized_separately BOOLEAN NOT NULL CHECK (
        collateral_recognized_separately IN (FALSE, TRUE)
    ),
    PRIMARY KEY (account_id, scenario)
);

CREATE TABLE ecl_cashflow_sensitivity_case (
    case_id TEXT PRIMARY KEY,
    description TEXT NOT NULL CHECK (LENGTH(TRIM(description)) > 0),
    is_baseline BOOLEAN NOT NULL CHECK (is_baseline IN (FALSE, TRUE)),
    annual_prepayment_rate_multiplier NUMERIC NOT NULL CHECK (
        annual_prepayment_rate_multiplier >= 0
    ),
    cure_rate_multiplier NUMERIC NOT NULL CHECK (cure_rate_multiplier >= 0),
    collateral_value_multiplier NUMERIC NOT NULL CHECK (
        collateral_value_multiplier >= 0
    ),
    collateral_haircut_addon NUMERIC NOT NULL CHECK (
        collateral_haircut_addon BETWEEN 0 AND 1
    ),
    cure_delay_addon_months INTEGER NOT NULL CHECK (
        cure_delay_addon_months >= 0
        AND cure_delay_addon_months = CAST(cure_delay_addon_months AS INTEGER)
    ),
    collateral_recovery_delay_addon_months INTEGER NOT NULL CHECK (
        collateral_recovery_delay_addon_months >= 0
        AND collateral_recovery_delay_addon_months = CAST(
            collateral_recovery_delay_addon_months AS INTEGER
        )
    ),
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    modelled_ecl NUMERIC NOT NULL CHECK (modelled_ecl >= 0),
    coverage_ratio NUMERIC NOT NULL CHECK (coverage_ratio >= 0),
    ecl_change NUMERIC NOT NULL,
    ecl_change_pct NUMERIC NOT NULL,
    CHECK (
        is_baseline = FALSE
        OR (
            annual_prepayment_rate_multiplier = 1
            AND cure_rate_multiplier = 1
            AND collateral_value_multiplier = 1
            AND collateral_haircut_addon = 0
            AND cure_delay_addon_months = 0
            AND collateral_recovery_delay_addon_months = 0
            AND ABS(ecl_change) < 0.000001
            AND ABS(ecl_change_pct) < 0.000001
        )
    )
);

CREATE UNIQUE INDEX one_ecl_cashflow_baseline
ON ecl_cashflow_sensitivity_case(is_baseline)
WHERE is_baseline = TRUE;

CREATE TABLE ecl_cashflow_account_result (
    case_id TEXT NOT NULL REFERENCES ecl_cashflow_sensitivity_case(case_id),
    account_id TEXT NOT NULL REFERENCES ecl_account_snapshot(account_id),
    stage INTEGER NOT NULL CHECK (stage IN (1, 2, 3)),
    stage_reason TEXT NOT NULL CHECK (LENGTH(TRIM(stage_reason)) > 0),
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    weighted_ecl NUMERIC NOT NULL CHECK (weighted_ecl >= 0),
    baseline_ecl NUMERIC NOT NULL CHECK (baseline_ecl >= 0),
    ecl_change NUMERIC NOT NULL,
    ecl_change_pct NUMERIC NOT NULL,
    PRIMARY KEY (case_id, account_id),
    CHECK (ABS(ecl_change - weighted_ecl + baseline_ecl) < 0.000001),
    CHECK (
        (baseline_ecl = 0 AND ABS(ecl_change_pct) < 0.000001)
        OR (
            baseline_ecl > 0
            AND ABS(ecl_change_pct - ecl_change / baseline_ecl) < 0.000001
        )
    )
);

CREATE TABLE ecl_cashflow_monthly_projection (
    case_id TEXT NOT NULL REFERENCES ecl_cashflow_sensitivity_case(case_id),
    scenario TEXT NOT NULL REFERENCES ecl_scenario_weight(scenario),
    scenario_weight NUMERIC NOT NULL CHECK (scenario_weight BETWEEN 0 AND 1),
    month INTEGER NOT NULL CHECK (month > 0 AND month = CAST(month AS INTEGER)),
    portfolio_ead NUMERIC NOT NULL CHECK (portfolio_ead >= 0),
    ead_weighted_lgd NUMERIC NOT NULL CHECK (ead_weighted_lgd BETWEEN 0 AND 1),
    contractual_principal_due NUMERIC NOT NULL CHECK (contractual_principal_due >= 0),
    scheduled_principal_applied NUMERIC NOT NULL CHECK (
        scheduled_principal_applied >= 0
    ),
    expected_prepayment NUMERIC NOT NULL CHECK (expected_prepayment >= 0),
    closing_balance NUMERIC NOT NULL CHECK (closing_balance >= 0),
    expected_cure_recovery NUMERIC NOT NULL CHECK (expected_cure_recovery >= 0),
    expected_collateral_recovery NUMERIC NOT NULL CHECK (
        expected_collateral_recovery >= 0
    ),
    discounted_expected_recovery_at_default NUMERIC NOT NULL CHECK (
        discounted_expected_recovery_at_default >= 0
    ),
    PRIMARY KEY (case_id, scenario, month)
);

CREATE TABLE ecl_cashflow_reconciliation (
    case_id TEXT PRIMARY KEY REFERENCES ecl_cashflow_sensitivity_case(case_id),
    modelled_ecl NUMERIC NOT NULL CHECK (modelled_ecl >= 0),
    account_ecl_sum NUMERIC NOT NULL CHECK (account_ecl_sum >= 0),
    reconciliation_difference NUMERIC NOT NULL,
    reconciled BOOLEAN NOT NULL CHECK (reconciled IN (FALSE, TRUE)),
    CHECK (
        ABS(reconciliation_difference - modelled_ecl + account_ecl_sum) < 0.000001
    ),
    CHECK (
        (reconciled = TRUE AND ABS(reconciliation_difference) < 0.000001)
        OR (reconciled = FALSE AND ABS(reconciliation_difference) >= 0.000001)
    )
);

CREATE TABLE ecl_macro_satellite_backtest (
    quarter DATE PRIMARY KEY,
    split TEXT NOT NULL CHECK (split IN ('development', 'validation', 'oot')),
    actual_npl_ratio NUMERIC NOT NULL CHECK (actual_npl_ratio BETWEEN 0 AND 1),
    model_prediction NUMERIC NOT NULL CHECK (model_prediction BETWEEN 0 AND 1),
    persistence_prediction NUMERIC NOT NULL CHECK (
        persistence_prediction BETWEEN 0 AND 1
    ),
    model_residual NUMERIC NOT NULL,
    unemployment_rate_pct NUMERIC NOT NULL,
    real_gdp_yoy_pct NUMERIC NOT NULL,
    CHECK (quarter < '2022-03-31'),
    CHECK (ABS(model_residual - actual_npl_ratio + model_prediction) < 0.000001)
);

CREATE TABLE ecl_macro_scenario_multiplier (
    scenario TEXT PRIMARY KEY CHECK (scenario IN ('upside', 'base', 'downside')),
    anchor_quarter DATE NOT NULL,
    unemployment_shock_pp NUMERIC NOT NULL,
    real_gdp_growth_shock_pp NUMERIC NOT NULL,
    predicted_npl_ratio NUMERIC NOT NULL CHECK (predicted_npl_ratio BETWEEN 0 AND 1),
    npl_multiplier NUMERIC NOT NULL CHECK (npl_multiplier > 0),
    evidence_use TEXT NOT NULL CHECK (evidence_use = 'sensitivity_only'),
    CHECK (scenario <> 'base' OR ABS(npl_multiplier - 1) < 0.000001)
);

CREATE TABLE ecl_macro_challenger_comparison (
    variant TEXT NOT NULL CHECK (
        variant IN ('incumbent_manual', 'challenger_empirical')
    ),
    stage TEXT NOT NULL CHECK (stage IN ('1', '2', '3', 'Total')),
    evidence_basis TEXT NOT NULL CHECK (LENGTH(TRIM(evidence_basis)) > 0),
    gross_exposure NUMERIC NOT NULL CHECK (gross_exposure >= 0),
    modelled_ecl NUMERIC NOT NULL CHECK (modelled_ecl >= 0),
    coverage_ratio NUMERIC NOT NULL CHECK (coverage_ratio >= 0),
    change_vs_incumbent NUMERIC NOT NULL,
    change_pct_vs_incumbent NUMERIC NOT NULL,
    PRIMARY KEY (variant, stage),
    CHECK (
        variant <> 'incumbent_manual'
        OR (
            ABS(change_vs_incumbent) < 0.000001
            AND ABS(change_pct_vs_incumbent) < 0.000001
        )
    )
);
