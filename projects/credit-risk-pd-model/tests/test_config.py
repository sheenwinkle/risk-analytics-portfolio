import numpy as np
import pytest

from credit_risk_pd.config import ModelConfig


def test_model_config_normalises_approval_thresholds():
    config = ModelConfig(
        calibration_fraction="0.25",
        approval_thresholds=["0.10", "0.20"],
        lgd="0.45",
        test_threshold="0.15",
    )

    assert config.approval_thresholds == (0.10, 0.20)
    assert config.calibration_fraction == 0.25
    assert config.lgd == 0.45
    assert config.test_threshold == 0.15


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"calibration_fraction": np.nan}, "calibration_fraction"),
        ({"approval_thresholds": ()}, "approval_thresholds"),
        ({"approval_thresholds": (0.10, 0.10)}, "duplicate"),
        ({"lgd": 1.1}, "lgd"),
        ({"test_threshold": 0.0}, "test_threshold"),
    ],
)
def test_model_config_rejects_invalid_risk_parameters(overrides, match):
    with pytest.raises(ValueError, match=match):
        ModelConfig(**overrides)
