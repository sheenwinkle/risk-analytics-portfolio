import numpy as np
import pytest

from credit_risk_pd.config import ModelConfig


def test_model_config_normalises_approval_thresholds():
    config = ModelConfig(
        calibration_fraction="0.25",
        approval_thresholds=["0.10", "0.15", "0.20"],
        lgd="0.45",
        test_threshold="0.15",
        strategy_incumbent_cutoff="0.15",
        strategy_max_bad_rate="0.13",
        strategy_max_expected_loss_rate="0.06",
        strategy_max_cutoff_increase="0.05",
        strategy_max_bad_rate_increase="0.03",
        strategy_bootstrap_repetitions=500,
        strategy_confidence_level="0.95",
    )

    assert config.approval_thresholds == (0.10, 0.15, 0.20)
    assert config.calibration_fraction == 0.25
    assert config.lgd == 0.45
    assert config.test_threshold == 0.15
    assert config.strategy_incumbent_cutoff == 0.15
    assert config.strategy_max_bad_rate == 0.13
    assert config.strategy_max_expected_loss_rate == 0.06
    assert config.strategy_max_cutoff_increase == 0.05
    assert config.strategy_max_bad_rate_increase == 0.03
    assert config.strategy_bootstrap_repetitions == 500
    assert config.strategy_confidence_level == 0.95


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"calibration_fraction": np.nan}, "calibration_fraction"),
        ({"approval_thresholds": ()}, "approval_thresholds"),
        ({"approval_thresholds": (0.10, 0.10)}, "duplicate"),
        ({"lgd": 1.1}, "lgd"),
        ({"test_threshold": 0.0}, "test_threshold"),
        ({"strategy_incumbent_cutoff": 1.0}, "strategy_incumbent_cutoff"),
        ({"strategy_incumbent_cutoff": 0.17}, "approval_thresholds"),
        ({"strategy_max_bad_rate": -0.1}, "strategy_max_bad_rate"),
        ({"strategy_max_expected_loss_rate": 1.1}, "strategy_max_expected_loss_rate"),
        ({"strategy_max_cutoff_increase": -0.1}, "strategy_max_cutoff_increase"),
        ({"strategy_max_bad_rate_increase": np.inf}, "strategy_max_bad_rate_increase"),
        ({"strategy_bootstrap_repetitions": 0}, "strategy_bootstrap_repetitions"),
        ({"strategy_confidence_level": 1.0}, "strategy_confidence_level"),
    ],
)
def test_model_config_rejects_invalid_risk_parameters(overrides, match):
    with pytest.raises(ValueError, match=match):
        ModelConfig(**overrides)
