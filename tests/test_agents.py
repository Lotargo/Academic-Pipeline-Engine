from academic_pe.agents.base import BaseAgent, DefaultAgent
from academic_pe.agents.factory import create_agent, register_agent_type, _AGENT_TYPES
from academic_pe.core.config import AgentConfig
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
