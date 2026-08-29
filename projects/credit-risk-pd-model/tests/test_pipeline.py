from credit_risk_pd.pipeline import run_pd_modelling_workflow


def test_pipeline_creates_outputs(tmp_path):
    outputs = run_pd_modelling_workflow(
        output_dir=tmp_path / "reports",
        model_dir=tmp_path / "models",
    )

    for path in outputs.values():
        assert path.exists()

