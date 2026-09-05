from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from credit_risk_pd.decision_strategy import run_decision_strategy_backtest


def test_strategy_selects_growth_challenger_pre_oot_then_rejects_it_on_oot_evidence():
    result = run_decision_strategy_backtest(
        calibration_pd=[0.05, 0.08, 0.12, 0.14, 0.18, 0.19, 0.22, 0.24],
        calibration_target=[0, 0, 0, 0, 1, 0, 1, 1],
        calibration_exposure=[1_000] * 8,
        calibration_interest_rate=[0.10] * 8,
        oot_pd=[0.05, 0.08, 0.12, 0.14, 0.18, 0.19, 0.22, 0.24],
        oot_target=[0, 0, 0, 0, 1, 1, 1, 1],
        oot_exposure=[1_000] * 8,
        oot_interest_rate=[0.10] * 8,
        candidate_cutoffs=(0.10, 0.15, 0.20, 0.25),
        incumbent_cutoff=0.15,
        max_bad_rate=0.20,
        max_expected_loss_rate=0.10,
        max_bad_rate_increase=0.20,
        lgd=0.50,
        bootstrap_repetitions=500,
        random_state=7,
    )

    selection = result.strategy_selection_audit.set_index("max_pd_cutoff")
    assert selection.loc[0.20, "selected_challenger"]
    assert not selection.loc[0.25, "meets_bad_rate_constraint"]
    assert not selection.loc[0.25, "within_cutoff_change_limit"]
    assert selection.loc[0.20, "selection_sample"] == "pre_oot_calibration_holdout"

    comparison = result.strategy_oot_comparison.set_index("policy")
    assert comparison.loc["incumbent", "approved_accounts"] == 4
    assert comparison.loc["challenger", "approved_accounts"] == 6
    assert comparison.loc["challenger", "approval_rate"] == pytest.approx(0.75)

    impact = result.strategy_incremental_impact.iloc[0]
    assert impact["incremental_approved_accounts"] == 2
    assert impact["incremental_approved_exposure"] == pytest.approx(2_000)
    assert impact["incremental_expected_credit_contribution_proxy"] > 0
    assert impact["incremental_realized_credit_contribution_proxy"] == pytest.approx(-800)
    assert impact["realized_contribution_ci_upper"] < 0

    checks = result.strategy_acceptance_checks.set_index("check")
    assert checks.loc["oot_realized_credit_contribution", "status"] == "fail"
    decision = result.strategy_governance_decision.iloc[0]
    assert decision["decision"] == "retain_incumbent"
    assert decision["overall_status"] == "fail"


def test_strategy_selection_is_unchanged_when_oot_outcomes_change():
    arguments = {
        "calibration_pd": [0.05, 0.12, 0.18, 0.19, 0.24, 0.25],
        "calibration_target": [0, 0, 0, 1, 1, 1],
        "calibration_exposure": [1_000] * 6,
        "calibration_interest_rate": [0.12] * 6,
        "oot_pd": [0.05, 0.12, 0.18, 0.19, 0.24, 0.25],
        "oot_exposure": [1_000] * 6,
        "oot_interest_rate": [0.12] * 6,
        "candidate_cutoffs": (0.10, 0.15, 0.20, 0.25),
        "incumbent_cutoff": 0.15,
        "max_bad_rate": 0.30,
        "max_expected_loss_rate": 0.10,
        "max_bad_rate_increase": 0.30,
        "bootstrap_repetitions": 100,
    }

    low_defaults = run_decision_strategy_backtest(
        **arguments,
        oot_target=[0, 0, 0, 0, 0, 1],
    )
    high_defaults = run_decision_strategy_backtest(
        **arguments,
        oot_target=[0, 0, 1, 1, 1, 1],
    )

    low_selected = low_defaults.strategy_selection_audit.loc[
        low_defaults.strategy_selection_audit["selected_challenger"],
        "max_pd_cutoff",
    ].item()
    high_selected = high_defaults.strategy_selection_audit.loc[
        high_defaults.strategy_selection_audit["selected_challenger"],
        "max_pd_cutoff",
    ].item()
    assert low_selected == high_selected == pytest.approx(0.20)
    assert (
        low_defaults.strategy_governance_decision["decision"].item()
        != high_defaults.strategy_governance_decision["decision"].item()
    )


def test_strategy_bootstrap_is_deterministic():
    kwargs = {
        "calibration_pd": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "calibration_target": [0, 0, 0, 1, 1, 1],
        "calibration_exposure": [1_000, 1_100, 1_200, 1_300, 1_400, 1_500],
        "calibration_interest_rate": [0.10] * 6,
        "oot_pd": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "oot_target": [0, 0, 0, 1, 1, 1],
        "oot_exposure": [1_000, 1_100, 1_200, 1_300, 1_400, 1_500],
        "oot_interest_rate": [0.10] * 6,
        "candidate_cutoffs": (0.10, 0.15, 0.20, 0.25),
        "incumbent_cutoff": 0.15,
        "max_bad_rate": 0.30,
        "max_expected_loss_rate": 0.20,
        "max_bad_rate_increase": 0.30,
        "bootstrap_repetitions": 250,
        "random_state": 91,
    }

    first = run_decision_strategy_backtest(**kwargs)
    second = run_decision_strategy_backtest(**kwargs)

    pd.testing.assert_frame_equal(
        first.strategy_incremental_impact,
        second.strategy_incremental_impact,
    )
    pd.testing.assert_frame_equal(
        first.strategy_acceptance_checks,
        second.strategy_acceptance_checks,
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"oot_pd": [0.10]}, "same length"),
        ({"calibration_target": [0, 2, 0, 1, 1, 1]}, "binary"),
        ({"oot_interest_rate": [0.1, 0.1, np.inf, 0.1, 0.1, 0.1]}, "interest"),
        ({"incumbent_cutoff": 0.17}, "incumbent cutoff"),
        ({"max_cutoff_increase": -0.1}, "max_cutoff_increase"),
        ({"bootstrap_repetitions": 0}, "bootstrap_repetitions"),
        ({"confidence_level": 1.0}, "confidence_level"),
    ],
)
def test_strategy_rejects_invalid_inputs(override, message):
    arguments = {
        "calibration_pd": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "calibration_target": [0, 0, 0, 1, 1, 1],
        "calibration_exposure": [1_000] * 6,
        "calibration_interest_rate": [0.10] * 6,
        "oot_pd": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "oot_target": [0, 0, 0, 1, 1, 1],
        "oot_exposure": [1_000] * 6,
        "oot_interest_rate": [0.10] * 6,
        "candidate_cutoffs": (0.10, 0.15, 0.20, 0.25),
        "incumbent_cutoff": 0.15,
        "max_bad_rate": 0.30,
        "max_expected_loss_rate": 0.20,
        "max_bad_rate_increase": 0.30,
        "bootstrap_repetitions": 100,
    }
    arguments.update(override)

    with pytest.raises(ValueError, match=message):
        run_decision_strategy_backtest(**arguments)
