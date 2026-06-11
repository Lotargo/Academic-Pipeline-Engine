from src.core.orchestrator import Orchestrator, PipelineState, InvalidTransitionError
from src.core.config import AppConfig, AgentConfig, SectionPrompt
from src.core.llm import MockProvider
from src.agents.base import BaseAgent
from typing import Dict


def _make_config() -> AppConfig:
    return AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="You are a writer.",
            ),
        },
    )


def test_initial_state():
    config = _make_config()
    llm = MockProvider()
    writer = BaseAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    assert orch.state == PipelineState.INIT


def test_transition_to_drafting():
    config = _make_config()
    llm = MockProvider()
    writer = BaseAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    orch.transition_to(PipelineState.DRAFTING)
    assert orch.state == PipelineState.DRAFTING


def test_invalid_transition_raises():
    config = _make_config()
    llm = MockProvider()
    writer = BaseAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    try:
        orch.transition_to(PipelineState.DONE)
        assert False, "Should have raised InvalidTransitionError"
    except InvalidTransitionError:
        pass


def test_full_pipeline_mock():
    config = _make_config()
    llm = MockProvider()
    writer = BaseAgent(config.agents["writer"], llm)

    outputs: Dict[str, str] = {}

    def fake_renderer(content, output_filename):
        outputs.update(content)
        return "test_output.docx"

    orch = Orchestrator(
        writer=writer,
        config=config,
        renderer=fake_renderer,
    )

    result = orch.run_pipeline()

    assert orch.state == PipelineState.DONE
    assert result == "test_output.docx"
    assert "theory" in orch.context
    assert "calculation" in orch.context
    assert "conclusion" in orch.context


def test_reviewer_loop_approves():
    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="You are a writer.",
            ),
            "reviewer": AgentConfig(
                role="Reviewer", model="mock", temperature=0.0,
                system_prompt="Always approve.",
            ),
        },
    )
    llm = MockProvider()
    writer = BaseAgent(config.agents["writer"], llm)
    reviewer = BaseAgent(config.agents["reviewer"], llm)
    orch = Orchestrator(writer=writer, reviewer=reviewer, config=config)

    result = orch.run_pipeline()

    assert orch.state == PipelineState.DONE
    assert result == "(no renderer configured)"


def test_reviewer_loop_rejected_then_approved():
    call_count = 0

    class ConditionalMock(MockProvider):
        def generate(self, system_prompt, user_prompt, model, temperature):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return "REJECTED: too informal"
            return "APPROVED"

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="You are a writer.",
            ),
            "reviewer": AgentConfig(
                role="Reviewer", model="mock", temperature=0.0,
                system_prompt="Reviewer.",
            ),
        },
    )
    llm = ConditionalMock()
    writer = BaseAgent(config.agents["writer"], llm)
    reviewer = BaseAgent(config.agents["reviewer"], llm)
    orch = Orchestrator(writer=writer, reviewer=reviewer, config=config)

    result = orch.run_pipeline()

    assert orch.state == PipelineState.DONE
    assert result == "(no renderer configured)"
