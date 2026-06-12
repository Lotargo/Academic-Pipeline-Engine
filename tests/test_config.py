from academic_pe.core.config import load_config


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

    assert config.retry.max_retries == 3
    assert config.retry.base_delay == 1.0
    assert config.retry.max_delay == 30.0


def test_config_has_circuit_breaker():
    config = load_config("config/agents.yaml")
    assert config.circuit_breaker.enabled is False
    assert config.circuit_breaker.failure_threshold == 5
    assert config.circuit_breaker.recovery_timeout == 30.0


def test_config_has_output_fields():
    config = load_config("config/agents.yaml")
    assert config.pipeline.output_filename == "Final_Academic_Paper.docx"
    assert config.pipeline.output_dir == "exports"


def test_config_agent_type_optional():
    config = load_config("config/agents.yaml")
    assert config.agents["writer"].agent_type is None


def test_config_defaults():
    from academic_pe.core.config import AppConfig, AgentConfig
    cfg = AppConfig(
        agents={
            "test": AgentConfig(
                role="Test", model="m", temperature=0.5,
                system_prompt="test",
            ),
        },
    )
    assert cfg.circuit_breaker.enabled is False
    assert cfg.fsm.enabled is False
    assert cfg.style.font_name == "Times New Roman"
    assert cfg.pipeline.output_filename == "Final_Academic_Paper.docx"
    assert cfg.pipeline.output_dir == "exports"
    assert cfg.pipeline.language == "auto"
    assert cfg.pipeline.template_mode == "custom"
    assert cfg.pipeline.template_id is None
    assert cfg.ui.language == "ru"


def test_config_has_template_selection_fields():
    from academic_pe.core.config import TemplateMode
    config = load_config("config/agents.yaml")

    assert isinstance(config.pipeline.template_mode, TemplateMode)
    assert config.pipeline.template_id is None or isinstance(config.pipeline.template_id, str)

