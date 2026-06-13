from academic_pe.contracts.drift import (
    check_academic_drift,
    check_ai_markers,
    check_forbidden_citations,
    check_forbidden_rubric,
    check_forbidden_title_page,
    check_forbidden_visualization,
    run_all,
)
from academic_pe.contracts.models import ArtifactContract


def _contract(**kwargs) -> ArtifactContract:
    data = {
        "manifest_id": "creative_poem",
        "artifact": "creative_poem",
        "forbid": [
            "academic_drift",
            "research_paper_structure",
            "forced_visualization",
            "ai_markers",
            "citations",
            "title_page",
            "rubric",
        ],
        "visualization_required": False,
    }
    data.update(kwargs)
    return ArtifactContract(**data)


def test_drift_checks_pass_clean_poem():
    result = run_all(
        _contract(),
        {"poem": "Red silk in rain\nA quiet window glows\nNo footnotes, no masks."},
    )

    assert result.passed
    assert result.issues == []


def test_detects_academic_drift_when_forbidden():
    result = check_academic_drift(
        _contract(),
        {"poem": "# Abstract\nThis paper analyzes the symbolic role of red."},
    )

    assert not result.passed
    assert "academic-paper structure" in result.issues[0]


def test_allows_academic_sections_when_not_forbidden():
    contract = _contract(forbid=[])

    result = check_academic_drift(
        contract,
        {"paper": "# Abstract\nThis paper analyzes the symbolic role of red."},
    )

    assert result.passed


def test_detects_forbidden_visualization_artifact():
    result = check_forbidden_visualization(
        _contract(),
        {"poem": "![Plot](exports/run_1/plot_poem.png)"},
    )

    assert not result.passed
    assert "visualization artifact" in result.issues[0]


def test_allows_visualization_when_contract_requires_it():
    result = check_forbidden_visualization(
        _contract(visualization_required=True),
        {"paper": "![Plot](exports/run_1/plot_analysis.png)"},
    )

    assert result.passed


def test_detects_ai_markers_and_placeholders():
    result = check_ai_markers(
        _contract(),
        {"readme": "As an AI language model, I cannot verify this. [insert link]"},
    )

    assert not result.passed
    assert "AI/meta" in result.issues[0]


def test_detects_forbidden_citation_apparatus():
    result = check_forbidden_citations(
        _contract(),
        {"story": "The sky was red (Ivanov, 2024).\n\n# References\nA source."},
    )

    assert not result.passed
    assert "citations" in result.issues[0]


def test_detects_forbidden_title_page_near_top():
    result = check_forbidden_title_page(
        _contract(),
        {"essay": "# Title Page\nAuthor: Student\n\nText starts here."},
    )

    assert not result.passed
    assert "title-page apparatus" in result.issues[0]


def test_detects_forbidden_rubric():
    result = check_forbidden_rubric(
        _contract(),
        {"essay": "# Grading Criteria\n- Imagery: 5 points"},
    )

    assert not result.passed
    assert "rubric" in result.issues[0]
