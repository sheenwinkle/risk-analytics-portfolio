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


def _finite_float(value: float, label: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not isfinite(converted):
        raise ValueError(f"{label} must be a finite number.")
    return converted


DEFAULT_CONFIG = ModelConfig()

