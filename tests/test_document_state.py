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
