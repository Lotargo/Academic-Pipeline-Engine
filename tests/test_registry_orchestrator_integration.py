import os
import tempfile
import pytest
from academic_pe.core.orchestrator import Orchestrator
from academic_pe.core.config import AppConfig, AgentConfig, PipelineConfig, SectionPrompt, QualityGateConfig, VolumeGateConfig, LatexGateConfig, PromptLeakageGateConfig
from academic_pe.core.llm import MockProvider
from academic_pe.agents.base import DefaultAgent
from academic_pe.core.registry import SQLiteRegistryStore

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

def _make_config() -> AppConfig:
    return AppConfig(
        agents={
            "writer": AgentConfig(
                role="Writer", model="mock", temperature=0.0,
                system_prompt="You are a writer.",
            ),
        },
        quality_gate=QualityGateConfig(
            volume=VolumeGateConfig(enabled=False),
            latex=LatexGateConfig(enabled=False),
            prompt_leakage=PromptLeakageGateConfig(enabled=False),
        ),
        pipeline=PipelineConfig(
            sections=[
                SectionPrompt(name="theory", topic="Theory Topic", instruction="write theory"),
            ]
        )
    )

def test_orchestrator_registers_run_details(temp_db):
    config = _make_config()
    run_id = "run_20260616_180000"
    config.pipeline.output_dir = f"exports/{run_id}"
    
    # Initialize mock writer agent
    llm = MockProvider()
    writer = DefaultAgent(config.agents["writer"], llm)
    
    # Initialize SQLite Registry Store
    registry_store = SQLiteRegistryStore(db_path=temp_db)
    
    # Create orchestrator with registry
    orch = Orchestrator(
        writer=writer,
        config=config,
        registry_store=registry_store,
        run_id=run_id
    )
    
    # Execute pipeline
    orch.user_topic = "Registry Integration"
    orch.user_instructions = "Verify registry logs"
    
    # We mock _renderer to avoid actual docx generation
    orch._renderer = lambda context, output_filename, config=None: output_filename
    
    output_path = orch.run_pipeline(render_artifact=True)
    assert output_path != ""
    
    # Verify run table
    run = registry_store.get_run(run_id)
    assert run is not None
    assert run.run_id == run_id
    assert run.topic == "Registry Integration"
    assert run.status == "succeeded"
    assert run.pipeline_mode == "standard"
    assert run.web_search_enabled is False
    
    # Verify agents table
    agents = registry_store.get_run_agents(run_id)
    assert len(agents) >= 1
    roles = {a.role for a in agents}
    assert "writer" in roles
    
    # Verify sections table
    sections = registry_store.get_run_sections(run_id)
    assert len(sections) >= 2  # document_plan and theory
    sec_names = {s.name for s in sections}
    assert "document_plan" in sec_names
    assert "theory" in sec_names
