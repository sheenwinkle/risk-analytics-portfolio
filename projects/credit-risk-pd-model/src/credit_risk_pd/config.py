from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ModelConfig:
    """Default modelling configuration for the PD workflow."""

    target_col: str = "default"
    date_col: str = "observation_date"
    id_col: str = "customer_id"
    oot_cutoff_date: str = "2022-01-01"
    calibration_fraction: float = 0.25
    approval_thresholds: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25)
    lgd: float = 0.45
    random_state: int = 42
    test_threshold: float = 0.15
    strategy_incumbent_cutoff: float = 0.15
    strategy_max_bad_rate: float = 0.13
    strategy_max_expected_loss_rate: float = 0.06
    strategy_max_cutoff_increase: float = 0.05
    strategy_max_bad_rate_increase: float = 0.03
    strategy_bootstrap_repetitions: int = 2_000
    strategy_confidence_level: float = 0.95

    def __post_init__(self) -> None:
        calibration_fraction = _finite_float(
            self.calibration_fraction,
            "calibration_fraction",
        )
        if not 0 < calibration_fraction < 1:
            raise ValueError("calibration_fraction must be greater than 0 and less than 1.")
        object.__setattr__(self, "calibration_fraction", calibration_fraction)

        thresholds = tuple(
            _finite_float(threshold, "approval_thresholds")
            for threshold in self.approval_thresholds
        )
        if not thresholds:
            raise ValueError("approval_thresholds must contain at least one value.")
        if any(not 0 < threshold < 1 for threshold in thresholds):
            raise ValueError(
                "approval_thresholds must contain values greater than 0 and less than 1."
            )
        if len(set(thresholds)) != len(thresholds):
            raise ValueError("approval_thresholds must not contain duplicate values.")
        object.__setattr__(self, "approval_thresholds", thresholds)

        lgd = _finite_float(self.lgd, "lgd")
        if not 0 <= lgd <= 1:
            raise ValueError("lgd must be between 0 and 1.")
        object.__setattr__(self, "lgd", lgd)

        test_threshold = _finite_float(self.test_threshold, "test_threshold")
        if not 0 < test_threshold < 1:
            raise ValueError("test_threshold must be greater than 0 and less than 1.")
        object.__setattr__(self, "test_threshold", test_threshold)

        strategy_incumbent_cutoff = _finite_float(
            self.strategy_incumbent_cutoff,
            "strategy_incumbent_cutoff",
        )
        if not 0 < strategy_incumbent_cutoff < 1:
            raise ValueError(
                "strategy_incumbent_cutoff must be greater than 0 and less than 1."
            )
        if strategy_incumbent_cutoff not in thresholds:
            raise ValueError(
                "strategy_incumbent_cutoff must be included in approval_thresholds."
            )
        object.__setattr__(self, "strategy_incumbent_cutoff", strategy_incumbent_cutoff)

        for field_name in (
            "strategy_max_bad_rate",
            "strategy_max_expected_loss_rate",
            "strategy_max_cutoff_increase",
            "strategy_max_bad_rate_increase",
        ):
            value = _finite_float(getattr(self, field_name), field_name)
            if not 0 <= value <= 1:
                raise ValueError(f"{field_name} must be between 0 and 1.")
            object.__setattr__(self, field_name, value)

        repetitions = self.strategy_bootstrap_repetitions
        if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions <= 0:
            raise ValueError("strategy_bootstrap_repetitions must be a positive integer.")

        confidence_level = _finite_float(
            self.strategy_confidence_level,
            "strategy_confidence_level",
        )
        if not 0 < confidence_level < 1:
            raise ValueError(
                "strategy_confidence_level must be greater than 0 and less than 1."
            )
        object.__setattr__(self, "strategy_confidence_level", confidence_level)


def _finite_float(value: float, label: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not isfinite(converted):
        raise ValueError(f"{label} must be a finite number.")
    return converted


DEFAULT_CONFIG = ModelConfig()
