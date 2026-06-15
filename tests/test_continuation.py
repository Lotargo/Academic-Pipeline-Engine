from academic_pe.core.continuation import (
    ContinuationIntent,
    detect_terminal_sections,
    infer_continuation_intent,
    source_has_hard_ending,
)


def test_continue_without_extra_instruction_bridges_closed_ending():
    source = {
        "context": {
            "story": "They closed the door and smiled at the dawn. The end.",
        }
    }

    resolution = infer_continuation_intent(
        topic="Continue",
        instructions="",
        continuation_source=source,
    )

    assert resolution is not None
    assert resolution.intent == ContinuationIntent.bridge_and_continue
    assert source_has_hard_ending(source) is True


def test_continue_without_hard_ending_appends():
    source = {
        "context": {
            "story": "The corridor bent left, and the candle went out.",
        }
    }

    resolution = infer_continuation_intent(
        topic="Continue",
        instructions="",
        continuation_source=source,
    )

    assert resolution is not None
    assert resolution.intent == ContinuationIntent.continue_append


def test_user_intent_override_wins_over_inferred_intent():
    resolution = infer_continuation_intent(
        topic="Continue",
        instructions="",
        continuation_source={
            "intent_override": "revise_in_place",
            "context": {"story": "They closed the door and smiled at the dawn. The end."},
        },
    )

    assert resolution is not None
    assert resolution.intent == ContinuationIntent.revise_in_place
    assert resolution.signals == ["user_intent_override"]


def test_improve_request_resolves_to_revise_in_place():
    resolution = infer_continuation_intent(
        topic="Essay",
        instructions="Improve the style but do not add a new essay.",
        continuation_source={"context": {"body": "Existing essay."}},
    )

    assert resolution is not None
    assert resolution.intent == ContinuationIntent.revise_in_place


def test_reference_request_resolves_to_update_references_only():
    resolution = infer_continuation_intent(
        topic="Coursework",
        instructions="Add bibliography sources only.",
        continuation_source={"context": {"analysis": "Existing body."}},
    )

    assert resolution is not None
    assert resolution.intent == ContinuationIntent.update_references_only


def test_source_style_request_does_not_resolve_to_references_only():
    resolution = infer_continuation_intent(
        topic="Continue",
        instructions="Preserve source style and continue.",
        continuation_source={"context": {"body": "Existing body without a hard ending"}},
    )

    assert resolution is not None
    assert resolution.intent == ContinuationIntent.continue_append


def test_detect_terminal_sections_from_context_and_runtime_template():
    source = {
        "context": {
            "analysis": "Body content.",
            "references": "1. Existing source.",
            "appendix_a": "Raw data.",
        },
        "runtime_template": {
            "sections": [
                {"name": "analysis", "title": "Analysis", "semantic_role": "academic_section"},
                {"name": "references", "title": "References", "semantic_role": "reference_section"},
                {"name": "appendix_a", "title": "Appendix A", "semantic_role": "appendix"},
            ]
        },
    }

    assert detect_terminal_sections(source) == ["references", "appendix_a"]
