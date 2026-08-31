import pandas as pd

from credit_risk_pd.pipeline import run_pd_modelling_workflow


def test_pipeline_creates_outputs(tmp_path):
    outputs = run_pd_modelling_workflow(
        output_dir=tmp_path / "reports",
        model_dir=tmp_path / "models",
    )

    assert "feature_importance" in outputs
    assert "woe_bins" in outputs
    assert "woe_summary" in outputs
    for path in outputs.values():
        assert path.exists()

    woe_bins = pd.read_csv(outputs["woe_bins"])
    woe_summary = pd.read_csv(outputs["woe_summary"])
    assert {"feature", "bin", "goods", "bads", "woe", "iv"}.issubset(woe_bins.columns)
    assert {"rank", "feature", "information_value", "iv_band"}.issubset(woe_summary.columns)
    assert woe_summary["information_value"].is_monotonic_decreasing

