-- Latest validation opinion for each model.
WITH ranked_runs AS (
    SELECT
        validation_run_id,
        model_name,
        score_version,
        overall_status,
        current_end,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY model_name
            ORDER BY created_at DESC, validation_run_id DESC
        ) AS recency_rank
    FROM model_validation_run
)
SELECT
    validation_run_id,
    model_name,
    score_version,
    overall_status,
    current_end,
    created_at
FROM ranked_runs
WHERE recency_rank = 1
ORDER BY model_name;

-- Open warning/fail findings from the latest validation run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    finding.status,
    finding.check_name,
    finding.finding,
    finding.recommended_action
FROM model_validation_finding AS finding
JOIN latest_run USING (validation_run_id)
ORDER BY
    CASE finding.status WHEN 'fail' THEN 1 ELSE 2 END,
    finding.check_name;

-- Metric trend and change from the preceding validation run.
SELECT
    run.model_name,
    metric.check_name,
    run.current_end,
    metric.metric_value,
    metric.status,
    metric.metric_value - LAG(metric.metric_value) OVER (
        PARTITION BY run.model_name, metric.check_name
        ORDER BY run.current_end, run.validation_run_id
    ) AS change_from_prior_run
FROM model_validation_run AS run
JOIN model_validation_metric AS metric USING (validation_run_id)
ORDER BY run.model_name, metric.check_name, run.current_end;

-- Challenger deltas for the latest run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    comparison,
    baseline_model,
    benchmark_model,
    auc_delta,
    ks_delta,
    absolute_calibration_gap_delta,
    brier_score_delta
FROM model_validation_benchmark
JOIN latest_run USING (validation_run_id)
ORDER BY comparison;

-- Validation status history for governance reporting.
SELECT
    model_name,
    DATE_TRUNC('quarter', current_end)::DATE AS validation_quarter,
    COUNT(*) AS run_count,
    COUNT(*) FILTER (WHERE overall_status = 'pass') AS pass_count,
    COUNT(*) FILTER (WHERE overall_status = 'warning') AS warning_count,
    COUNT(*) FILTER (WHERE overall_status = 'fail') AS fail_count
FROM model_validation_run
GROUP BY model_name, validation_quarter
ORDER BY model_name, validation_quarter;
