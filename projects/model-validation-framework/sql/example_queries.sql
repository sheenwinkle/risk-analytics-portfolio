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
    finding.lifecycle_status,
    finding.check_name,
    finding.finding,
    finding.recommended_action
FROM model_validation_finding AS finding
JOIN latest_run USING (validation_run_id)
WHERE finding.lifecycle_status <> 'closed'
ORDER BY
    CASE finding.status WHEN 'fail' THEN 1 ELSE 2 END,
    finding.check_name;

-- Finding lifecycle and remediation evidence for the latest validation run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    finding.finding_id,
    finding.check_name,
    finding.status AS initial_status,
    finding.lifecycle_status,
    event.event_type,
    event.event_status,
    event.metric_value,
    event.evidence_reference,
    event.detail,
    event.created_at
FROM model_validation_finding AS finding
JOIN latest_run USING (validation_run_id)
LEFT JOIN model_validation_finding_event AS event USING (finding_id)
ORDER BY finding.finding_id, event.created_at, event.finding_event_id;

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

-- Confidence intervals for the latest independent validation run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    metric,
    estimate,
    lower_bound,
    upper_bound,
    confidence_level,
    method
FROM model_validation_uncertainty
JOIN latest_run USING (validation_run_id)
ORDER BY metric;

-- Material vintage and segment calibration signals for the latest run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    group_type,
    group_dimension,
    group_value,
    observations,
    portfolio_share,
    mean_pd,
    observed_default_rate,
    calibration_gap,
    calibration_gap_lower,
    calibration_gap_upper,
    reliability_status,
    calibration_signal
FROM model_validation_group_performance
JOIN latest_run USING (validation_run_id)
WHERE calibration_signal IN ('pd_overprediction', 'pd_underprediction')
ORDER BY ABS(calibration_gap) DESC, group_type, group_dimension, group_value;

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

-- Feature drift and missingness for the latest validation run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    feature_name,
    feature_type,
    characteristic_stability_index,
    stability_status,
    reference_missing_rate,
    current_missing_rate,
    missing_rate_delta,
    availability_status
FROM model_validation_characteristic_summary
JOIN latest_run USING (validation_run_id)
ORDER BY characteristic_stability_index DESC, feature_name;

-- Bin-level drivers for materially shifted characteristics in the latest run.
WITH latest_run AS (
    SELECT validation_run_id
    FROM model_validation_run
    ORDER BY created_at DESC, validation_run_id DESC
    LIMIT 1
)
SELECT
    summary.feature_name,
    bin.bin,
    bin.bin_label,
    bin.reference_share,
    bin.current_share,
    bin.csi_component
FROM model_validation_characteristic_summary AS summary
JOIN latest_run USING (validation_run_id)
JOIN model_validation_characteristic_bin AS bin
    USING (validation_run_id, feature_name)
WHERE summary.stability_status IN ('moderate_shift', 'material_shift')
ORDER BY summary.feature_name, bin.csi_component DESC, bin.bin;
