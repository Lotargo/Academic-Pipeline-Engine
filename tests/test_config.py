from src.core.config import load_config

def test_load_config():
    """
    Verifies that the YAML configuration is correctly loaded and validated by Pydantic.
    """
    config = load_config("config/agents.yaml")

    assert config is not None
    assert "writer" in config.agents
    assert "reviewer" in config.agents

    writer = config.agents["writer"]
    assert writer.role == "Writer"
    assert writer.temperature == 0.7
    assert "expert academic writer" in writer.system_prompt
