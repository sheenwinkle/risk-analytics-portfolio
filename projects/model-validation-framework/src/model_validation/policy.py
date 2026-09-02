from __future__ import annotations

import math
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ValidationPolicy:
    """Traffic-light thresholds for independent PD model validation.

    Higher AUC and KS are better. Lower absolute calibration gap, PSI, and challenger
    AUC margin are better. Green maps to pass, amber maps to warning, and red maps to fail.
    The challenger margin is challenger raw AUC minus selected recalibrated incumbent AUC.
    """

    auc_green_min: float = 0.70
    auc_warning_min: float = 0.60
    ks_green_min: float = 0.30
    ks_warning_min: float = 0.20
    absolute_calibration_gap_green_max: float = 0.01
    absolute_calibration_gap_warning_max: float = 0.03
    psi_green_max: float = 0.10
    psi_warning_max: float = 0.25
    challenger_auc_margin_green_max: float = 0.01
    challenger_auc_margin_warning_max: float = 0.03

    def __post_init__(self) -> None:
        values = [getattr(self, item.name) for item in fields(self)]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
            raise ValueError("ValidationPolicy thresholds must be finite numbers")

        minimum_pairs = (
            (self.auc_green_min, self.auc_warning_min),
            (self.ks_green_min, self.ks_warning_min),
        )
        maximum_pairs = (
            (
                self.absolute_calibration_gap_green_max,
                self.absolute_calibration_gap_warning_max,
            ),
            (self.psi_green_max, self.psi_warning_max),
            (
                self.challenger_auc_margin_green_max,
                self.challenger_auc_margin_warning_max,
            ),
        )
        if any(green < warning for green, warning in minimum_pairs) or any(
            green > warning for green, warning in maximum_pairs
        ):
            raise ValueError(
                "ValidationPolicy thresholds must order green before warning"
            )

    def status_for_minimum(self, value: float, green_min: float, warning_min: float) -> str:
        if value >= green_min:
            return "pass"
        if value >= warning_min:
            return "warning"
        return "fail"

    def status_for_maximum(self, value: float, green_max: float, warning_max: float) -> str:
        if value <= green_max:
            return "pass"
        if value <= warning_max:
            return "warning"
        return "fail"
