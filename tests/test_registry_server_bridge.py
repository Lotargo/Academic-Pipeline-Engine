import os
import json
import tempfile
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

import academic_pe.server
from academic_pe.server import app, _write_history_metadata
from academic_pe.core.registry import SQLiteRegistryStore

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
    
    # Instantiate SQLiteRegistryStore on temp db
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

def test_bridge_write_updates_registry(test_env):
    client, store, metadata_dir = test_env
    
    # Create history item
    run_id = "run_20260616_120000"
    metadata_filename = os.path.join(metadata_dir, f"{run_id}.20260616120000.metadata.json")
    
    data = {
        "run_id": run_id,
        "topic": "Bridge Testing",
        "instructions": "Verify SQLite sync",
        "timestamp": datetime.now().isoformat(),
        "status": "COMPLETED",
        "docx_filename": "test.docx"
    }
    
    # This calls _write_history_metadata which triggers sync to registry_store
    _write_history_metadata(metadata_filename, data)
    
    # Verify run exists in registry
    run = store.get_run(run_id)
    assert run is not None
    assert run.topic == "Bridge Testing"
    assert run.status == "succeeded"
    
    # Verify docx artifact was registered
    artifacts = store.get_run_artifacts(run_id)
    assert len(artifacts) == 2  # docx and json metadata
    types = {a.artifact_type for a in artifacts}
    assert "docx" in types
    assert "json" in types

def test_bridge_archive_and_delete(test_env):
    client, store, metadata_dir = test_env
    
    run_id = "run_20260616_150000"
    metadata_id = f"{run_id}.20260616150000.metadata.json"
    metadata_filename = os.path.join(metadata_dir, metadata_id)
    
    data = {
        "run_id": run_id,
        "topic": "Archiving Test",
        "status": "COMPLETED",
        "archived": False
    }
    
    _write_history_metadata(metadata_filename, data)
    
    # 1. Archive via API
    response = client.post(f"/api/history/{metadata_id}/archive")
    assert response.status_code == 200
    
    # Check SQLite registry got updated
    run = store.get_run(run_id)
    assert run is not None
    metadata_parsed = json.loads(run.metadata_json)
    assert metadata_parsed.get("archived") is True
    
    # 2. Unarchive via API
    response = client.post(f"/api/history/{metadata_id}/unarchive")
    assert response.status_code == 200
    run = store.get_run(run_id)
    metadata_parsed = json.loads(run.metadata_json)
    assert metadata_parsed.get("archived") is False
    
    # 3. Delete via API
    response = client.delete(f"/api/history/{metadata_id}")
    assert response.status_code == 200
    
    # Check run was deleted from SQLite
    run = store.get_run(run_id)
    assert run is None
