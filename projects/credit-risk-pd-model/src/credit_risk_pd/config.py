from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Default modelling configuration for the PD workflow."""

    target_col: str = "default"
    date_col: str = "observation_date"
    id_col: str = "customer_id"
    oot_cutoff_date: str = "2022-01-01"
    random_state: int = 42
    test_threshold: float = 0.5


DEFAULT_CONFIG = ModelConfig()

