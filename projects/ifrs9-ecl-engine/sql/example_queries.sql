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
