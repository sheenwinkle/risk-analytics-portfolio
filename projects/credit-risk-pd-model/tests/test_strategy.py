import pandas as pd
import pytest

from credit_risk_pd.strategy import approval_strategy_table


def test_approval_strategy_table_calculates_fixed_threshold_scenarios_exactly():
    pd_scores = pd.Series([0.02, 0.05, 0.08, 0.12, 0.20])
    y_true = pd.Series([0, 1, 0, 1, 1])
    exposures = pd.Series([1000, 2000, 3000, 4000, 5000])

    strategy = approval_strategy_table(
        pd_scores,
        y_true,
        exposures,
        thresholds=(0.05, 0.10),
        lgd=0.50,
    )

    first = strategy.loc[strategy["max_pd_cutoff"].eq(0.05)].iloc[0]
    assert first["lgd"] == pytest.approx(0.50)
    assert first["approved_accounts"] == 2
    assert first["rejected_accounts"] == 3
    assert first["approval_rate"] == pytest.approx(2 / 5)
    assert first["approved_observed_defaults"] == 1
    assert first["approved_default_rate"] == pytest.approx(1 / 2)
    assert first["approved_exposure"] == pytest.approx(3000)
    assert first["expected_loss"] == pytest.approx((0.02 * 1000 + 0.05 * 2000) * 0.50)
    assert first["expected_loss_rate"] == pytest.approx(first["expected_loss"] / 3000)
    assert first["rejected_default_capture_rate"] == pytest.approx(2 / 3)

    second = strategy.loc[strategy["max_pd_cutoff"].eq(0.10)].iloc[0]
    assert second["approved_accounts"] == 3
    assert second["rejected_accounts"] == 2
    assert second["approved_exposure"] == pytest.approx(6000)
    assert second["expected_loss"] == pytest.approx(
        (0.02 * 1000 + 0.05 * 2000 + 0.08 * 3000) * 0.50
    )


@pytest.mark.parametrize(
    ("pd_scores", "y_true", "exposures", "thresholds", "lgd", "match"),
    [
        ([0.1, 1.1], [0, 1], [100, 100], (0.2,), 0.45, "between 0 and 1"),
        ([0.1, 0.2], [0, 2], [100, 100], (0.2,), 0.45, "binary"),
        ([0.1, 0.2], [0, 1], [100, -1], (0.2,), 0.45, "nonnegative"),
        ([0.1, 0.2], [0, 1], [100, 100], (0.0,), 0.45, "thresholds"),
        ([0.1, 0.2], [0, 1], [100, 100], (0.2,), 1.5, "LGD"),
        ([0.1, 0.2], [0], [100, 100], (0.2,), 0.45, "same length"),
        ([], [], [], (0.2,), 0.45, "at least one"),
        ([0.1], [0], [100], (0.2, 0.2), 0.45, "duplicate"),
    ],
)
def test_approval_strategy_table_validates_inputs(
    pd_scores,
    y_true,
    exposures,
    thresholds,
    lgd,
    match,
):
    with pytest.raises(ValueError, match=match):
        approval_strategy_table(pd_scores, y_true, exposures, thresholds=thresholds, lgd=lgd)
