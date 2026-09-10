from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]
CASE_STUDY = PROJECT_ROOT / "case-study.md"
PUBLIC_REPORTS = PROJECT_ROOT / "reports" / "public_lendingclub"


def test_case_study_is_recruiter_ready_and_evidence_backed():
    case_study = CASE_STUDY.read_text(encoding="utf-8")
    impact = pd.read_csv(PUBLIC_REPORTS / "strategy_incremental_impact.csv").iloc[0]
    metrics = pd.read_csv(PUBLIC_REPORTS / "model_metrics.csv")
    scoring_audit = pd.read_csv(PUBLIC_REPORTS / "scoring_audit.csv").iloc[0]
    recalibration = pd.read_csv(PUBLIC_REPORTS / "recalibration_summary.csv")

    recalibrated_rf = metrics[
        metrics["model"].eq("random_forest") & metrics["score_type"].eq("recalibrated")
    ].iloc[0]
    raw_rf = metrics[metrics["model"].eq("random_forest") & metrics["score_type"].eq("raw")].iloc[
        0
    ]
    calibrated = recalibration[recalibration["score_type"].eq("recalibrated")].iloc[0]

    required_phrases = [
        "Economics + CS + FRM",
        "My contribution",
        "retrospective champion-challenger backtest",
        "not a randomized A/B test",
        "privacy-safe aggregate evidence",
        "artifact integrity",
        "application_id is not published",
        "policy_input_flags_not_model_attribution",
        "Resume bullet",
        f"{int(scoring_audit['records_scored']):,} public OOT applications",
        f"{int(scoring_audit['batches_scored']):,} governed scoring batches",
        f"{int(impact['incremental_approved_accounts']):,} incremental approvals",
        f"USD {impact['incremental_approved_exposure'] / 1_000_000:.1f}m incremental exposure",
        f"USD {impact['incremental_realized_credit_contribution_proxy'] / 1_000_000:.1f}m realised contribution proxy uplift",
        f"{impact['realized_contribution_ci_lower'] / 1_000_000:.1f}m-{impact['realized_contribution_ci_upper'] / 1_000_000:.1f}m",
        f"ROC-AUC {recalibrated_rf['roc_auc']:.4f}",
        f"Brier {raw_rf['brier_score']:.4f} to {calibrated['brier_score']:.4f}",
    ]

    for phrase in required_phrases:
        assert phrase in case_study


def test_project_readme_links_to_case_study():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "[case study](case-study.md)" in readme


def test_portfolio_readme_links_to_case_study():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "[Project 1 case study](projects/credit-risk-pd-model/case-study.md)" in readme
