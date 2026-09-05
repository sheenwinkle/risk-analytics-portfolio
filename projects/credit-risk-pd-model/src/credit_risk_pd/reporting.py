from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from credit_risk_pd.woe import WOE_SIGN_CONVENTION

MetricFormatter = Callable[[object], str]


def generate_model_report(reports_dir: str | Path = "reports") -> Path:
    """Generate a recruiter-readable markdown summary from model report CSVs."""
    reports_path = Path(reports_dir)
    metrics = _read_csv(
        reports_path / "model_metrics.csv",
        [
            "model",
            "score_type",
            "classification_threshold",
            "roc_auc",
            "gini",
            "ks",
            "brier_score",
            "precision",
            "recall",
        ],
    )
    selection = _read_csv(
        reports_path / "model_selection_audit.csv",
        [
            "model",
            "model_development_accounts",
            "calibration_holdout_accounts",
            "model_development_start",
            "model_development_end",
            "calibration_holdout_start",
            "calibration_holdout_end",
            "calibration_holdout_roc_auc",
            "selected_model",
        ],
    )
    recalibration = _read_csv(
        reports_path / "recalibration_summary.csv",
        [
            "model",
            "score_type",
            "evaluation_sample",
            "recalibration_fit_sample",
            "recalibration_fit_intercept",
            "recalibration_fit_slope",
            "calibration_intercept",
            "calibration_slope",
            "brier_score",
            "log_loss",
            "mean_pd",
            "observed_default_rate",
        ],
    )
    strategy = _read_csv(
        reports_path / "approval_strategy.csv",
        [
            "max_pd_cutoff",
            "lgd",
            "approved_accounts",
            "rejected_accounts",
            "approval_rate",
            "approved_observed_defaults",
            "approved_default_rate",
            "approved_exposure",
            "expected_loss",
            "expected_loss_rate",
            "rejected_default_capture_rate",
        ],
    )
    strategy_selection = _read_csv(
        reports_path / "strategy_selection_audit.csv",
        [
            "selection_sample",
            "max_pd_cutoff",
            "incumbent_policy",
            "approved_accounts",
            "approval_rate",
            "approved_default_rate",
            "expected_loss_rate",
            "max_bad_rate_constraint",
            "max_expected_loss_rate_constraint",
            "eligible_growth_challenger",
            "selected_challenger",
        ],
    )
    strategy_comparison = _read_csv(
        reports_path / "strategy_oot_comparison.csv",
        [
            "evaluation_sample",
            "policy",
            "max_pd_cutoff",
            "approved_accounts",
            "approval_rate",
            "approved_default_rate",
            "approved_exposure",
            "expected_loss",
            "realized_loss_proxy",
            "expected_credit_contribution_proxy",
            "realized_credit_contribution_proxy",
        ],
    )
    strategy_impact = _read_csv(
        reports_path / "strategy_incremental_impact.csv",
        [
            "incremental_approved_accounts",
            "incremental_approval_rate",
            "incremental_approved_exposure",
            "incremental_expected_credit_contribution_proxy",
            "incremental_realized_credit_contribution_proxy",
            "marginal_observed_default_rate",
            "realized_contribution_ci_lower",
            "realized_contribution_ci_upper",
            "confidence_level",
        ],
    )
    strategy_checks = _read_csv(
        reports_path / "strategy_acceptance_checks.csv",
        [
            "check",
            "metric_value",
            "threshold",
            "direction",
            "confidence_lower",
            "confidence_upper",
            "status",
            "detail",
        ],
    )
    strategy_decision = _read_csv(
        reports_path / "strategy_governance_decision.csv",
        [
            "incumbent_cutoff",
            "challenger_cutoff",
            "overall_status",
            "decision",
            "evidence_type",
            "causal_claim",
        ],
    )
    calibration = _read_csv(
        reports_path / "calibration_table.csv",
        [
            "bucket",
            "accounts",
            "predicted_pd",
            "observed_default_rate",
            "defaults",
            "calibration_gap",
        ],
    )
    psi = _read_csv(reports_path / "psi_report.csv", ["feature", "psi", "status"])
    woe_summary = _read_csv(
        reports_path / "woe_summary.csv",
        ["rank", "feature", "feature_type", "bins", "information_value", "iv_band"],
    )
    feature_importance = _read_csv(
        reports_path / "feature_importance.csv",
        ["feature", "importance_mean", "importance_std"],
    )

    selection = selection.sort_values(
        ["selected_model", "calibration_holdout_roc_auc"],
        ascending=[False, False],
    ).reset_index(drop=True)
    selected_model = selection.loc[selection["selected_model"].astype(bool)].iloc[0]
    selected_model_name = selected_model["model"]
    metrics = metrics.sort_values(["model", "score_type"]).reset_index(drop=True)
    feature_importance = feature_importance.sort_values(
        "importance_mean",
        ascending=False,
    ).reset_index(drop=True)
    woe_summary = woe_summary.sort_values(
        ["information_value", "feature"],
        ascending=[False, True],
    ).reset_index(drop=True)
    selected_recalibrated = metrics.loc[
        metrics["model"].eq(selected_model_name) & metrics["score_type"].eq("recalibrated")
    ].iloc[0]
    selected_recalibration = recalibration.loc[
        recalibration["model"].eq(selected_model_name)
    ].iloc[0]
    material_shift_count = int(psi["status"].eq("material_shift").sum())
    moderate_shift_count = int(psi["status"].eq("moderate_shift").sum())
    top_drift_feature = psi.sort_values("psi", ascending=False).iloc[0]
    top_importance_feature = feature_importance.iloc[0]
    top_iv_feature = woe_summary.iloc[0]
    largest_gap = float(calibration["calibration_gap"].abs().max())
    decision = strategy_decision.iloc[0]
    incremental_impact = strategy_impact.iloc[0]

    report = "\n".join(
        [
            "# Credit Risk PD Model Report",
            "",
            "## Executive Summary",
            "",
            (
                "- Selected model by pre-OOT calibration holdout ROC-AUC: "
                f"`{selected_model_name}`."
            ),
            (
                "- Discrimination: "
                f"OOT recalibrated ROC-AUC {_format_decimal(selected_recalibrated['roc_auc'])}, "
                f"Gini {_format_decimal(selected_recalibrated['gini'])}, "
                f"KS {_format_decimal(selected_recalibrated['ks'])}."
            ),
            (
                "- PD recalibration: "
                f"OOT recalibrated Brier score "
                f"{_format_decimal(selected_recalibrated['brier_score'])}; "
                f"largest absolute decile gap {_format_percent(largest_gap)}."
            ),
            (
                "- Stability: "
                f"{material_shift_count} material shift feature(s), "
                f"{moderate_shift_count} moderate shift feature(s); "
                f"top PSI feature `{top_drift_feature['feature']}` "
                f"({_format_decimal(top_drift_feature['psi'])})."
            ),
            (
                "- Explainability: "
                f"top out-of-time permutation importance feature "
                f"`{top_importance_feature['feature']}` "
                f"({_format_decimal(top_importance_feature['importance_mean'])} mean "
                "ROC-AUC decrease after permutation)."
            ),
            (
                "- Scorecard diagnostics: "
                f"top development-sample Information Value feature "
                f"`{top_iv_feature['feature']}` "
                f"({_format_decimal(top_iv_feature['information_value'])}, "
                f"{top_iv_feature['iv_band']})."
            ),
            (
                "- Credit decision strategy: "
                f"`{decision['decision']}` after a pre-OOT selected "
                f"{_format_percent(decision['challenger_cutoff'])} challenger was evaluated "
                "on untouched OOT outcomes."
            ),
            "",
            "## Model Performance",
            "",
            (
                "Model selection occurred before OOT evaluation: candidates were trained on the "
                "earlier model-development sample and selected by ROC-AUC on the later pre-OOT "
                "calibration holdout."
            ),
            (
                "Precision, recall, accuracy, and confusion counts use the fixed configured "
                "threshold of "
                f"{_format_percent(selected_recalibrated['classification_threshold'])}; "
                "it is not tuned on OOT outcomes."
            ),
            "",
            _markdown_table(
                selection,
                [
                    ("model", "Model", str),
                    ("model_development_accounts", "Dev Accounts", _format_integer),
                    ("calibration_holdout_accounts", "Holdout Accounts", _format_integer),
                    ("model_development_end", "Dev End", str),
                    ("calibration_holdout_start", "Holdout Start", str),
                    ("calibration_holdout_roc_auc", "Holdout ROC-AUC", _format_decimal),
                    ("selected_model", "Selected", _format_boolean),
                ],
            ),
            "",
            _markdown_table(
                metrics,
                [
                    ("model", "Model", str),
                    ("score_type", "Score", str),
                    ("classification_threshold", "Threshold", _format_percent),
                    ("roc_auc", "ROC-AUC", _format_decimal),
                    ("gini", "Gini", _format_decimal),
                    ("ks", "KS", _format_decimal),
                    ("brier_score", "Brier", _format_decimal),
                    ("precision", "Precision", _format_percent),
                    ("recall", "Recall", _format_percent),
                ],
            ),
            "",
            "## PD Recalibration",
            "",
            (
                "Logistic recalibration is fitted only on the pre-OOT calibration holdout. "
                "Raw and recalibrated PD diagnostics below are calculated on the untouched "
                "OOT sample."
            ),
            (
                "Fitted transform: logit(PD_recalibrated) = "
                f"{_format_decimal(selected_recalibration['recalibration_fit_intercept'])} + "
                f"{_format_decimal(selected_recalibration['recalibration_fit_slope'])} x "
                "logit(PD_raw)."
            ),
            "",
            _markdown_table(
                recalibration.loc[recalibration["model"].eq(selected_model_name)],
                [
                    ("score_type", "Score", str),
                    ("calibration_intercept", "Intercept", _format_decimal),
                    ("calibration_slope", "Slope", _format_decimal),
                    ("brier_score", "Brier", _format_decimal),
                    ("log_loss", "Log Loss", _format_decimal),
                    ("mean_pd", "Mean PD", _format_percent),
                    ("observed_default_rate", "Observed Default Rate", _format_percent),
                ],
            ),
            "",
            "## Calibration Review",
            "",
            (
                "Decile calibration runs from D01 (lowest predicted PD) to D10 (highest). "
                "Positive gaps indicate predicted PD is above the realised default rate."
            ),
            "",
            _markdown_table(
                calibration,
                [
                    ("bucket", "PD Bucket", str),
                    ("accounts", "Accounts", _format_integer),
                    ("predicted_pd", "Predicted PD", _format_percent),
                    ("observed_default_rate", "Observed Default Rate", _format_percent),
                    ("defaults", "Defaults", _format_integer),
                    ("calibration_gap", "Gap", _format_percent),
                ],
            ),
            "",
            "## Lending Strategy",
            "",
            (
                "Approval cutoffs are fixed scenario rows, not recommendations. Expected loss is "
                "calculated as the sum of recalibrated PD x LGD x EAD for approved accounts, "
                "using loan_amount as an EAD proxy."
            ),
            "",
            _markdown_table(
                strategy,
                [
                    ("max_pd_cutoff", "Max PD", _format_percent),
                    ("lgd", "LGD", _format_percent),
                    ("approved_accounts", "Approved", _format_integer),
                    ("approval_rate", "Approval Rate", _format_percent),
                    ("approved_default_rate", "Approved Default Rate", _format_percent),
                    ("approved_exposure", "Approved Exposure", _format_integer),
                    ("expected_loss", "Expected Loss", _format_integer),
                    ("expected_loss_rate", "Expected Loss Rate", _format_percent),
                    (
                        "rejected_default_capture_rate",
                        "Rejected Default Capture",
                        _format_percent,
                    ),
                ],
            ),
            "",
            "## Pre-OOT Champion-Challenger Strategy",
            "",
            (
                "The growth challenger is selected only on the pre-OOT calibration holdout "
                "by maximising approval rate subject to observed bad-rate and expected-loss-rate "
                "constraints. The cutoff is then frozen before OOT evaluation."
            ),
            (
                "The same pre-OOT holdout supports recalibration and policy development; this "
                "can make selection evidence optimistic, but it does not contaminate the frozen "
                "OOT acceptance decision."
            ),
            (
                "This is a retrospective paired champion-challenger backtest, not a randomized "
                "A/B test, so it quantifies historical policy impact without making a causal claim."
            ),
            f"Decision: **{str(decision['decision']).replace('_', ' ').upper()}**.",
            (
                f"The challenger produced {_format_integer(incremental_impact['incremental_approved_accounts'])} "
                "incremental approvals and "
                f"{_format_integer(incremental_impact['incremental_approved_exposure'])} "
                "incremental exposure. Expected credit contribution changed by "
                f"{_format_integer(incremental_impact['incremental_expected_credit_contribution_proxy'])}, "
                "while the realised contribution proxy changed by "
                f"{_format_integer(incremental_impact['incremental_realized_credit_contribution_proxy'])} "
                f"({_format_percent(incremental_impact['confidence_level'])} paired bootstrap "
                f"interval {_format_integer(incremental_impact['realized_contribution_ci_lower'])} "
                f"to {_format_integer(incremental_impact['realized_contribution_ci_upper'])})."
            ),
            (
                "Credit contribution is a deliberately simplified one-year proxy: interest "
                "income less PD x LGD x EAD for expected results, and interest income less "
                "observed-default x LGD x EAD for realised results. It excludes funding, "
                "operating costs, prepayment, and timing."
            ),
            "",
            "### Pre-OOT Selection",
            "",
            _markdown_table(
                strategy_selection,
                [
                    ("max_pd_cutoff", "Max PD", _format_percent),
                    ("incumbent_policy", "Incumbent", _format_boolean),
                    ("approval_rate", "Approval Rate", _format_percent),
                    ("approved_default_rate", "Observed Bad Rate", _format_percent),
                    ("expected_loss_rate", "Expected Loss Rate", _format_percent),
                    ("eligible_growth_challenger", "Eligible", _format_boolean),
                    ("selected_challenger", "Selected", _format_boolean),
                ],
            ),
            "",
            "### OOT Policy Comparison",
            "",
            _markdown_table(
                strategy_comparison,
                [
                    ("policy", "Policy", str),
                    ("max_pd_cutoff", "Max PD", _format_percent),
                    ("approved_accounts", "Approved", _format_integer),
                    ("approval_rate", "Approval Rate", _format_percent),
                    ("approved_default_rate", "Observed Bad Rate", _format_percent),
                    ("approved_exposure", "Approved Exposure", _format_integer),
                    ("expected_credit_contribution_proxy", "Expected Contribution", _format_integer),
                    ("realized_credit_contribution_proxy", "Realised Contribution", _format_integer),
                ],
            ),
            "",
            "### Acceptance Checks",
            "",
            _markdown_table(
                strategy_checks,
                [
                    ("check", "Check", str),
                    ("metric_value", "Value", _format_decimal),
                    ("threshold", "Threshold", _format_decimal),
                    ("confidence_lower", "CI Lower", _format_decimal),
                    ("confidence_upper", "CI Upper", _format_decimal),
                    ("status", "Status", str),
                ],
            ),
            "",
            "## Feature Importance",
            "",
            (
                "Permutation importance measures the drop in out-of-time ROC-AUC when each "
                "input feature is shuffled, giving model-agnostic evidence for validation review."
            ),
            "",
            _markdown_table(
                feature_importance,
                [
                    ("feature", "Feature", str),
                    ("importance_mean", "Mean ROC-AUC Drop", _format_decimal),
                    ("importance_std", "Std Dev", _format_decimal),
                ],
            ),
            "",
            "## Information Value",
            "",
            (
                "Weight of Evidence and Information Value are calculated on the development "
                "sample for scorecard-style variable screening. "
                f"{WOE_SIGN_CONVENTION}"
            ),
            "",
            _markdown_table(
                woe_summary,
                [
                    ("rank", "Rank", _format_integer),
                    ("feature", "Feature", str),
                    ("feature_type", "Type", str),
                    ("bins", "Bins", _format_integer),
                    ("information_value", "IV", _format_decimal),
                    ("iv_band", "Band", str),
                ],
            ),
            "",
            "## Population Stability",
            "",
            (
                "PSI highlights feature drift between the development and out-of-time samples, "
                "supporting model monitoring and validation review."
            ),
            "",
            _markdown_table(
                psi.sort_values("psi", ascending=False),
                [
                    ("feature", "Feature", str),
                    ("psi", "PSI", _format_decimal),
                    ("status", "Status", str),
                ],
            ),
            "",
        ]
    )

    report_path = reports_path / "model_report.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    return report_path


def _read_csv(path: Path, required_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing report input: {path}")

    frame = pd.read_csv(path)
    missing = sorted(set(required_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required column(s): {', '.join(missing)}")
    if frame.empty:
        raise ValueError(f"{path} must contain at least one row")
    return frame


def _markdown_table(
    frame: pd.DataFrame,
    columns: list[tuple[str, str, MetricFormatter]],
) -> str:
    header = "| " + " | ".join(label for _, label, _ in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| "
        + " | ".join(formatter(row[column]) for column, _, formatter in columns)
        + " |"
        for _, row in frame.iterrows()
    ]
    return "\n".join([header, separator, *rows])


def _format_decimal(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.3f}"


def _format_percent(value: object) -> str:
    return f"{float(value):.1%}"


def _format_integer(value: object) -> str:
    return f"{float(value):.0f}"


def _format_boolean(value: object) -> str:
    return "yes" if bool(value) else "no"
