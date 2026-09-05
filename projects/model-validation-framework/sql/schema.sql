CREATE TABLE IF NOT EXISTS model_validation_run (
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

CREATE TABLE IF NOT EXISTS model_validation_metric (
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

CREATE TABLE IF NOT EXISTS model_validation_finding (
    finding_id BIGSERIAL PRIMARY KEY,
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    check_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('warning', 'fail')),
    lifecycle_status TEXT NOT NULL DEFAULT 'open' CHECK (
        lifecycle_status IN ('open', 'pending_fresh_oot', 'closed')
    ),
    finding TEXT NOT NULL,
    recommended_action TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_validation_uncertainty (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    metric TEXT NOT NULL,
    estimate NUMERIC NOT NULL,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    confidence_level NUMERIC NOT NULL CHECK (
        confidence_level > 0 AND confidence_level < 1
    ),
    method TEXT NOT NULL CHECK (
        method IN ('delong', 'wilson_score', 'normal_mean', 'paired_normal')
    ),
    observations INTEGER NOT NULL CHECK (observations > 0),
    defaults INTEGER NOT NULL CHECK (defaults >= 0 AND defaults <= observations),
    PRIMARY KEY (validation_run_id, metric),
    CHECK (lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound)
);

CREATE TABLE IF NOT EXISTS model_validation_group_performance (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    group_type TEXT NOT NULL CHECK (group_type IN ('vintage', 'segment')),
    group_dimension TEXT NOT NULL,
    group_value TEXT NOT NULL,
    observations INTEGER NOT NULL CHECK (observations > 0),
    portfolio_share NUMERIC NOT NULL CHECK (
        portfolio_share > 0 AND portfolio_share <= 1
    ),
    defaults INTEGER NOT NULL CHECK (defaults >= 0 AND defaults <= observations),
    non_defaults INTEGER NOT NULL CHECK (
        non_defaults >= 0 AND defaults + non_defaults = observations
    ),
    expected_defaults NUMERIC NOT NULL CHECK (expected_defaults >= 0),
    mean_pd NUMERIC NOT NULL CHECK (mean_pd >= 0 AND mean_pd <= 1),
    observed_default_rate NUMERIC NOT NULL CHECK (
        observed_default_rate >= 0 AND observed_default_rate <= 1
    ),
    observed_default_rate_lower NUMERIC NOT NULL,
    observed_default_rate_upper NUMERIC NOT NULL,
    calibration_gap NUMERIC NOT NULL,
    calibration_gap_lower NUMERIC,
    calibration_gap_upper NUMERIC,
    expected_to_observed_ratio NUMERIC,
    roc_auc NUMERIC,
    roc_auc_lower NUMERIC,
    roc_auc_upper NUMERIC,
    ks NUMERIC,
    discrimination_status TEXT NOT NULL CHECK (
        discrimination_status IN ('available', 'not_available_single_class')
    ),
    reliability_status TEXT NOT NULL CHECK (
        reliability_status IN ('sufficient', 'limited_sample')
    ),
    calibration_signal TEXT NOT NULL CHECK (
        calibration_signal IN (
            'pd_overprediction', 'pd_underprediction',
            'not_statistically_distinct', 'not_available'
        )
    ),
    PRIMARY KEY (validation_run_id, group_type, group_dimension, group_value),
    CHECK (observed_default_rate_lower <= observed_default_rate_upper),
    CHECK (
        calibration_gap_lower IS NULL OR calibration_gap_upper IS NULL
        OR calibration_gap_lower <= calibration_gap_upper
    ),
    CHECK (roc_auc IS NULL OR (roc_auc >= 0 AND roc_auc <= 1)),
    CHECK (ks IS NULL OR (ks >= 0 AND ks <= 1))
);

CREATE TABLE IF NOT EXISTS model_validation_characteristic_summary (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    feature_name TEXT NOT NULL,
    feature_type TEXT NOT NULL CHECK (feature_type IN ('numeric', 'categorical')),
    reference_start DATE NOT NULL,
    reference_end DATE NOT NULL,
    current_start DATE NOT NULL,
    current_end DATE NOT NULL,
    reference_observations INTEGER NOT NULL CHECK (reference_observations > 0),
    current_observations INTEGER NOT NULL CHECK (current_observations > 0),
    reference_missing_rate NUMERIC NOT NULL CHECK (
        reference_missing_rate >= 0 AND reference_missing_rate <= 1
    ),
    current_missing_rate NUMERIC NOT NULL CHECK (
        current_missing_rate >= 0 AND current_missing_rate <= 1
    ),
    missing_rate_delta NUMERIC NOT NULL CHECK (
        missing_rate_delta >= -1 AND missing_rate_delta <= 1
    ),
    requested_bins INTEGER CHECK (requested_bins > 0),
    effective_bins INTEGER NOT NULL CHECK (effective_bins > 0),
    binning_method TEXT NOT NULL CHECK (
        binning_method IN (
            'reference_quantile_midpoint', 'reference_missing_indicator',
            'all_missing', 'category_union'
        )
    ),
    availability_status TEXT NOT NULL CHECK (
        availability_status IN ('available', 'reference_all_missing', 'all_missing')
    ),
    characteristic_stability_index NUMERIC NOT NULL CHECK (
        characteristic_stability_index >= 0
    ),
    stability_status TEXT NOT NULL CHECK (
        stability_status IN (
            'stable', 'moderate_shift', 'material_shift', 'not_available'
        )
    ),
    PRIMARY KEY (validation_run_id, feature_name),
    CHECK (reference_start <= reference_end),
    CHECK (reference_end < current_start),
    CHECK (current_start <= current_end)
);

CREATE TABLE IF NOT EXISTS model_validation_characteristic_bin (
    validation_run_id BIGINT NOT NULL,
    feature_name TEXT NOT NULL,
    feature_type TEXT NOT NULL CHECK (feature_type IN ('numeric', 'categorical')),
    bin TEXT NOT NULL,
    bin_label TEXT NOT NULL,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    category_value TEXT,
    reference_observations INTEGER NOT NULL CHECK (reference_observations >= 0),
    current_observations INTEGER NOT NULL CHECK (current_observations >= 0),
    reference_share NUMERIC NOT NULL CHECK (reference_share >= 0 AND reference_share <= 1),
    current_share NUMERIC NOT NULL CHECK (current_share >= 0 AND current_share <= 1),
    csi_component NUMERIC NOT NULL CHECK (csi_component >= 0),
    PRIMARY KEY (validation_run_id, feature_name, bin),
    FOREIGN KEY (validation_run_id, feature_name)
        REFERENCES model_validation_characteristic_summary(validation_run_id, feature_name),
    CHECK (lower_bound IS NULL OR upper_bound IS NULL OR lower_bound < upper_bound)
);

ALTER TABLE model_validation_finding
    ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'open';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'model_validation_finding_lifecycle_status_check'
          AND conrelid = 'model_validation_finding'::regclass
    ) THEN
        ALTER TABLE model_validation_finding
            ADD CONSTRAINT model_validation_finding_lifecycle_status_check
            CHECK (lifecycle_status IN ('open', 'pending_fresh_oot', 'closed'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS model_validation_finding_event (
    finding_event_id BIGSERIAL PRIMARY KEY,
    finding_id BIGINT NOT NULL REFERENCES model_validation_finding(finding_id),
    event_type TEXT NOT NULL CHECK (
        event_type IN ('identified', 'remediation_retest', 'closure_decision')
    ),
    event_status TEXT NOT NULL,
    metric_value NUMERIC,
    evidence_reference TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE model_validation_finding_event
    DROP CONSTRAINT IF EXISTS model_validation_finding_event_event_status_check;

ALTER TABLE model_validation_finding_event
    ADD CONSTRAINT model_validation_finding_event_event_status_check CHECK (
        event_status IN (
            'pass', 'warning', 'fail', 'open', 'pending_fresh_oot', 'closed'
        )
    );

CREATE TABLE IF NOT EXISTS model_validation_benchmark (
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

CREATE TABLE IF NOT EXISTS model_validation_limitation (
    validation_run_id BIGINT NOT NULL REFERENCES model_validation_run(validation_run_id),
    limitation TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    description TEXT NOT NULL,
    mitigation TEXT NOT NULL,
    PRIMARY KEY (validation_run_id, limitation)
);

CREATE INDEX IF NOT EXISTS idx_model_validation_run_model_created
    ON model_validation_run (model_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_model_validation_finding_status
    ON model_validation_finding (status, validation_run_id);

CREATE INDEX IF NOT EXISTS idx_model_validation_finding_event_finding
    ON model_validation_finding_event (finding_id, created_at);

CREATE INDEX IF NOT EXISTS idx_model_validation_group_lookup
    ON model_validation_group_performance (
        group_type, group_dimension, group_value, validation_run_id
    );

CREATE INDEX IF NOT EXISTS idx_model_validation_characteristic_status
    ON model_validation_characteristic_summary (
        stability_status, characteristic_stability_index DESC, validation_run_id
    );
