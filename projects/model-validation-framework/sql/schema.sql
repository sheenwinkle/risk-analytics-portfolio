CREATE TABLE model_validation_run (
    validation_run_id BIGSERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    score_version TEXT NOT NULL,
    source_report_path TEXT NOT NULL,
    source_commit_sha TEXT,
    reference_start DATE NOT NULL,
    reference_end DATE NOT NULL,
    current_start DATE NOT NULL,
    current_end DATE NOT NULL,
    reference_observations INTEGER NOT NULL CHECK (reference_observations > 0),
    current_observations INTEGER NOT NULL CHECK (current_observations > 0),
    requested_bins INTEGER NOT NULL CHECK (requested_bins > 0),
    effective_bins INTEGER NOT NULL CHECK (
        effective_bins > 0 AND effective_bins <= requested_bins
    ),
    overall_status TEXT NOT NULL CHECK (overall_status IN ('pass', 'warning', 'fail')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (reference_start <= reference_end),
    CHECK (reference_end < current_start),
    CHECK (current_start <= current_end)
);

CREATE TABLE model_validation_metric (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    check_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    direction TEXT NOT NULL CHECK (
        direction IN ('higher_is_better', 'lower_is_better')
    ),
    green_threshold NUMERIC NOT NULL,
    warning_threshold NUMERIC NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pass', 'warning', 'fail')),
    detail TEXT NOT NULL,
    PRIMARY KEY (validation_run_id, check_name)
);

CREATE TABLE model_validation_finding (
    finding_id BIGSERIAL PRIMARY KEY,
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    check_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('warning', 'fail')),
    finding TEXT NOT NULL,
    recommended_action TEXT NOT NULL
);

CREATE TABLE model_validation_benchmark (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    comparison TEXT NOT NULL,
    baseline_model TEXT NOT NULL,
    baseline_score_version TEXT NOT NULL,
    benchmark_model TEXT NOT NULL,
    benchmark_score_version TEXT NOT NULL,
    baseline_auc NUMERIC NOT NULL,
    benchmark_auc NUMERIC NOT NULL,
    auc_delta NUMERIC NOT NULL,
    baseline_ks NUMERIC NOT NULL,
    benchmark_ks NUMERIC NOT NULL,
    ks_delta NUMERIC NOT NULL,
    baseline_absolute_calibration_gap NUMERIC NOT NULL,
    benchmark_absolute_calibration_gap NUMERIC NOT NULL,
    absolute_calibration_gap_delta NUMERIC NOT NULL,
    baseline_brier_score NUMERIC NOT NULL,
    benchmark_brier_score NUMERIC NOT NULL,
    brier_score_delta NUMERIC NOT NULL,
    PRIMARY KEY (validation_run_id, comparison)
);

CREATE TABLE model_validation_limitation (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    limitation TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    description TEXT NOT NULL,
    mitigation TEXT NOT NULL,
    PRIMARY KEY (validation_run_id, limitation)
);

CREATE INDEX idx_model_validation_run_model_created
    ON model_validation_run (model_name, created_at DESC);

CREATE INDEX idx_model_validation_finding_status
    ON model_validation_finding (status, validation_run_id);
