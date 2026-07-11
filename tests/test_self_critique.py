from academic_pe.agents.self_critique import run_self_critique
from academic_pe.core.config import AgentConfig, SelfCritiqueConfig
from academic_pe.core.llm import LLMProvider


class StaticCritiqueProvider(LLMProvider):
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
            }
        )
        return self.response


def _config() -> AgentConfig:
    return AgentConfig(
        role="Writer",
        model="mock",
        temperature=0.7,
        system_prompt="Writer prompt.",
        self_critique=SelfCritiqueConfig(enabled=True, temperature=0.1),
    )


def test_self_critique_repairs_output_from_json_response():
    provider = StaticCritiqueProvider(
        '{"summary":"Removed AI wrapper.","patches":[{"old":"Sure, here is the final artifact: ","new":""}]}'
    )

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Write the final artifact.",
        draft_output="Sure, here is the final artifact: Final artifact text.",
        system_prompt="Contract prompt.",
    )

    assert result.output == "Final artifact text."
    assert result.summary == "Removed AI wrapper."
    assert result.changed is True
    assert provider.calls[0]["temperature"] == 0.1
    assert "Do not return REJECTED" in provider.calls[0]["system_prompt"]
    assert "exact unique text" in provider.calls[0]["system_prompt"]


def test_writer_self_critique_rejects_ambiguous_patch_and_preserves_draft():
    provider = StaticCritiqueProvider(
        '{"summary":"Changed repeated text.","patches":[{"old":"same","new":"other"}]}'
    )

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Write the final artifact.",
        draft_output="same and same",
        system_prompt="Contract prompt.",
    )

    assert result.output == "same and same"
    assert result.skipped_reason == "invalid_exact_patch"


def test_writer_self_critique_empty_patch_list_preserves_draft():
    provider = StaticCritiqueProvider('{"summary":"No repair needed.","patches":[]}')

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Write the final artifact.",
        draft_output="Already correct.",
        system_prompt="Contract prompt.",
    )

    assert result.output == "Already correct."
    assert result.changed is False


def test_writer_self_critique_receives_only_active_contract_sections():
    provider = StaticCritiqueProvider('{"summary":"No repair needed.","patches":[]}')

    run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Write the final artifact.",
        draft_output="Already correct.",
        system_prompt=(
            "PRIVATE BASE SYSTEM GUIDANCE\n\n"
            "[Active Artifact Contract]\n(document (artifact report))\n\n"
            "[Active Agent Contract]\n(agent_contract_delta (agent writer))"
        ),
        context="FULL DOCUMENT CONTEXT MUST NOT BE REPEATED",
    )

    prompt = provider.calls[0]["user_prompt"]
    assert "(artifact report)" in prompt
    assert "agent_contract_delta" in prompt
    assert "PRIVATE BASE SYSTEM GUIDANCE" not in prompt
    assert "FULL DOCUMENT CONTEXT MUST NOT BE REPEATED" not in prompt
    assert "[Active System Prompt And Contract]" not in prompt


def test_self_critique_invalid_response_keeps_original_output():
    provider = StaticCritiqueProvider("not json")

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Task",
        draft_output="Original text.",
        system_prompt="Prompt",
    )

    assert result.output == "Original text."
    assert result.skipped_reason == "invalid_response"


def test_self_critique_blocking_feedback_keeps_original_output():
    provider = StaticCritiqueProvider(
        '{"summary":"Found issue.","output":"REJECTED\\n- [general]: ask the user what to do"}'
    )

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Task",
        draft_output="Original text.",
        system_prompt="Prompt",
    )

    assert result.output == "Original text."
    assert result.skipped_reason == "blocking_feedback"


def test_self_critique_applies_researcher_rules():
    provider = StaticCritiqueProvider(
        '{"summary":"Fixed overreach.","output":"Clean findings."}'
    )

    run_self_critique(
        agent_name="researcher",
        config=_config(),
        llm=provider,
        task_description="Task",
        draft_output="Findings.",
        system_prompt="Contract prompt.",
    )

    assert "check source relevance" in provider.calls[0]["user_prompt"]
    assert "forcing citations" in provider.calls[0]["user_prompt"]


def test_self_critique_applies_exporter_rules():
    provider = StaticCritiqueProvider(
        '{"summary":"Fixed structure.","output":"Clean structure."}'
    )

    run_self_critique(
        agent_name="exporter",
        config=_config(),
        llm=provider,
        task_description="Task",
        draft_output="Structure.",
        system_prompt="Contract prompt.",
    )

    assert "format compatibility" in provider.calls[0]["user_prompt"]
    assert "headings, spacing" in provider.calls[0]["user_prompt"]


def test_self_critique_applies_academic_mode_rules():
    provider = StaticCritiqueProvider(
        '{"summary":"Fixed assumption.","output":"Rigorous text."}'
    )

    run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description="Task",
        draft_output="Draft.",
        system_prompt="academic_mode",
    )

    assert "unsupported claims" in provider.calls[0]["user_prompt"]
    assert "methodological clarity" in provider.calls[0]["user_prompt"]


def test_self_critique_preserves_valid_patch_when_repair_breaks_format():
    draft_patch = """<<<<<<< REPLACE 1-1
Corrected line.
>>>>>>>"""
    provider = StaticCritiqueProvider(
        '{"summary":"Rewrote patch as text.","output":"Corrected line."}'
    )

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description=(
            "Edit the current section by returning a minimal patch. "
            "If changes are needed, return one or more REPLACE blocks. "
            "If not, return NO_CHANGES."
        ),
        draft_output=draft_patch,
        system_prompt="Contract prompt.",
    )

    assert result.output == draft_patch
    assert result.skipped_reason == "invalid_patch_repair"
    assert "Preserve the machine-readable patch protocol" in provider.calls[0]["user_prompt"]


def test_self_critique_accepts_valid_patch_repair():
    provider = StaticCritiqueProvider(
        '{"summary":"Restored patch format.","output":"<<<<<<< REPLACE 1-1\\nCorrected line.\\n>>>>>>>"}'
    )

    result = run_self_critique(
        agent_name="writer",
        config=_config(),
        llm=provider,
        task_description=(
            "Edit the current section by returning a minimal patch. "
            "If changes are needed, return one or more REPLACE blocks. "
            "If not, return NO_CHANGES."
        ),
        draft_output="Corrected line.",
        system_prompt="Contract prompt.",
    )

    assert result.output == "<<<<<<< REPLACE 1-1\nCorrected line.\n>>>>>>>"
    assert result.summary == "Restored patch format."
