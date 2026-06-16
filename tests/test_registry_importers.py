import os
import json
import tempfile
import pytest
from datetime import datetime
from academic_pe.core.registry.sqlite_store import SQLiteRegistryStore
from academic_pe.core.registry.importers import import_metadata_json, import_all_metadata_jsons

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d

def test_import_single_metadata_json(temp_db, temp_dir):
    store = SQLiteRegistryStore(db_path=temp_db)
    
    # 1. Prepare dummy docx and pdf files so get_file_metadata will read sizes / checksums if they exist
    docx_file = os.path.join(temp_dir, "test_doc.docx")
    pdf_file = os.path.join(temp_dir, "test_doc.pdf")
    with open(docx_file, "w") as f:
        f.write("mock docx content")
    with open(pdf_file, "w") as f:
        f.write("mock pdf content")
        
    # 2. Write metadata JSON
    run_id = "run_20260616_120000"
    metadata_data = {
        "run_id": run_id,
        "topic": "Machine Learning",
        "instructions": "Use python to implement ML models",
        "timestamp": "2026-06-16T12:00:00",
        "status": "COMPLETED",
        "docx_filename": docx_file,
        "pdf_filename": pdf_file,
        "context": {
            "document_plan": "# Plan",
            "overview": "Generated overview text.",
        },
        "document_plan": "# Plan",
        "previous_prompt": "Topic: Machine Learning\nInstructions: Use python to implement ML models",
        "template_mode": "auto",
        "resolved_manifest": {"id": "technical_readme", "version": 1},
        "decision_summary": {"confidence": 0.95},
        "runtime_template": {
            "template_id": "compat_template",
            "metadata": {"test": "ok"}
        },
        "continuation_source": {
            "docx_filename": "source.docx",
            "topic": "Source Topic"
        }
    }
    
    metadata_path = os.path.join(temp_dir, f"{run_id}.20260616120000.metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_data, f)
        
    # 3. Import
    imported_run_id = import_metadata_json(store, metadata_path, output_dir=temp_dir)
    assert imported_run_id == run_id
    
    # 4. Assertions on SQLite
    run = store.get_run(run_id)
    assert run is not None
    assert run.run_id == run_id
    assert run.topic == "Machine Learning"
    assert run.status == "succeeded"
    run_meta = json.loads(run.metadata_json)
    assert run_meta["context"]["overview"] == "Generated overview text."
    assert run_meta["document_plan"] == "# Plan"
    assert run_meta["previous_prompt"].startswith("Topic: Machine Learning")
    assert run_meta["template_mode"] == "auto"
    assert run_meta["resolved_manifest"] == {"id": "technical_readme", "version": 1}
    assert run_meta["decision_summary"] == {"confidence": 0.95}
    
    # Check artifacts (should have docx, pdf, and metadata json)
    artifacts = store.get_run_artifacts(run_id)
    assert len(artifacts) == 3
    types = {a.artifact_type for a in artifacts}
    assert "docx" in types
    assert "pdf" in types
    assert "json" in types
    
    # Check snapshots
    snapshots = store.get_run_snapshots(run_id)
    assert len(snapshots) == 1
    assert snapshots[0].snapshot_type == "runtime_template"
    
    # Check sources
    sources = store.get_run_sources(run_id)
    assert len(sources) == 1
    assert sources[0].source_type == "continuation"

def test_import_all_metadata_jsons(temp_db, temp_dir):
    store = SQLiteRegistryStore(db_path=temp_db)
    
    # Create two metadata files
    run1 = "run_20260616_130000"
    run2 = "run_20260616_140000"
    
    with open(os.path.join(temp_dir, f"{run1}.20260616130000.metadata.json"), "w") as f:
        json.dump({"run_id": run1, "topic": "Topic 1", "status": "COMPLETED"}, f)
        
    with open(os.path.join(temp_dir, f"{run2}.20260616140000.metadata.json"), "w") as f:
        json.dump({"run_id": run2, "topic": "Topic 2", "status": "FAILED"}, f)
        
    imported = import_all_metadata_jsons(store, metadata_dir=temp_dir, output_dir=temp_dir)
    assert len(imported) == 2
    assert run1 in imported
    assert run2 in imported
    
    r1 = store.get_run(run1)
    assert r1.topic == "Topic 1"
    assert r1.status == "succeeded"
    
    r2 = store.get_run(run2)
    assert r2.topic == "Topic 2"
    assert r2.status == "failed"
