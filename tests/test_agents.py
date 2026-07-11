from academic_pe.agents.base import BaseAgent, DefaultAgent
from academic_pe.agents.factory import create_agent, register_agent_type, _AGENT_TYPES
from academic_pe.core.config import AgentConfig, SelfCritiqueConfig
from academic_pe.core.llm import MockProvider


def test_agent_process():
    cfg = AgentConfig(
        role="Tester",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="You are a test agent.",
    )
    llm = MockProvider()
    agent = DefaultAgent(cfg, llm)

    result = agent.process("Perform a test task")

    assert result is not None
    assert isinstance(result, str)
    assert "mock response" in result.lower()


def test_agent_process_with_context():
    cfg = AgentConfig(
        role="Tester",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="Base Prompt",
    )
    llm = MockProvider()
    agent = DefaultAgent(cfg, llm)

    result = agent.process("Task", context="Important Context")

    assert result is not None
    assert "Important Context" in result or "Base Prompt" in result


def test_base_agent_is_abstract():
    import abc
    assert bool(getattr(BaseAgent, "__abstractmethods__", None))


def test_default_agent_is_not_abstract():
    assert not bool(getattr(DefaultAgent, "__abstractmethods__", None))


class TestAgentFactory:
    def test_create_default_agent(self):
        cfg = AgentConfig(
            role="Test", model="m", temperature=0.0,
            system_prompt="test",
        )
        agent = create_agent("unknown_name", cfg)
        assert isinstance(agent, DefaultAgent)

    def test_create_writer_by_name(self):
        from academic_pe.agents.writer import WriterAgent
        cfg = AgentConfig(
            role="Writer", model="m", temperature=0.0,
            system_prompt="test",
        )
        agent = create_agent("writer", cfg)
        assert isinstance(agent, WriterAgent)

    def test_create_reviewer_by_name(self):
        from academic_pe.agents.writer import ReviewerAgent
        cfg = AgentConfig(
            role="Reviewer", model="m", temperature=0.0,
            system_prompt="test",
        )
        agent = create_agent("reviewer", cfg)
        assert isinstance(agent, ReviewerAgent)

    def test_create_specialized_reviewers_by_name(self):
        from academic_pe.agents.factory import create_agent
        from academic_pe.agents.writer import ReviewerAgent

        config = AgentConfig(role="EvidenceReviewer", provider="mock", model="mock", temperature=0, system_prompt="Review evidence.")
        assert isinstance(create_agent("evidence_reviewer", config), ReviewerAgent)
        config = AgentConfig(role="EditorialReviewer", provider="mock", model="mock", temperature=0, system_prompt="Review prose.")
        assert isinstance(create_agent("editorial_reviewer", config), ReviewerAgent)

    def test_create_researcher_by_name(self):
        from academic_pe.agents.researcher import ResearcherAgent
        cfg = AgentConfig(
            role="Researcher", model="m", temperature=0.0,
            system_prompt="test",
        )
        agent = create_agent("researcher", cfg)
        assert isinstance(agent, ResearcherAgent)

    def test_create_with_explicit_agent_type(self):
        from academic_pe.agents.writer import WriterAgent
        cfg = AgentConfig(
            role="Custom", model="m", temperature=0.0,
            system_prompt="test",
            agent_type="writer",
        )
        agent = create_agent("anything", cfg)
        assert isinstance(agent, WriterAgent)

    def test_register_custom_type(self):
        class MyAgent(DefaultAgent):
            pass

        register_agent_type("my_custom", MyAgent)
        cfg = AgentConfig(
            role="Custom", model="m", temperature=0.0,
            system_prompt="test",
        )
        agent = create_agent("custom", cfg, agent_type="my_custom")
        assert isinstance(agent, MyAgent)

    def test_unknown_type_raises(self):
        cfg = AgentConfig(
            role="Test", model="m", temperature=0.0,
            system_prompt="test",
        )
        try:
            create_agent("test", cfg, agent_type="nonexistent")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "nonexistent" in str(e)


def test_writer_agent_grep_loop():
    from academic_pe.agents.writer import WriterAgent
    
    class GrepMockProvider(MockProvider):
        def __init__(self):
            self.calls = 0
            self.last_user_prompt = ""
            
        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls += 1
            self.last_user_prompt = user_prompt
            if self.calls == 1:
                return "USE_GREP: 纯洁"
            return "This is the final text without chinese characters."
            
    cfg = AgentConfig(
        role="Writer",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="You are a writer.",
    )
    llm = GrepMockProvider()
    agent = WriterAgent(cfg, llm)
    
    doc_sections = {
        "intro": "Введение с ромашкой.",
        "theory": "Теория с китайскими символами: 纯洁 и 种子.",
    }
    
    result = agent.process("Task description", document_sections=doc_sections)
    
    assert llm.calls == 2
    assert "Grep tool matches:" in llm.last_user_prompt
    assert "Section 'theory'" in llm.last_user_prompt
    assert "纯洁" in llm.last_user_prompt
    assert result == "This is the final text without chinese characters."


def test_writer_agent_self_critique_repairs_final_output():
    from academic_pe.agents.writer import WriterAgent

    class CritiqueMockProvider(MockProvider):
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
            if len(self.calls) == 1:
                return "Sure, here is the requested artifact: Clean text."
            return '{"summary":"Removed wrapper.","patches":[{"old":"Sure, here is the requested artifact: ","new":""}]}'

    cfg = AgentConfig(
        role="Writer",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="You are a writer.",
        self_critique=SelfCritiqueConfig(enabled=True),
    )
    llm = CritiqueMockProvider()
    agent = WriterAgent(cfg, llm)

    result = agent.process("Write final text.")

    assert result == "Clean text."
    assert agent.last_self_critique_summary == "Removed wrapper."
    assert len(llm.calls) == 2
    assert "[Draft Output]" in llm.calls[1]["user_prompt"]


def test_default_agent_researcher_self_critique_uses_research_rules():
    class ResearchCritiqueProvider(MockProvider):
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
            if len(self.calls) == 1:
                return "Findings with weak source relevance."
            return '{"summary":"Fixed source relevance.","output":"Clean relevant findings."}'

    cfg = AgentConfig(
        role="Source Researcher",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="Researcher prompt.",
        self_critique=SelfCritiqueConfig(enabled=True),
    )
    llm = ResearchCritiqueProvider()
    agent = DefaultAgent(cfg, llm)

    result = agent.process("Find sources.")

    assert result == "Clean relevant findings."
    assert agent.last_self_critique_summary == "Fixed source relevance."
    assert "Researcher self-critique" in llm.calls[1]["user_prompt"]
    assert "source relevance" in llm.calls[1]["user_prompt"]
    assert "evidence overreach" in llm.calls[1]["user_prompt"]


def test_default_agent_exporter_self_critique_uses_format_rules():
    class ExportCritiqueProvider(MockProvider):
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
            if len(self.calls) == 1:
                return "# Title Page\nDraft export structure."
            return '{"summary":"Removed title page.","output":"Clean export structure."}'

    cfg = AgentConfig(
        role="Document Exporter",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="Exporter prompt.",
        self_critique=SelfCritiqueConfig(enabled=True),
    )
    llm = ExportCritiqueProvider()
    agent = DefaultAgent(cfg, llm)

    result = agent.process("Prepare export.")

    assert result == "Clean export structure."
    assert agent.last_self_critique_summary == "Removed title page."
    assert "Exporter/renderer self-critique" in llm.calls[1]["user_prompt"]
    assert "format compatibility" in llm.calls[1]["user_prompt"]
    assert "without adding title pages" in llm.calls[1]["user_prompt"]
