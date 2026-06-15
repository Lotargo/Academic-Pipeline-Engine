import os
import tempfile
import pytest
from datetime import datetime
from academic_pe.core.registry.models import (
    Run, RunAgent, Artifact, RuntimeSnapshot,
    Section, Source, Evaluation, Event
)
from academic_pe.core.registry.sqlite_store import SQLiteRegistryStore

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_store_creation_and_migration(temp_db):
    # This should create db and apply migrations successfully
    store = SQLiteRegistryStore(db_path=temp_db)
    assert os.path.exists(temp_db)
    
    # Try creating store again - migrations should be idempotent
    store2 = SQLiteRegistryStore(db_path=temp_db)
    
    # Verify we can list runs (should be empty)
    runs = store2.list_runs()
    assert len(runs) == 0

def test_run_crud(temp_db):
    store = SQLiteRegistryStore(db_path=temp_db)
    
    run = Run(
        run_id="run_20260616_120000",
        kind="generation",
        status="created",
        topic="AI Testing",
        instructions_preview="Verify run CRUD works",
        pipeline_mode="standard",
        web_search_enabled=True,
        created_at=datetime.now().isoformat(),
        output_dir="/tmp/run"
    )
    
    store.create_run(run)
    
    # Retrieve run
    fetched = store.get_run("run_20260616_120000")
    assert fetched is not None
    assert fetched.run_id == run.run_id
    assert fetched.topic == "AI Testing"
    assert fetched.web_search_enabled is True
    
    # Update run
    store.update_run_status(
        run_id="run_20260616_120000",
        status="succeeded",
        finished_at=datetime.now().isoformat()
    )
    
    fetched = store.get_run("run_20260616_120000")
    assert fetched.status == "succeeded"
    assert fetched.finished_at is not None

def test_relations(temp_db):
    store = SQLiteRegistryStore(db_path=temp_db)
    
    run_id = "run_relations"
    run = Run(
        run_id=run_id,
        kind="generation",
        status="running",
        created_at=datetime.now().isoformat()
    )
    store.create_run(run)
    
    # 1. Agent
    agent = RunAgent(
        run_id=run_id,
        role="planner",
        provider="openai",
        model="gpt-4o",
        temperature=0.7,
        self_critique_enabled=True
    )
    store.add_agent(agent)
    agents = store.get_run_agents(run_id)
    assert len(agents) == 1
    assert agents[0].model == "gpt-4o"
    assert agents[0].self_critique_enabled is True
    
    # 2. Artifact
    artifact = Artifact(
        run_id=run_id,
        artifact_type="docx",
        path="/path/to/doc.docx",
        relative_path="doc.docx",
        filename="doc.docx",
        created_at=datetime.now().isoformat()
    )
    store.add_artifact(artifact)
    artifacts = store.get_run_artifacts(run_id)
    assert len(artifacts) == 1
    assert artifacts[0].filename == "doc.docx"
    
    # 3. Snapshot
    snapshot = RuntimeSnapshot(
        run_id=run_id,
        snapshot_type="config",
        version="1.0",
        fingerprint="abcd",
        metadata_json='{"key": "value"}'
    )
    store.add_runtime_snapshot(snapshot)
    snapshots = store.get_run_snapshots(run_id)
    assert len(snapshots) == 1
    assert snapshots[0].fingerprint == "abcd"
    
    # 4. Section
    section = Section(
        run_id=run_id,
        name="intro",
        title="Introduction",
        char_count=500,
        order_index=1
    )
    store.add_section(section)
    sections = store.get_run_sections(run_id)
    assert len(sections) == 1
    assert sections[0].name == "intro"
    
    # 5. Source
    source = Source(
        run_id=run_id,
        source_type="upload",
        title="Paper PDF",
        path="papers/pdf.pdf"
    )
    store.add_source(source)
    sources = store.get_run_sources(run_id)
    assert len(sources) == 1
    assert sources[0].title == "Paper PDF"
    
    # 6. Evaluation
    evaluation = Evaluation(
        run_id=run_id,
        eval_type="quality_gate",
        status="passed",
        summary="All metrics checked",
        created_at=datetime.now().isoformat()
    )
    store.add_evaluation(evaluation)
    evals = store.get_run_evaluations(run_id)
    assert len(evals) == 1
    assert evals[0].status == "passed"
    
    # 7. Event
    event = Event(
        run_id=run_id,
        event_type="progress",
        stage="planner",
        message="Planning complete",
        created_at=datetime.now().isoformat()
    )
    store.add_event(event)
    events = store.get_run_events(run_id)
    assert len(events) == 1
    assert events[0].stage == "planner"
