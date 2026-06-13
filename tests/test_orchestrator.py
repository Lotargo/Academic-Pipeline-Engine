from academic_pe.core.orchestrator import Orchestrator, PipelineState, InvalidTransitionError, PipelineError, create_orchestrator_from_config
from academic_pe.core.config import AppConfig, AgentConfig, PipelineConfig, QualityGateConfig, VolumeGateConfig, LatexGateConfig, SectionPrompt, TemplateMode, LanguagePolicy
from academic_pe.core.llm import MockProvider
from academic_pe.agents.base import DefaultAgent
from academic_pe.core.template_library import TemplateLibrary
from academic_pe.core.template_selector import TemplateSelector
from academic_pe.core.templates import DocumentTemplate, PromptManifest, RuntimePromptManifest, RuntimeTemplate, RuntimeTemplateSource, TemplateSection
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

    def fake_renderer(content, output_filename, config=None):
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


def test_pipeline_renderer_uses_title_for_default_filename(tmp_path):
    config = _make_config()
    config.pipeline.output_dir = str(tmp_path)
    config.pipeline.title = 'Количественный анализ: A/B "C"'
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)

    seen: Dict[str, str] = {}

    def fake_renderer(content, output_filename, config=None):
        seen["output_filename"] = output_filename
        return output_filename

    orch = Orchestrator(
        writer=writer,
        config=config,
        renderer=fake_renderer,
    )

    result = orch.run_pipeline()

    assert result == str(tmp_path / "Количественный анализ - A-B C.docx")
    assert seen["output_filename"] == result


def test_pipeline_renderer_uses_user_topic_when_title_is_default_placeholder(tmp_path):
    config = _make_config()
    config.pipeline.output_dir = str(tmp_path)
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)

    def fake_renderer(content, output_filename, config=None):
        return output_filename

    orch = Orchestrator(
        writer=writer,
        config=config,
        renderer=fake_renderer,
    )
    orch.user_topic = "Direct Pipeline Topic"

    result = orch.run_pipeline()

    assert result == str(tmp_path / "Direct Pipeline Topic.docx")


def test_create_orchestrator_from_config_applies_fixed_template_and_manifest():
    library = TemplateLibrary([
        DocumentTemplate(
            id="technical_note",
            name="Technical Note",
            category="technical",
            sections=[
                TemplateSection(
                    name="problem",
                    title="Problem",
                    instruction="Define the problem.",
                )
            ],
            prompt_manifest=PromptManifest(
                writer_role="Technical writer",
                reviewer_role="Technical reviewer",
                writer_task="Write a concise technical note.",
            ),
        )
    ])
    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer",
                model="mock",
                temperature=0.0,
                system_prompt="Base writer prompt.",
            )
        },
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="theory", topic="Theory", instruction="Explain."),
            ],
            template_mode=TemplateMode.fixed,
            template_id="technical_note",
        ),
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )

    orch = create_orchestrator_from_config(
        config,
        template_selector=TemplateSelector(library=library),
    )

    assert [section.name for section in orch._config.pipeline.sections] == ["problem"]
    assert orch.runtime_template is not None
    assert orch.runtime_template.source_template_id == "technical_note"
    assert "Role for this document template: Technical writer" in orch._writer.config.system_prompt
    assert "Write a concise technical note." in orch._writer.config.system_prompt


def test_create_orchestrator_from_config_keeps_custom_sections():
    config = _make_config()

    orch = create_orchestrator_from_config(config)

    assert [section.name for section in orch._config.pipeline.sections] == [
        "theory",
        "calculation",
        "conclusion",
    ]
    assert orch.runtime_template is not None
    assert orch.runtime_template.source_template_id == "custom_current"


def test_create_orchestrator_from_config_applies_auto_planner_output():
    class FakePlanner:
        def plan(self, topic: str, instructions: str = ""):
            template = DocumentTemplate(
                id="runtime_poem",
                name="Runtime Poem",
                category="creative",
                sections=[
                    TemplateSection(
                        name="poem",
                        title="Poem",
                        instruction="Write stanza-oriented poetry.",
                    )
                ],
                prompt_manifest=PromptManifest(
                    writer_role="Poet",
                    reviewer_role="Poetry reviewer",
                    writer_task=f"Write about {topic}.",
                ),
            )
            runtime_template = RuntimeTemplate.from_document_template(template)
            runtime_template.source = RuntimeTemplateSource.auto
            runtime_template.source_template_id = None
            runtime_manifest = RuntimePromptManifest.from_document_template(template)
            runtime_manifest.source = RuntimeTemplateSource.auto
            runtime_manifest.source_template_id = None
            return runtime_template, runtime_manifest

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer",
                model="mock",
                temperature=0.0,
                system_prompt="Base writer prompt.",
            )
        },
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="theory", topic="Theory", instruction="Explain."),
            ],
            template_mode=TemplateMode.auto,
        ),
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )

    orch = create_orchestrator_from_config(
        config,
        template_selector=TemplateSelector(planner=FakePlanner()),
        user_topic="daisies",
    )

    assert [section.name for section in orch._config.pipeline.sections] == ["poem"]
    assert orch.runtime_template is not None
    assert orch.runtime_template.source == RuntimeTemplateSource.auto
    assert "Role for this document template: Poet" in orch._writer.config.system_prompt
    assert "Write about daisies." in orch._writer.config.system_prompt


def test_auto_language_uses_user_prompt_language_for_drafting():
    config = _make_config()
    config.pipeline.language = LanguagePolicy.auto

    class CapturingProvider(MockProvider):
        def __init__(self):
            self.prompts = []

        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
            self.prompts.append(user_prompt)
            return "APPROVED" if "Check the provided text" in user_prompt else "English draft content for the section."

    llm = CapturingProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    orch.user_topic = "AI Agent Design Principles"
    orch.run_pipeline(render_artifact=False)

    assert any("Write the entire document in English." in prompt for prompt in llm.prompts)
    assert not any("Write the entire document in Russian." in prompt for prompt in llm.prompts)


def test_auto_language_detects_russian_user_prompt():
    config = _make_config()
    config.pipeline.language = LanguagePolicy.auto

    class CapturingProvider(MockProvider):
        def __init__(self):
            self.prompts = []

        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
            self.prompts.append(user_prompt)
            return "Текст раздела на русском языке."

    llm = CapturingProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    orch.user_topic = "Принципы проектирования AI агентов"
    orch.run_pipeline(render_artifact=False)

    assert any("Write the entire document in Russian." in prompt for prompt in llm.prompts)


def test_auto_language_uses_explicit_language_request_over_prompt_language():
    config = _make_config()
    config.pipeline.language = LanguagePolicy.auto

    class CapturingProvider(MockProvider):
        def __init__(self):
            self.prompts = []

        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
            self.prompts.append(user_prompt)
            return "English draft content for the section."

    llm = CapturingProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    orch.user_topic = "Реферат про бабочек для 3 класса"
    orch.user_instructions = "Написать текст на английском языке."
    orch.run_pipeline(render_artifact=False)

    assert any("Write the entire document in English." in prompt for prompt in llm.prompts)
    assert not any("Write the entire document in Russian." in prompt for prompt in llm.prompts)


def test_auto_language_supports_explicit_chinese_request():
    config = _make_config()
    config.pipeline.language = LanguagePolicy.auto

    class CapturingProvider(MockProvider):
        def __init__(self):
            self.prompts = []

        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
            self.prompts.append(user_prompt)
            return "中文内容。"

    llm = CapturingProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    orch.user_topic = "Реферат про бабочек для 3 класса"
    orch.user_instructions = "Написать на китайском."
    orch.run_pipeline(render_artifact=False)

    assert any("Write the entire document in Chinese." in prompt for prompt in llm.prompts)


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
        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
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
        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
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


def test_self_verification_workflow():
    from academic_pe.agents.writer import WriterAgent, ReviewerAgent
    from academic_pe.core.config import QualityGateConfig, VolumeGateConfig, LatexGateConfig
    
    # Mock LLM provider that controls the flow
    class FlowMockProvider(MockProvider):
        def __init__(self):
            self.review_calls = 0
            self.writer_calls = 0
            self.verify_calls = 0
            
        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            # If called for review
            if "Check the provided text for material academic quality issues" in user_prompt:
                self.review_calls += 1
                if self.review_calls == 1:
                    return "REJECTED: contains chinese symbols like 纯洁"
                return "APPROVED"
                
            # If called for verification/writing
            if "Your task is to verify if the text of section" in user_prompt:
                self.verify_calls += 1
                if self.verify_calls == 1:
                    # First verify fails, returns corrected text
                    return "Corrected section text without chinese characters."
                # Second verify passes
                return "VERIFIED"
                
            self.writer_calls += 1
            # Normal drafting/revision response
            if "Revise the section" in user_prompt or "minimal patch" in user_prompt:
                return "Corrected draft section."
            return "Initial draft section."

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="Writer prompt.",
            ),
            "reviewer": AgentConfig(
                role="Reviewer", model="mock", temperature=0.0,
                system_prompt="Reviewer prompt.",
            ),
        },
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )
    
    llm = FlowMockProvider()
    writer = WriterAgent(config.agents["writer"], llm)
    reviewer = ReviewerAgent(config.agents["reviewer"], llm)
    
    orch = Orchestrator(writer=writer, reviewer=reviewer, config=config)
    
    result = orch.run_pipeline(render_artifact=False)
    
    assert orch.state == PipelineState.DONE
    # Verify first rejection was captured
    assert orch.first_attempt_reason == "contains chinese symbols like 纯洁"
    # Verify review was called twice (first rejects, second approves after revision/verification)
    assert llm.review_calls == 2
    # Verify self-verification was called
    assert llm.verify_calls > 0
    # The final context of sections should be corrected
    assert "theory" in orch.context
    assert orch.context["theory"] == "Corrected section text without chinese characters."


def test_parse_rejection_reasons():
    from academic_pe.core.orchestrator import parse_rejection_reasons
    from academic_pe.core.config import SectionPrompt

    sections = [
        SectionPrompt(name="theory", topic="State Machines", instruction=""),
        SectionPrompt(name="calculation", topic="Algorithmic Complexity", instruction=""),
    ]

    reason_text = """REJECTED
    - [theory]: line 10: spelling error in machine definition
    - Algorithmic Complexity: line 15: complexity claims do not match
    - [general]: the overall formatting should be improved
    """

    res = parse_rejection_reasons(reason_text, sections)
    
    # "theory" should have its specific reason and the general reason
    assert "spelling error in machine definition" in res["theory"]
    assert "the overall formatting should be improved" in res["theory"]
    
    # "calculation" should have its specific reason and the general reason (matched by topic)
    assert "complexity claims do not match" in res["calculation"]
    assert "the overall formatting should be improved" in res["calculation"]


def test_document_memory_includes_subsequent_sections():
    config = _make_config()
    # Modify config to have two sections
    config.pipeline.sections = [
        SectionPrompt(name="theory", topic="State Machines", instruction=""),
        SectionPrompt(name="calculation", topic="Algorithmic Complexity", instruction=""),
    ]
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(writer=writer, config=config)
    orch.context = {
        "theory": "First section text.",
        "calculation": "Second section text.",
    }

    # memory for "theory" (first section)
    mem_theory = orch._document_memory(current_section_name="theory")
    assert "[Already Written Sections (After This Section)]" in mem_theory
    assert "## Algorithmic Complexity\nSecond section text." in mem_theory

    # memory for "calculation" (second section)
    mem_calc = orch._document_memory(current_section_name="calculation")
    assert "[Already Written Sections (Before This Section)]" in mem_calc
    assert "## State Machines\nFirst section text." in mem_calc


def test_reviewer_receives_line_numbers_and_section_headers():
    from academic_pe.agents.writer import WriterAgent, ReviewerAgent
    
    # Mock LLM provider to capture system_prompt and user_prompt
    class ReviewCaptureMock(MockProvider):
        def __init__(self):
            self.review_context = None

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            if "[Text to Review]" in system_prompt:
                self.review_context = system_prompt
                return "APPROVED"
            return "Section content."

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="Writer prompt.",
            ),
            "reviewer": AgentConfig(
                role="Reviewer", model="mock", temperature=0.0,
                system_prompt="Reviewer prompt.",
            ),
        },
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )
    
    llm = ReviewCaptureMock()
    writer = WriterAgent(config.agents["writer"], llm)
    reviewer = ReviewerAgent(config.agents["reviewer"], llm)
    
    orch = Orchestrator(writer=writer, reviewer=reviewer, config=config)
    orch.run_pipeline(render_artifact=False)
    
    assert llm.review_context is not None
    assert "=== Section: theory ===" in llm.review_context
    assert "1: Section content." in llm.review_context


def test_should_preserve_topic():
    from academic_pe.core.orchestrator import should_preserve_topic
    assert should_preserve_topic("Do not change topic") is True
    assert should_preserve_topic("do not rename the topic please") is True
    assert should_preserve_topic("Use latex and formulas") is False
    assert should_preserve_topic("") is False


def test_rewrite_document_topic_preserves_on_constraint():
    from academic_pe.core.orchestrator import rewrite_document_topic
    
    class FakeWriter(DefaultAgent):
        def process(self, task_description, context=None, on_delta=None, document_sections=None):
            return "Refined Title"

    writer = FakeWriter(AgentConfig(role="Writer", model="mock", temperature=0.0, system_prompt=""), MockProvider())
    
    # constraint present
    res = rewrite_document_topic("FSM", "do not rename", writer)
    assert res == "FSM"


def test_rewrite_document_topic_refines_title():
    from academic_pe.core.orchestrator import rewrite_document_topic
    
    class FakeWriter(DefaultAgent):
        def process(self, task_description, context=None, on_delta=None, document_sections=None):
            return "Advanced FSM Design Pattern"

    writer = FakeWriter(AgentConfig(role="Writer", model="mock", temperature=0.0, system_prompt=""), MockProvider())
    
    # no constraint present
    res = rewrite_document_topic("FSM", "Use latex", writer)
    assert res == "Advanced FSM Design Pattern"


def test_create_orchestrator_from_config_does_not_refine_topic_for_mock_provider():
    config = _make_config()
    # provider is mock by default
    orch = create_orchestrator_from_config(config, user_topic="FSM", user_instructions="Use latex")
    assert orch.user_topic == "FSM"


def test_continuation_source_is_included_in_planning_context():
    config = _make_config()

    class CapturingProvider(MockProvider):
        def __init__(self):
            self.prompts = []

        def generate(self, system_prompt: str, user_prompt: str, model: str, temperature: float, on_delta=None) -> str:
            self.prompts.append(user_prompt)
            return "APPROVED" if "Check the provided text" in user_prompt else "Generated section content."

    llm = CapturingProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    orch = Orchestrator(
        writer=writer,
        config=config,
        continuation_source={
            "source_type": "generated",
            "topic": "Existing Work",
            "context": {
                "intro": "Existing introduction.",
                "conclusion": "Existing final summary.",
            },
            "document_plan": "Existing plan.",
        },
    )
    orch.user_topic = "Existing Work"
    orch.user_instructions = "Extend with a new case study."

    orch.run_pipeline(render_artifact=False)

    planning_prompt = llm.prompts[0]
    assert "[Continuation Source]" in planning_prompt
    assert "Previous document topic/title: Existing Work" in planning_prompt
    assert "Existing final summary." in planning_prompt
    assert "Plan one coherent revised/continued document" in planning_prompt


def test_strip_markdown_fences():
    from academic_pe.core.orchestrator import strip_markdown_fences
    
    # Strict wrapped
    assert strip_markdown_fences("```markdown\nHello\n```") == "Hello"
    assert strip_markdown_fences("```\nHello\n```") == "Hello"
    
    # Wrapped with language info and whitespace
    assert strip_markdown_fences("   ```latex\nHello\n```   ") == "Hello"
    
    # Single code block inside text
    assert strip_markdown_fences("Intro\n```\nContent text here\n```") == "Content text here"
    
    # Normal text remains same
    assert strip_markdown_fences("Normal paragraph.") == "Normal paragraph."


def test_quality_gate_automated_rejection_in_loop():
    from academic_pe.agents.writer import WriterAgent, ReviewerAgent
    
    # Mock LLM provider that starts with a code block, quality gate triggers auto-rejection,
    # then next turn it returns clean text which gets approved.
    class QualityGateTestMock(MockProvider):
        def __init__(self):
            self.draft_calls = 0
            self.review_calls = 0

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            if "Check the provided text for material academic quality issues" in user_prompt:
                self.review_calls += 1
                return "APPROVED" # LLM reviewer is lenient and approves

            if "verify" in user_prompt.lower():
                return "VERIFIED"

            # Writer calls
            if "Revise the section" in user_prompt or "minimal patch" in user_prompt:
                self.draft_calls += 1
                if "Quality Gate issue" in user_prompt:
                    # Clean up code fence because of quality gate rejection
                    return "Clean section content."
                return "Some prefix text\n```markdown\nSection with code block.\n```"

            return "Some prefix text\n```markdown\nSection with code block.\n```"

    config = AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="Writer prompt.",
            ),
            "reviewer": AgentConfig(
                role="Reviewer", model="mock", temperature=0.0,
                system_prompt="Reviewer prompt.",
            ),
        },
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
        ),
    )
    
    llm = QualityGateTestMock()
    writer = WriterAgent(config.agents["writer"], llm)
    reviewer = ReviewerAgent(config.agents["reviewer"], llm)
    
    orch = Orchestrator(writer=writer, reviewer=reviewer, config=config)
    # Put raw backticks in context so Quality Gate fails initially
    orch.context = {"theory": "```markdown\nSection with code block.\n```"}
    
    # Run the pipeline
    result = orch.run_pipeline(render_artifact=False)
    
    assert orch.state == PipelineState.DONE
    # LLM reviewer should NOT be called during the first iteration because Quality Gate rejected it programmatically
    # But after revision to "Clean section content." Quality Gate passes, and LLM reviewer is called and approves.
    assert llm.review_calls == 1
    assert orch.context["theory"] == "Clean section content."
