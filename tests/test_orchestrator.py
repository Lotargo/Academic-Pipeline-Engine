from academic_pe.core.orchestrator import Orchestrator, PipelineState, InvalidTransitionError, PipelineError
from academic_pe.core.config import AppConfig, AgentConfig, QualityGateConfig, VolumeGateConfig, LatexGateConfig
from academic_pe.core.llm import MockProvider
from academic_pe.agents.base import DefaultAgent
from typing import Dict


def _make_config() -> AppConfig:
    return AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="You are a writer.",
            ),
        },
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )


def test_initial_state():
    config = _make_config()
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    assert orch.state == PipelineState.INIT


def test_transition_to_drafting():
    config = _make_config()
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    orch.transition_to(PipelineState.DRAFTING)
    assert orch.state == PipelineState.DRAFTING


def test_invalid_transition_raises():
    config = _make_config()
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    try:
        orch.transition_to(PipelineState.DONE)
        assert False, "Should have raised InvalidTransitionError"
    except InvalidTransitionError:
        pass


def test_full_pipeline_mock():
    config = _make_config()
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)

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
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    reviewer = DefaultAgent(config.agents["reviewer"], llm)
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
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )
    llm = ConditionalMock()
    writer = DefaultAgent(config.agents["writer"], llm)
    reviewer = DefaultAgent(config.agents["reviewer"], llm)
    orch = Orchestrator(writer=writer, reviewer=reviewer, config=config)

    result = orch.run_pipeline()

    assert orch.state == PipelineState.DONE
    assert result == "(no renderer configured)"


def test_pipeline_failure_transitions_to_failed():
    class FailingProvider(MockProvider):
        def generate(self, system_prompt, user_prompt, model, temperature):
            raise RuntimeError("LLM crashed")

    config = _make_config()
    llm = FailingProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)

    try:
        orch.run_pipeline()
        assert False, "Should have raised PipelineError"
    except PipelineError:
        assert orch.state == PipelineState.FAILED


class TestHooks:
    def test_on_enter_fires(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        entered = []
        orch.on_enter(lambda old, new: entered.append((old, new)))

        orch.transition_to(PipelineState.DRAFTING)
        assert len(entered) == 1
        assert entered[0] == (PipelineState.INIT, PipelineState.DRAFTING)

    def test_on_exit_fires(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        exited = []
        orch.on_exit(lambda old, new: exited.append((old, new)))

        orch.transition_to(PipelineState.DRAFTING)
        assert len(exited) == 1
        assert exited[0] == (PipelineState.INIT, PipelineState.DRAFTING)

    def test_hooks_fire_in_order(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        order = []
        orch.on_exit(lambda old, new: order.append("exit"))
        orch.on_enter(lambda old, new: order.append("enter"))

        orch.transition_to(PipelineState.DRAFTING)
        assert order == ["exit", "enter"]

    def test_multiple_hooks(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        calls = []
        orch.on_enter(lambda old, new: calls.append("a"))
        orch.on_enter(lambda old, new: calls.append("b"))

        orch.transition_to(PipelineState.DRAFTING)
        assert calls == ["a", "b"]


class TestRecovery:
    def test_previous_state_initially_none(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)
        assert orch.previous_state is None

    def test_revert_after_transition(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        orch.transition_to(PipelineState.DRAFTING)
        assert orch.state == PipelineState.DRAFTING
        assert orch.previous_state == PipelineState.INIT

        prev = orch.revert()
        assert orch.state == PipelineState.INIT
        assert prev == PipelineState.INIT

    def test_revert_empty_history_raises(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        try:
            orch.revert()
            assert False, "Should have raised PipelineError"
        except PipelineError:
            pass

    def test_multiple_reverts(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        orch.transition_to(PipelineState.DRAFTING)
        orch.transition_to(PipelineState.REVIEWING)
        assert orch.state == PipelineState.REVIEWING

        orch.revert()
        assert orch.state == PipelineState.DRAFTING

        orch.revert()
        assert orch.state == PipelineState.INIT

    def test_history_grows_with_transitions(self):
        config = _make_config()
        llm = MockProvider()
        writer = DefaultAgent(config.agents["writer"], llm)
        orch = Orchestrator(writer=writer, config=config)

        orch.transition_to(PipelineState.DRAFTING)
        orch.transition_to(PipelineState.REVIEWING)
        assert len(orch._state_history) == 2
