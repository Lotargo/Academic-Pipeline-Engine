import os
import json
import tempfile
import pytest
import shutil
from pathlib import Path
from datetime import datetime

from academic_pe.core.orchestrator import Orchestrator, create_orchestrator_from_config
from academic_pe.core.config import AppConfig, AgentConfig, PipelineConfig, SectionPrompt, QualityGateConfig, VolumeGateConfig, LatexGateConfig
from academic_pe.core.llm import MockProvider
from academic_pe.agents.base import DefaultAgent
from academic_pe.agents.researcher import ResearcherAgent
from academic_pe.core.registry import SQLiteRegistryStore, Source, Artifact, Evaluation, Run
from scripts.ocr_research_smoke_runner import run_scenario, SmokeScenario, SmokeResult, SmokeLog
from scripts.ocr_research_quality_eval_runner import run_scenario as run_quality_scenario, QualityScenario

@pytest.fixture
def temp_env():
    # Setup temporary directory for workspace
    temp_dir = tempfile.TemporaryDirectory()
    workspace_path = Path(temp_dir.name)
    
    # Setup database file
    db_path = workspace_path / "academic_pe_registry.sqlite3"
    registry_store = SQLiteRegistryStore(db_path=str(db_path))
    
    # Copy configuration files so the runners can load configuration
    shutil.copytree(str(Path("config").resolve()), str(workspace_path / "config"))
    
    yield workspace_path, registry_store
    
    temp_dir.cleanup()

def _make_config(output_dir: str) -> AppConfig:
    return AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="You are a writer.",
            ),
        },
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=True, min_chars=1),
            latex=LatexGateConfig(enabled=False),
        ),
        pipeline=PipelineConfig(
            output_dir=output_dir,
            sections=[
                SectionPrompt(name="theory", topic="Theory Topic", instruction="write theory"),
            ]
        )
    )

def test_continuation_and_reference_materials_registration(temp_env):
    workspace_path, store = temp_env
    output_dir = str(workspace_path / "run_123")
    config = _make_config(output_dir)
    
    # Setup mock continuation source and reference materials
    continuation_source = {
        "source_type": "uploaded",
        "topic": "Continuity Topic",
        "instructions": "Continue writing",
        "context": {"theory": "Initial theory content."},
        "filename": "previous_paper.pdf",
        "content": "Original PDF text content",
        "intent_override": "Write more equations",
        "token_count": 42
    }
    
    reference_materials = [
        {
            "filename": "reference_doc.docx",
            "content": "Reference document text parsed from ocr",
            "attachment_type": "passive_reference",
            "token_count": 120
        },
        {
            "filename": "notes.md",
            "content": "A simple markdown file upload",
            "attachment_type": "passive_reference",
            "token_count": 15
        }
    ]
    
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    
    orch = Orchestrator(
        writer=writer,
        config=config,
        registry_store=store,
        run_id="run_123",
        continuation_source=continuation_source,
        reference_materials=reference_materials
    )
    orch.user_topic = "Topic"
    orch.user_instructions = "Instructions"
    orch._renderer = lambda content, output_filename, config=None: output_filename
    
    # Run the pipeline
    orch.run_pipeline(render_artifact=False)
    
    # 1. Verify sources in database
    sources = store.get_run_sources("run_123")
    assert len(sources) == 3
    
    types = {s.source_type for s in sources}
    assert "continuation" in types
    assert "ocr" in types
    assert "manual_reference" in types
    
    continuation_src = next(s for s in sources if s.source_type == "continuation")
    assert continuation_src.title == "Continuity Topic"
    metadata = json.loads(continuation_src.metadata_json)
    assert metadata["token_count"] == 42
    assert metadata["intent_override"] == "Write more equations"
    
    docx_src = next(s for s in sources if s.title == "reference_doc.docx")
    assert docx_src.source_type == "ocr"
    
    md_src = next(s for s in sources if s.title == "notes.md")
    assert md_src.source_type == "manual_reference"
    
    # 2. Verify artifact files on disk & database registration
    attachments_path = Path(output_dir) / "attachments"
    assert attachments_path.exists()
    assert (attachments_path / "previous_paper.pdf.txt").exists()
    assert (attachments_path / "reference_doc.docx.txt").exists()
    assert (attachments_path / "notes.md").exists()
    
    artifacts = store.get_run_artifacts("run_123")
    types_art = {a.artifact_type for a in artifacts}
    assert "ocr_output" in types_art
    assert "markdown" in types_art

def test_web_research_results_registration(temp_env):
    workspace_path, store = temp_env
    output_dir = str(workspace_path / "run_web")
    config = _make_config(output_dir)
    
    # Mock researcher agent that produces file results on disk
    class MockResearcher(ResearcherAgent):
        def run_research(self, queries, run_dir):
            research_dir = Path(run_dir) / "research"
            research_dir.mkdir(parents=True, exist_ok=True)
            with open(research_dir / "query_0.json", "w", encoding="utf-8") as f:
                json.dump({
                    "query": "superconductivity progress",
                    "results": [
                        {
                            "title": "New High Temp Superconductors",
                            "url": "https://science.org/paper1",
                            "snippet": "We found a new material that superconducts at 150K",
                            "content": "Full parsed content of the superconducting article showing room temp potential."
                        }
                    ]
                }, f)
            return "Mock research findings text"
            
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    researcher = MockResearcher(AgentConfig(role="Researcher", model="mock", temperature=0.0, system_prompt="Research"), llm)
    
    orch = Orchestrator(
        writer=writer,
        researcher=researcher,
        config=config,
        registry_store=store,
        run_id="run_web",
        web_search_enabled=True
    )
    orch.user_topic = "Superconductivity"
    orch.user_instructions = "Find room temp superconductors"
    # dedicated planner configuration
    orch._has_dedicated_planner = True
    orch._renderer = lambda content, output_filename, config=None: output_filename
    
    orch.run_pipeline(render_artifact=False)
    
    # Verify research log artifact
    artifacts = store.get_run_artifacts("run_web")
    log_art = next(a for a in artifacts if a.artifact_type == "research_log")
    assert log_art.filename == "query_0.json"
    assert log_art.is_diagnostic is True
    
    # Verify crawled web source
    sources = store.get_run_sources("run_web")
    web_src = next(s for s in sources if s.source_type == "web")
    assert web_src.title == "New High Temp Superconductors"
    assert web_src.url == "https://science.org/paper1"
    
    metadata = json.loads(web_src.metadata_json)
    assert metadata["query"] == "superconductivity progress"
    assert "150K" in metadata["snippet"]

def test_evaluations_registration(temp_env):
    workspace_path, store = temp_env
    output_dir = str(workspace_path / "run_eval")
    config = _make_config(output_dir)
    
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    
    orch = Orchestrator(
        writer=writer,
        config=config,
        registry_store=store,
        run_id="run_eval"
    )
    orch.user_topic = "Evaluations test"
    orch._renderer = lambda content, output_filename, config=None: output_filename
    
    orch.run_pipeline(render_artifact=False)
    
    # Verify quality gate evaluation was registered
    evals = store.get_run_evaluations("run_eval")
    assert len(evals) >= 1
    
    qg_eval = next(e for e in evals if e.eval_type == "quality_gate")
    assert qg_eval.status == "passed"
    assert "passed" in qg_eval.summary or "all checks passed" in qg_eval.summary

def test_smoke_runner_registry_integration(temp_env, monkeypatch):
    workspace_path, store = temp_env
    
    # Redirect root, default DB path and note path inside runner script
    monkeypatch.setattr("scripts.ocr_research_smoke_runner.ROOT", workspace_path)
    monkeypatch.setattr("scripts.ocr_research_smoke_runner.LOG_DIR", workspace_path / "exports" / "_smoke_ocr_research")
    monkeypatch.setattr("scripts.ocr_research_smoke_runner.NOTE_PATH", workspace_path / "exports" / "OCR_RESEARCH_SMOKE_NOTES.md")
    
    # Mock scenario catalog
    from scripts.ocr_research_smoke_runner import scenario_catalog
    scenario = scenario_catalog()["web_search_off_standard_pipeline"]
    
    # Run mock scenario
    import argparse
    args = argparse.Namespace(
        scenario="web_search_off_standard_pipeline",
        note="exports/smoke_notes.md",
        log_path=str(workspace_path / "exports" / "test_stage_log.jsonl")
    )
    
    exit_code = run_scenario(scenario, args)
    assert exit_code == 0
    
    # Check that smoke run was logged in SQLite database
    # Find runs of kind="smoke"
    runner_db_path = workspace_path / "exports" / "_metadata" / "academic_pe_registry.sqlite3"
    runner_store = SQLiteRegistryStore(db_path=str(runner_db_path))
    runs = runner_store.list_runs()
    smoke_runs = [r for r in runs if r.kind == "smoke"]
    assert len(smoke_runs) >= 1
    
    smoke_run = next(r for r in smoke_runs if not r.run_id.endswith("_orch"))
    assert smoke_run.status == "succeeded"
    assert smoke_run.topic == scenario.title
    
    # Check evaluation
    evals = runner_store.get_run_evaluations(smoke_run.run_id)
    assert len(evals) == 1
    assert evals[0].eval_type == "smoke"
    assert evals[0].status == "passed"
    
    # Check stage log artifact
    artifacts = runner_store.get_run_artifacts(smoke_run.run_id)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "smoke_log"
    assert artifacts[0].is_diagnostic is True

def test_quality_runner_registry_integration(temp_env, monkeypatch):
    workspace_path, store = temp_env
    
    # Redirect root, default DB path and note path inside quality runner script
    monkeypatch.setattr("scripts.ocr_research_quality_eval_runner.ROOT", workspace_path)
    monkeypatch.setattr("scripts.ocr_research_quality_eval_runner.OUTPUT_DIR", workspace_path / "exports" / "_quality_eval_ocr_research")
    monkeypatch.setattr("scripts.ocr_research_quality_eval_runner.NOTE_PATH", workspace_path / "exports" / "OCR_RESEARCH_QUALITY_EVAL.md")
    
    import scripts.ocr_research_quality_eval_runner
    original_prepare_config = scripts.ocr_research_quality_eval_runner._prepare_config
    def mock_prepare_config(scenario, output_dir):
        config = original_prepare_config(scenario, output_dir)
        from academic_pe.core.config import ProviderEnum
        for name in config.agents:
            config.agents[name].provider = ProviderEnum.mock
            config.agents[name].model = "mock"
        return config
    monkeypatch.setattr("scripts.ocr_research_quality_eval_runner._prepare_config", mock_prepare_config)

    from scripts.ocr_research_quality_eval_runner import scenario_catalog as q_scenario_catalog
    scenario = q_scenario_catalog()["web_research_operational_brief"]
    
    # Run quality scenario
    exit_code = run_quality_scenario(scenario)
    assert exit_code == 0
    
    # Check that quality run was logged in SQLite database
    runner_db_path = workspace_path / "exports" / "_metadata" / "academic_pe_registry.sqlite3"
    runner_store = SQLiteRegistryStore(db_path=str(runner_db_path))
    runs = runner_store.list_runs()
    # Find nested mock orchestrator runs (kind="generation" or "smoke") and verify they succeeded
    gen_runs = [r for r in runs if r.kind in ("generation", "smoke")]
    assert len(gen_runs) == 1
    
    gen_run = gen_runs[0]
    assert gen_run.run_id.startswith("quality_")
    
    # Check evaluation
    evals = runner_store.get_run_evaluations(gen_run.run_id)
    # It should have quality_gate, contract_drift, and the runner's semi_manual evaluations
    eval_types = {e.eval_type for e in evals}
    assert "quality_gate" in eval_types
    assert "semi_manual" in eval_types
    
    semi_manual_eval = next(e for e in evals if e.eval_type == "semi_manual")
    assert semi_manual_eval.status == "pending"
    assert semi_manual_eval.summary is not None and "Pending manual review" in semi_manual_eval.summary
    
    # Check result artifacts
    artifacts = runner_store.get_run_artifacts(gen_run.run_id)
    types = {a.artifact_type for a in artifacts}
    assert "quality_result" in types
    assert "preview" in types
