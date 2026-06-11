from src.agents.base import BaseAgent
from src.core.config import AgentConfig
from src.core.llm import MockProvider


def test_agent_process():
    cfg = AgentConfig(
        role="Tester",
        model="gpt-mock",
        temperature=0.0,
        system_prompt="You are a test agent.",
    )
    llm = MockProvider()
    agent = BaseAgent(cfg, llm)

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
    agent = BaseAgent(cfg, llm)

    result = agent.process("Task", context="Important Context")

    assert result is not None
    assert "Important Context" in result or "Base Prompt" in result
