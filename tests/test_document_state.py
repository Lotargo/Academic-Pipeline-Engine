from academic_pe.core.document_state import extract_document_state


def test_extract_document_state_from_continuation_source():
    state = extract_document_state(
        {
            "context": {
                "analysis": "Analysis body.",
                "references": "1. Existing source.",
                "appendix_a": "Raw data.",
            },
            "runtime_template": {
                "sections": [
                    {
                        "name": "analysis",
                        "title": "Analysis",
                        "semantic_role": "academic_section",
                        "heading_policy": "render_required",
                    },
                    {
                        "name": "references",
                        "title": "References",
                        "semantic_role": "reference_section",
                    },
                    {
                        "name": "appendix_a",
                        "title": "Appendix A",
                        "semantic_role": "appendix",
                    },
                ]
            },
            "runtime_prompt_manifest": {
                "metadata": {
                    "resolved_manifest": {"id": "academic_report"},
                }
            },
        }
    )

    assert [section.name for section in state.source_sections] == [
        "analysis",
        "references",
        "appendix_a",
    ]
    assert state.rendered_body["analysis"] == "Analysis body."
    assert state.source_sections[0].semantic_role == "academic_section"
    assert state.terminal_sections == ["references", "appendix_a"]
    assert state.headings == ["Analysis", "References", "Appendix A"]
    assert state.runtime_manifest["resolved_manifest"]["id"] == "academic_report"


def test_extract_document_state_ignores_document_plan_context():
    state = extract_document_state(
        {
            "context": {
                "document_plan": "Internal plan.",
                "body": "Visible body.",
            }
        }
    )

    assert [section.name for section in state.source_sections] == ["body"]
    assert "document_plan" not in state.rendered_body


def test_extract_document_state_builds_heading_tree_style_and_dossier():
    state = extract_document_state(
        {
            "context": {
                "chapter_1": (
                    "## 1.1 Problem\n\n"
                    "We analyze Pipeline Engine behavior and preserve style.\n\n"
                    "Table 1 shows the baseline. Formula (1) defines the score.\n\n"
                    "The next step must continue from this point."
                ),
                "references": (
                    "1. Smith (2024). Pipeline testing.\n"
                    "- Иванов (2023). Академические пайплайны.\n"
                    "1. Smith (2024). Pipeline testing."
                ),
            },
            "runtime_template": {
                "sections": [
                    {
                        "name": "chapter_1",
                        "title": "Chapter 1",
                        "semantic_role": "chapter",
                        "heading_policy": "render_required",
                    },
                    {
                        "name": "references",
                        "title": "References",
                        "semantic_role": "reference_section",
                    },
                ]
            },
        }
    )

    assert [(heading.title, heading.level, heading.source) for heading in state.heading_tree] == [
        ("Chapter 1", 1, "section"),
        ("1.1 Problem", 2, "markdown"),
        ("References", 1, "section"),
    ]
    assert state.style_profile.language_hint == "en"
    assert state.style_profile.heading_style == "markdown"
    assert state.style_profile.citation_style == "numbered"
    assert state.style_profile.has_numbered_headings is True
    assert [(entry.marker, entry.style) for entry in state.reference_registry] == [
        ("1", "numbered"),
        ("", "author_year"),
    ]
    assert ("table", "1", "chapter_1") in [
        (label.label_type, label.label, label.section_name)
        for label in state.structural_labels
    ]
    assert ("formula", "1", "chapter_1") in [
        (label.label_type, label.label, label.section_name)
        for label in state.structural_labels
    ]
    assert state.continuity_dossier.current_stopping_point == "The next step must continue from this point."
    assert state.continuity_dossier.reference_summary == "2 reference(s), style=numbered"
