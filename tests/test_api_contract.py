from academic_pe.api_models import RunRequest


def test_run_request_accepts_template_selection_fields():
    payload = RunRequest(
        topic="Finite state machines",
        instructions="Keep it concise.",
        template_mode="fixed",
        template_id="technical_note",
    )

    assert payload.template_mode == "fixed"
    assert payload.template_id == "technical_note"


def test_run_request_template_selection_fields_are_optional():
    payload = RunRequest(topic="Finite state machines")

    assert payload.template_mode is None
    assert payload.template_id is None
