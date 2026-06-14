from academic_pe.contracts.drift import (
    check_academic_drift,
    check_ai_markers,
    check_forbidden_citations,
    check_forbidden_rubric,
    check_forbidden_title_page,
    check_forbidden_visualization,
    check_genre_style_markers,
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


def test_detects_apology_wrappers_and_template_filler():
    result = check_ai_markers(
        _contract(),
        {
            "story": (
                "Here is the requested story.\n"
                "I apologize, but this is only a draft.\n"
                "[TODO] Add real ending.\n"
                "Lorem ipsum."
            )
        },
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


def test_detects_new_ai_smoothness_markers():
    for word in [
        "disclaimer",
        "this document does not",
        "please note that",
        "feel free to",
        "hope this helps",
        "if you have any questions",
        "important note",
        "note: ",
        "for the purposes of this",
        "due to safety guidelines",
        "delve",
        "testament",
    ]:
        result = check_ai_markers(
            _contract(),
            {"essay": f"Let us {word} into the matter."},
        )
        assert not result.passed, f"Failed to detect AI smoothness marker: {word}"
        assert "AI/meta" in result.issues[0]


def test_detects_poem_explanation_instead_of_poetic_text():
    result = check_genre_style_markers(
        _contract(artifact="creative_poem"),
        {"poem": "Analysis:\nThis poem explores the symbolic role of rain."},
    )

    assert not result.passed
    assert "poetic text" in result.issues[0]


def test_detects_story_summary_wrapper_instead_of_narrative():
    result = check_genre_style_markers(
        _contract(artifact="creative_story"),
        {"story": "In this story, a child learns to be brave."},
    )

    assert not result.passed
    assert "artifact-native narrative" in result.issues[0]


def test_detects_research_register_in_school_essay():
    result = check_genre_style_markers(
        _contract(artifact="school_essay"),
        {"essay": "The methodological framework is supported by peer-reviewed literature."},
    )

    assert not result.passed
    assert "school essay" in result.issues[0]


def test_detects_academic_prose_in_readme():
    result = check_genre_style_markers(
        _contract(artifact="technical_readme"),
        {"readme": "The present study describes the package methodology."},
    )

    assert not result.passed
    assert "technical README" in result.issues[0]


def test_detects_generic_filler_in_academic_paper():
    result = check_genre_style_markers(
        _contract(artifact="academic_paper"),
        {"paper": "In today's world, this topic is very interesting."},
    )

    assert not result.passed
    assert "generic filler" in result.issues[0]


def test_genre_style_check_passes_artifact_native_examples():
    examples = [
        (_contract(artifact="creative_poem"), {"poem": "Red silk in rain\nA quiet window glows."}),
        (_contract(artifact="creative_story"), {"story": "Mira opened the blue door and heard the sea inside."}),
        (_contract(artifact="school_essay"), {"essay": "I think summer holidays are important because we rest and learn new things."}),
        (_contract(artifact="technical_readme"), {"readme": "# Usage\nRun `ape start` after installation."}),
        (_contract(artifact="academic_paper"), {"paper": "The analysis defines the dataset, assumptions, and limitations."}),
    ]

    for contract, context in examples:
        result = check_genre_style_markers(contract, context)

        assert result.passed
