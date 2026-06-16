import os
import json
import tempfile
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

import academic_pe.server
from academic_pe.server import app, _write_history_metadata
from academic_pe.core.registry import SQLiteRegistryStore, NoopRegistryStore
from academic_pe.core.registry.models import (
    Run, RunAgent, Artifact, RuntimeSnapshot,
    Section, Source, Evaluation, Event
)

@pytest.fixture
def test_env():
    # 1. Temporary SQLite db
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    
    # 2. Setup mock metadata directory
    temp_dir = tempfile.TemporaryDirectory()
    metadata_dir = os.path.join(temp_dir.name, "_metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    
    # 3. Patch server global registry_store and history directory
    old_store = academic_pe.server.registry_store
    old_meta_dir = academic_pe.server._history_metadata_dir
    
    new_store = SQLiteRegistryStore(db_path=db_path)
    academic_pe.server.registry_store = new_store
    academic_pe.server._history_metadata_dir = lambda: metadata_dir
    
    client = TestClient(app)
    
    yield client, new_store, metadata_dir
    
    # Restore
    academic_pe.server.registry_store = old_store
    academic_pe.server._history_metadata_dir = old_meta_dir
    temp_dir.cleanup()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_list_runs_filtering(test_env):
    client, store, _ = test_env
    
    # Create test runs
    run1 = Run(
        run_id="run_1",
        kind="generation",
        status="succeeded",
        topic="Topic 1",
        pipeline_mode="standard",
        created_at="2026-06-16T10:00:00",
        metadata_json=json.dumps({"template_id": "tpl_alpha"})
    )
    run2 = Run(
        run_id="run_2",
        kind="generation",
        status="failed",
        topic="Topic 2",
        pipeline_mode="continuation",
        created_at="2026-06-16T11:00:00",
        metadata_json=json.dumps({"template_id": "tpl_beta"})
    )
    run3 = Run(
        run_id="run_3",
        kind="smoke",
        status="succeeded",
        topic="Topic 3",
        pipeline_mode="standard",
        created_at="2026-06-17T09:00:00",
        metadata_json=json.dumps({"template_id": "tpl_alpha"})
    )
    
    store.create_run(run1)
    store.create_run(run2)
    store.create_run(run3)
    
    # Add artifacts to run1 to test artifact_type filter
    store.add_artifact(Artifact(
        run_id="run_1",
        artifact_type="pdf",
        path="foo.pdf",
        relative_path="foo.pdf",
        filename="foo.pdf",
        created_at="2026-06-16T10:05:00"
    ))
    
    # 1. Test basic listing via API
    resp = client.get("/api/registry/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 3
    # Order should be DESC by created_at (run_3, run_2, run_1)
    assert runs[0]["run_id"] == "run_3"
    assert runs[1]["run_id"] == "run_2"
    assert runs[2]["run_id"] == "run_1"
    
    # 2. Test status filter
    resp = client.get("/api/registry/runs?status=failed")
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_2"
    
    # 3. Test kind filter
    resp = client.get("/api/registry/runs?kind=smoke")
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_3"
    
    # 4. Test pipeline_mode filter
    resp = client.get("/api/registry/runs?pipeline_mode=continuation")
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_2"
    
    # 5. Test template_id filter
    resp = client.get("/api/registry/runs?template_id=tpl_alpha")
    runs = resp.json()
    assert len(runs) == 2
    assert {r["run_id"] for r in runs} == {"run_1", "run_3"}
    
    # 6. Test artifact_type filter
    resp = client.get("/api/registry/runs?artifact_type=pdf")
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_1"
    
    # 7. Test created_date filter (exact date)
    resp = client.get("/api/registry/runs?created_date=2026-06-16")
    runs = resp.json()
    assert len(runs) == 2
    assert {r["run_id"] for r in runs} == {"run_1", "run_2"}
    
    # 8. Test created_date filter (month prefix)
    resp = client.get("/api/registry/runs?created_date=2026-06")
    runs = resp.json()
    assert len(runs) == 3
    
    # 9. Test pagination (limit/offset)
    resp = client.get("/api/registry/runs?limit=1&offset=1")
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_2"

def test_inspect_run(test_env):
    client, store, _ = test_env
    
    run_id = "run_inspect"
    run = Run(
        run_id=run_id,
        kind="generation",
        status="running",
        topic="Inspect Topic",
        created_at="2026-06-16T12:00:00"
    )
    store.create_run(run)
    
    # Add relations
    store.add_agent(RunAgent(run_id=run_id, role="writer", model="gpt-4o"))
    store.add_artifact(Artifact(run_id=run_id, artifact_type="docx", path="out.docx", relative_path="out.docx", filename="out.docx", created_at="2026-06-16T12:01:00"))
    store.add_runtime_snapshot(RuntimeSnapshot(run_id=run_id, snapshot_type="runtime_template", metadata_json="{}"))
    store.add_section(Section(run_id=run_id, name="sec1", title="Sec 1"))
    store.add_source(Source(run_id=run_id, source_type="web", title="Src 1"))
    store.add_evaluation(Evaluation(run_id=run_id, eval_type="smoke", status="passed", created_at="2026-06-16T12:02:00"))
    store.add_event(Event(run_id=run_id, event_type="stage", stage="start", message="Run started", created_at="2026-06-16T12:00:00"))
    
    resp = client.get(f"/api/registry/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["run"]["run_id"] == run_id
    assert len(data["agents"]) == 1
    assert data["agents"][0]["role"] == "writer"
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["artifact_type"] == "docx"
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["snapshot_type"] == "runtime_template"
    assert len(data["sections"]) == 1
    assert data["sections"][0]["name"] == "sec1"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_type"] == "web"
    assert len(data["evaluations"]) == 1
    assert data["evaluations"][0]["eval_type"] == "smoke"
    assert len(data["events"]) == 1
    assert data["events"][0]["event_type"] == "stage"
    
    # Test 404 for non-existent run
    resp = client.get("/api/registry/runs/nonexistent")
    assert resp.status_code == 404

def test_api_history_integration(test_env):
    client, store, metadata_dir = test_env
    
    # Create a generation run in registry
    run_id = "run_hist"
    run = Run(
        run_id=run_id,
        kind="generation",
        status="succeeded",
        topic="History Topic",
        created_at="2026-06-16T12:00:00",
        metadata_json=json.dumps({
            "archived": False,
            "academic_mode": True,
            "author": "Tester"
        })
    )
    store.create_run(run)
    store.add_artifact(Artifact(
        run_id=run_id,
        artifact_type="docx",
        path="out.docx",
        relative_path="out.docx",
        filename="out.docx",
        created_at="2026-06-16T12:01:00"
    ))
    
    # Mock existence of the docx output file on disk so it is not filtered out
    os.makedirs(os.path.join("exports", run_id), exist_ok=True)
    temp_docx = os.path.join("exports", run_id, "out.docx")
    with open(temp_docx, "w") as f:
        f.write("mock docx content")
        
    try:
        resp = client.get("/api/history")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["run_id"] == run_id
        assert items[0]["topic"] == "History Topic"
        assert items[0]["academic_mode"] is True
        assert items[0]["author"] == "Tester"
        assert items[0]["filename"] == "out.docx"
    finally:
        if os.path.exists(temp_docx):
            os.remove(temp_docx)
        if os.path.exists(os.path.join("exports", run_id)):
            os.rmdir(os.path.join("exports", run_id))

def test_api_history_noop_fallback(test_env):
    client, store, metadata_dir = test_env
    
    # Temporarily set registry_store to NoopRegistryStore to force fallback
    academic_pe.server.registry_store = NoopRegistryStore()
    
    # Create legacy JSON metadata file
    metadata_filename = os.path.join(metadata_dir, "legacy.20260616120000.metadata.json")
    data = {
        "run_id": "run_20260616_120000",
        "topic": "Legacy File Topic",
        "timestamp": "2026-06-16T12:00:00",
        "status": "COMPLETED",
        "docx_filename": "legacy.docx"
    }
    with open(metadata_filename, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    # Mock existence of the docx output file on disk so it is not filtered out
    temp_docx = os.path.join("exports", "legacy.docx")
    with open(temp_docx, "w") as f:
        f.write("mock docx content")
        
    try:
        resp = client.get("/api/history")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["run_id"] == "run_20260616_120000"
        assert items[0]["topic"] == "Legacy File Topic"
    finally:
        # Restore store
        academic_pe.server.registry_store = store
        if os.path.exists(temp_docx):
            os.remove(temp_docx)
