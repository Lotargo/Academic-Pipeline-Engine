from src.core.config import load_config


def test_load_config():
    config = load_config("config/agents.yaml")

    assert config is not None
    assert "writer" in config.agents
    assert "reviewer" in config.agents

    writer = config.agents["writer"]
    assert writer.role == "Writer"
    assert writer.temperature == 0.7
    assert "expert academic writer" in writer.system_prompt

    assert len(config.pipeline.sections) == 3
    assert config.pipeline.sections[0].name == "theory"
    assert config.pipeline.sections[1].name == "calculation"
    assert config.pipeline.sections[2].name == "conclusion"
