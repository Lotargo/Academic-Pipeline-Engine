from academic_pe.core.config import load_config


EXAMPLE_CONFIG = "config/agents.example.yaml"


def test_load_config():
    config = load_config(EXAMPLE_CONFIG)

    assert config is not None
    assert "writer" in config.agents
    assert "reviewer" in config.agents

    writer = config.agents["writer"]
    assert writer.role == "Writer"
    assert writer.temperature == 0.7
    assert writer.reasoning_effort == "medium"
    assert "expert artifact-aware writer" in writer.system_prompt
    assert "formal, impersonal academic style" not in writer.system_prompt

    assert len(config.pipeline.sections) == 3
    assert config.pipeline.sections[0].name == "theory"
    assert config.pipeline.sections[1].name == "calculation"
    assert config.pipeline.sections[2].name == "conclusion"

    assert config.retry.max_retries == 3
    assert config.retry.base_delay == 1.0
    assert config.retry.max_delay == 30.0
    assert config.quality_gate.calculation.enabled is True
    assert config.quality_gate.calculation.tolerance == 1e-6


def test_config_has_circuit_breaker():
    config = load_config(EXAMPLE_CONFIG)
    assert config.circuit_breaker.enabled is False
    assert config.circuit_breaker.failure_threshold == 5
    assert config.circuit_breaker.recovery_timeout == 30.0


def test_config_has_output_fields():
    config = load_config(EXAMPLE_CONFIG)
    assert config.pipeline.output_filename == "Final_Academic_Paper.docx"
    assert config.pipeline.output_dir == "exports"


def test_config_agent_type_optional():
    config = load_config(EXAMPLE_CONFIG)
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
    assert cfg.export_qa.enabled is True
    assert cfg.export_qa.auto_repair_enabled is False
    assert cfg.export_qa.warnings_log_enabled is True
    assert cfg.export_qa.provider == "zen"
    assert cfg.export_qa.model == "mimo-v2.5-free"
    assert cfg.export_qa.temperature == 0.1
    assert cfg.agents["test"].self_critique.enabled is False
    assert cfg.agents["test"].self_critique.temperature is None
    assert cfg.agents["test"].reasoning_effort is None


def test_config_has_template_selection_fields():
    from academic_pe.core.config import TemplateMode
    config = load_config(EXAMPLE_CONFIG)

    assert isinstance(config.pipeline.template_mode, TemplateMode)
    assert config.pipeline.template_id is None or isinstance(config.pipeline.template_id, str)


def test_config_prompts_are_artifact_aware():
    config = load_config(EXAMPLE_CONFIG)

    planner_prompt = config.agents["planner"].system_prompt
    example_prompt = config.agents["example_generator"].system_prompt

    assert "artifact-aware template planner" in planner_prompt
    assert "artifact requests" in example_prompt
    assert "Academic Document template planner" not in planner_prompt
    assert "academic research topics" not in example_prompt
