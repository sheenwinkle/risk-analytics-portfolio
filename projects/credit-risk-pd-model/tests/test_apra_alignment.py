from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]
ALIGNMENT_MATRIX = REPO_ROOT / "docs" / "apra-alignment-matrix.md"


def test_apra_alignment_matrix_sets_regulatory_boundary():
    matrix = ALIGNMENT_MATRIX.read_text(encoding="utf-8")

    required_phrases = [
        "APRA-aligned portfolio artifact",
        "not an APRA-compliant production framework",
        "not APRA-approved",
        "Implemented",
        "Partially aligned",
        "Not in scope",
        "APS 220 Credit Risk Management",
        "APG 220 Credit Risk Management",
        "APS 113 Internal Ratings-based Approach",
        "CPS 220 Risk Management",
        "CPS 230 Operational Risk Management",
        "CPS 234 Information Security",
        "Credit risk appetite and strategy",
        "Rating-system development, validation, and monitoring",
        "Operational resilience and business continuity",
        "Information security and PII controls",
        "resume-safe wording",
    ]

    for phrase in required_phrases:
        assert phrase in matrix


def test_portfolio_readme_links_apra_alignment_matrix_and_avoids_compliance_claim():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "[APRA alignment matrix](docs/apra-alignment-matrix.md)" in readme
    assert "APRA-aligned" in readme
    assert "APRA-compliant" not in readme


def test_project_docs_do_not_overstate_apra_compliance():
    searched_docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "portfolio-roadmap.md",
        REPO_ROOT / "docs" / "resume-project-description.md",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "case-study.md",
        PROJECT_ROOT / "interview-walkthrough.md",
    ]

    for path in searched_docs:
        text = path.read_text(encoding="utf-8")
        assert "APRA-compliant" not in text
        assert "APRA compliant" not in text

    resume_text = (REPO_ROOT / "docs" / "resume-project-description.md").read_text(
        encoding="utf-8"
    )
    assert "APRA-aligned educational portfolio" in resume_text


def test_project_entry_points_link_apra_alignment_boundary():
    expected_link = "[APRA alignment matrix](../../docs/apra-alignment-matrix.md)"
    for path in [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "case-study.md",
        PROJECT_ROOT / "interview-walkthrough.md",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "APRA-aligned" in text
        assert expected_link in text
