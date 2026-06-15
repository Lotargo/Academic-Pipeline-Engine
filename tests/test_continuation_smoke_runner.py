from pathlib import Path

from scripts.continuation_smoke_runner import (
    align_config_sections_to_continuation_source,
    configured_real_providers,
    config_snapshot,
    disable_expensive_smoke_loops,
    safe_stage_message,
    scenario_catalog,
    safe_config_for_smoke,
    safe_error_message,
    run_checks,
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


def test_academic_references_fixture_avoids_section_self_headings():
    context = scenario_catalog()["academic_references"].continuation_source["context"]

    assert "## 1. Introduction" not in context["introduction"]
    assert "## References" not in context["references"]


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


def test_disable_expensive_smoke_loops_turns_off_self_critique_and_retry():
    config = _config(ProviderEnum.zen)
    config.agents["writer"].self_critique.enabled = True

    smoke = disable_expensive_smoke_loops(config)

    assert smoke.retry.max_retries == 0
    assert smoke.agents["writer"].self_critique.enabled is False
    assert config.agents["writer"].self_critique.enabled is True


def test_safe_error_message_redacts_auth_like_text():
    assert safe_error_message(RuntimeError("Authorization: Bearer abc")) == "[redacted]"


def test_align_config_sections_to_continuation_source_uses_scenario_context():
    config = _config()
    scenario = scenario_catalog()["technical_continuation"]

    smoke = align_config_sections_to_continuation_source(config, scenario)

    assert [section.name for section in smoke.pipeline.sections] == ["readme"]
    assert smoke.pipeline.template_mode == TemplateMode.custom
    assert [section.name for section in config.pipeline.sections] == ["body"]


def test_run_checks_fails_when_final_reviewer_retry_rejected():
    scenario = scenario_catalog()["school_revision"]

    passed, issues = run_checks(
        scenario,
        {"essay": "Improved essay content that is long enough. " * 8},
        {"continuation_intent": {"intent": "revise_in_place"}, "edit_plan": {"operations": []}},
        [{"kind": "stage_log", "message": "Reviewer rejected (attempt 3/3): [content redacted]"}],
    )

    assert passed is False
    assert "reviewer rejected the final retry" in issues[0]
