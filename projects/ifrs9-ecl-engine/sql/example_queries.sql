-- Portfolio ECL and coverage ratio by stage.
SELECT
    stage,
    COUNT(*) AS account_count,
    SUM(gross_exposure) AS gross_exposure,
    SUM(weighted_ecl) AS weighted_ecl,
    CASE
        WHEN SUM(gross_exposure) = 0 THEN 0
        ELSE SUM(weighted_ecl) / SUM(gross_exposure)
    END AS coverage_ratio
FROM ecl_account_result
GROUP BY stage
ORDER BY stage;

-- Stage migration from prior reporting stage to current reporting stage.
SELECT
    prior_stage,
    stage AS current_stage,
    COUNT(*) AS account_count,
    SUM(gross_exposure) AS gross_exposure,
    SUM(weighted_ecl) AS weighted_ecl
FROM ecl_account_result
GROUP BY prior_stage, stage
ORDER BY prior_stage, current_stage;

-- Scenario contribution to weighted ECL.
SELECT
    scenario,
    MAX(scenario_weight) AS scenario_weight,
    SUM(scenario_ecl) AS scenario_ecl,
    SUM(weighted_scenario_ecl) AS weighted_scenario_ecl
FROM ecl_scenario_result
GROUP BY scenario
ORDER BY scenario;

-- Accounts with the highest coverage ratios.
SELECT
    account_id,
    stage,
    stage_reason,
    gross_exposure,
    weighted_ecl,
    coverage_ratio
FROM ecl_account_result
ORDER BY coverage_ratio DESC, weighted_ecl DESC
LIMIT 20;

-- Macro sensitivity ranking; changes are analysis only and are not booked adjustments.
SELECT
    case_id,
    is_baseline,
    modelled_ecl,
    change_vs_baseline,
    change_pct_vs_baseline,
    coverage_ratio
FROM ecl_macro_sensitivity_case
ORDER BY modelled_ecl DESC, case_id;

-- Overlay control register, including blocked and pending requests.
SELECT
    overlay_id,
    risk_driver,
    scope,
    trigger_met,
    double_counting_check,
    approval_status,
    recognition_status,
    requested_amount,
    recognized_amount
FROM ecl_management_overlay
ORDER BY overlay_id;

-- Model-to-reported ECL bridge with the highest non-booked sensitivity disclosed separately.
SELECT
    reporting_id,
    baseline_modelled_ecl,
    highest_sensitivity_case_id,
    highest_sensitivity_delta_not_booked,
    recognized_management_overlay,
    illustrative_reported_ecl,
    illustrative_reported_coverage_ratio
FROM ecl_reporting_reconciliation;

-- SICR rebuttal decision register, including requests that did not change stage.
SELECT
    rebuttal_id,
    account_id,
    reporting_date,
    current_days_past_due,
    approval_status,
    decision_outcome,
    stage_without_rebuttal,
    stage_with_rebuttal
FROM ecl_sicr_rebuttal_decision
ORDER BY reporting_date, rebuttal_id;

-- Portfolio impact of effective, pending, and blocked SICR rebuttal decisions.
SELECT
    reporting_date,
    baseline_modelled_ecl,
    governed_modelled_ecl,
    ecl_reduction,
    ecl_reduction_pct,
    effective_rebuttal_count,
    pending_rebuttal_count,
    blocked_rebuttal_count
FROM ecl_sicr_rebuttal_reconciliation
ORDER BY reporting_date;

-- Contractual cash-flow sensitivity ranking and quantified change from baseline.
SELECT
    case_id,
    description,
    is_baseline,
    modelled_ecl,
    ecl_change,
    ecl_change_pct,
    coverage_ratio
FROM ecl_cashflow_sensitivity_case
ORDER BY modelled_ecl DESC, case_id;

-- Accounts driving the combined-downside ECL increase.
SELECT
    account_id,
    stage,
    gross_exposure,
    baseline_ecl,
    weighted_ecl AS stressed_ecl,
    ecl_change,
    ecl_change_pct
FROM ecl_cashflow_account_result
WHERE case_id = 'combined_downside'
ORDER BY ecl_change DESC, account_id;

-- Base-scenario EAD and effective LGD trajectory for baseline versus combined downside.
SELECT
    case_id,
    month,
    portfolio_ead,
    ead_weighted_lgd,
    expected_prepayment,
    discounted_expected_recovery_at_default
FROM ecl_cashflow_monthly_projection
WHERE scenario = 'base'
  AND case_id IN ('baseline', 'combined_downside')
ORDER BY month, case_id;

-- Data-quality exception query; a governed run should return no rows.
SELECT
    case_id,
    modelled_ecl,
    account_ecl_sum,
    reconciliation_difference
FROM ecl_cashflow_reconciliation
WHERE reconciled = FALSE
   OR ABS(reconciliation_difference) >= 0.000001
ORDER BY case_id;

-- Frozen OOT macro-satellite error versus the previous-quarter persistence benchmark.
SELECT
    COUNT(*) AS oot_quarters,
    AVG(ABS(actual_npl_ratio - model_prediction)) AS model_mae,
    AVG(ABS(actual_npl_ratio - persistence_prediction)) AS persistence_mae,
    1 - (
        AVG(ABS(actual_npl_ratio - model_prediction))
        / NULLIF(AVG(ABS(actual_npl_ratio - persistence_prediction)), 0)
    ) AS mae_improvement_vs_persistence
FROM ecl_macro_satellite_backtest
WHERE split = 'oot';

-- Trace the sensitivity-only macro scenario ordering and calibration anchor.
SELECT
    scenario,
    anchor_quarter,
    unemployment_shock_pp,
    real_gdp_growth_shock_pp,
    predicted_npl_ratio,
    npl_multiplier,
    evidence_use
FROM ecl_macro_scenario_multiplier
WHERE evidence_use = 'sensitivity_only'
ORDER BY npl_multiplier;

-- Quantify the empirical challenger impact while holding the ECL portfolio fixed.
SELECT
    variant,
    modelled_ecl,
    coverage_ratio,
    change_vs_incumbent,
    change_pct_vs_incumbent
FROM ecl_macro_challenger_comparison
WHERE stage = 'Total'
ORDER BY variant;
