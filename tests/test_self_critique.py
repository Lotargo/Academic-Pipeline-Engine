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
        '{"summary":"Removed AI wrapper.","output":"Final artifact text."}'
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
