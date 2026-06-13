from academic_pe.api_models import RunRequest


def test_run_request_accepts_template_selection_fields():
    payload = RunRequest(
        topic="Finite state machines",
        instructions="Keep it concise.",
        template_mode="fixed",
        template_id="technical_note",
        author="Lotargo",
    )

    assert payload.template_mode == "fixed"
    assert payload.template_id == "technical_note"
    assert payload.author == "Lotargo"


def test_run_request_template_selection_fields_are_optional():
    payload = RunRequest(topic="Finite state machines")

    assert payload.template_mode is None
    assert payload.template_id is None
    assert payload.author is None


def test_run_request_accepts_continuation_source():
    payload = RunRequest(
        topic="AI Agent Design",
        instructions="Extend with deployment risks.",
        continuation_source={
            "source_type": "generated",
            "topic": "AI Agent Design",
            "context": {
                "intro": "Existing introduction.",
                "conclusion": "Existing final summary.",
            },
            "document_plan": "Existing plan.",
            "metadata_id": "paper.metadata.json",
            "run_id": "run_20260613_120000",
        },
    )

    assert payload.continuation_source is not None
    assert payload.continuation_source.topic == "AI Agent Design"
    assert payload.continuation_source.context["conclusion"] == "Existing final summary."
