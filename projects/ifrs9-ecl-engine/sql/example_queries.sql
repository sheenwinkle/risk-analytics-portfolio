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
