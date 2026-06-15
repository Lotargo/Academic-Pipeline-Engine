from pathlib import Path

from scripts.continuation_smoke_runner import (
    configured_real_providers,
    config_snapshot,
    safe_stage_message,
    scenario_catalog,
    safe_config_for_smoke,
)
from academic_pe.core.config import AppConfig, AgentConfig, PipelineConfig, ProviderEnum, SectionPrompt, TemplateMode


def _config(provider: ProviderEnum = ProviderEnum.mock) -> AppConfig:
    return AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer",
                provider=provider,
                model="test-model",
                temperature=0.1,
                system_prompt="write",
            ),
            "reviewer": AgentConfig(
                role="Reviewer",
                provider=ProviderEnum.mock,
                model="review-model",
                temperature=0.1,
                system_prompt="review",
            ),
        },
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="body", topic="Body", instruction="Draft body."),
            ],
            template_mode=TemplateMode.auto,
            academic_mode=True,
        ),
    )


def test_scenario_catalog_contains_required_single_run_scenarios():
    scenarios = scenario_catalog()

    assert set(scenarios) == {
        "creative_continuation",
        "creative_bridge",
        "school_revision",
        "academic_references",
        "technical_continuation",
    }
    assert scenarios["academic_references"].continuation_source["context"]["references"]


def test_config_snapshot_records_provider_and_model_only():
    snapshot = config_snapshot(_config(ProviderEnum.zen))

    assert "writer=zen/test-model" in snapshot
    assert "reviewer=mock/review-model" in snapshot
    assert "key" not in snapshot.lower()
    assert "secret" not in snapshot.lower()


def test_configured_real_providers_excludes_mock_and_deduplicates():
    assert configured_real_providers(_config(ProviderEnum.zen)) == ["zen"]
    assert configured_real_providers(_config(ProviderEnum.mock)) == []


def test_safe_config_for_smoke_keeps_run_bounded_without_mutating_source(tmp_path: Path):
    config = _config()
    smoke = safe_config_for_smoke(config, tmp_path)

    assert smoke.pipeline.output_dir == str(tmp_path)
    assert smoke.pipeline.template_mode == TemplateMode.custom
    assert smoke.pipeline.academic_mode is False
    assert smoke.retry.max_retries <= 1
    assert config.pipeline.template_mode == TemplateMode.auto
    assert config.pipeline.academic_mode is True


def test_safe_stage_message_redacts_generated_content():
    message = (
        "Reviewer rejected (attempt 1/3): # Generated Section\n\n"
        "This is generated document text.\n\nSystem prompt used: secret-looking prompt"
    )

    sanitized = safe_stage_message(message)

    assert "generated document text" not in sanitized
    assert "secret-looking prompt" not in sanitized
    assert "content redacted" in sanitized
