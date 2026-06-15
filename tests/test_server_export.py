from fastapi.testclient import TestClient
from academic_pe.server import (
    _artifact_manifest_metadata,
    _history_item_from_metadata,
    _write_export_metadata,
    _with_artifact_manifest_metadata,
    app,
    current_run,
    run_lock,
)
from academic_pe.api_models import ExportRequest
import json
import os
from types import SimpleNamespace

def test_export_request_validation():
    # Verify that ExportRequest accepts runtime_template
    req = ExportRequest(
        filename="test.docx",
        topic="Dynamic Topic",
        author="Lotargo",
        run_id="run_20260613_120000",
        context={"intro": "Introduction text"},
        runtime_template={
            "source": "auto",
            "name": "Dynamic Schema",
            "category": "academic",
            "sections": [
                {"name": "intro", "title": "Introduction", "instruction": "Write intro"}
            ]
        }
    )
    assert req.runtime_template is not None
    assert req.runtime_template["name"] == "Dynamic Schema"
    assert req.author == "Lotargo"
    assert req.run_id == "run_20260613_120000"


def test_artifact_manifest_metadata_is_flattened_for_history_items():
    runtime_prompt_manifest = {
        "metadata": {
            "resolved_manifest": {"id": "creative_poem", "version": 1},
            "resolved_contract": {"artifact": "creative_poem", "visualization_required": False},
            "contract_sexpr": "(document\n  (artifact creative_poem)\n)",
            "manifest_selection": {
                "manifest_id": "creative_poem",
                "confidence": 0.9,
                "matched_phrases": ["poem"],
                "ambiguity_notes": [],
            },
            "decision_summary": {
                "selected_manifest": "creative_poem",
                "confidence": 0.9,
                "mode": "standard",
                "summary": "Detected poem request.",
            },
        }
    }

    metadata = _with_artifact_manifest_metadata(
        {
            "topic": "Poem",
            "timestamp": "2026-06-13 12:00:00",
            "runtime_prompt_manifest": runtime_prompt_manifest,
        }
    )
    history_item = _history_item_from_metadata("poem.20260613120000.metadata.json", metadata)

    assert _artifact_manifest_metadata(runtime_prompt_manifest)["resolved_manifest"]["id"] == "creative_poem"
    assert metadata["resolved_manifest"]["id"] == "creative_poem"
    assert metadata["resolved_contract"]["artifact"] == "creative_poem"
    assert metadata["manifest_selection"]["matched_phrases"] == ["poem"]
    assert metadata["decision_summary"]["selected_manifest"] == "creative_poem"
    assert history_item["resolved_manifest"]["id"] == "creative_poem"
    assert history_item["decision_summary"]["summary"] == "Detected poem request."
    assert history_item["contract_sexpr"].startswith("(document")


def test_export_metadata_persists_artifact_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class DummyExportResult:
        filename = "paper.docx"

        def to_dict(self):
            return {"status": "passed", "filename": self.filename, "issues": []}

    config = SimpleNamespace(
        pipeline=SimpleNamespace(
            template_mode=SimpleNamespace(value="auto"),
            template_id=None,
            academic_mode=False,
        )
    )

    with run_lock:
        previous_run = dict(current_run)
        current_run.update(
            {
                "instructions": "Write a poem.",
                "artifact_override": "creative_poem",
                "template_mode": "auto",
                "template_id": None,
                "runtime_template": None,
                "runtime_prompt_manifest": None,
                "document_plan": None,
                "original_context": {},
                "academic_mode": False,
                "logs": [],
                "reviewer_feedback": [],
            }
        )

    try:
        _write_export_metadata(
            DummyExportResult(),
            config,
            "Poem",
            "2026-06-13 12:00:00",
            "Lotargo",
            None,
            {"text": "A quiet poem."},
            None,
        )
    finally:
        with run_lock:
            current_run.clear()
            current_run.update(previous_run)

    metadata_files = list((tmp_path / "exports" / "_metadata").glob("*.metadata.json"))
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["artifact_override"] == "creative_poem"


def test_export_endpoint_with_runtime_template(monkeypatch, tmp_path):
    # Mock export_docx_with_qa to avoid actual LibreOffice call or file rendering
    mock_called = []
    
    from academic_pe.tools.export_qa import ExportResult, RenderResult
    
    def mock_export_docx_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        return ExportResult(
            status="passed",
            filename="paper.docx",
            path=str(tmp_path / "paper.docx"),
            issues=[],
            render=RenderResult(status="skipped", message="QA skipped")
        )
        
    monkeypatch.setattr("academic_pe.server.export_docx_with_qa", mock_export_docx_with_qa)
    
    client = TestClient(app)
    
    # 1. Post request with runtime_template
    payload = {
        "filename": "paper.docx",
        "topic": "My Dynamic Paper",
        "context": {
            "custom_intro": "Hello custom intro",
            "custom_method": "Hello custom method"
        },
        "runtime_template": {
            "source": "auto",
            "name": "Dynamic Outline",
            "category": "science",
            "sections": [
                {"name": "custom_intro", "title": "Custom Intro", "instruction": ""},
                {"name": "custom_method", "title": "Custom Method", "instruction": ""}
            ]
        }
    }
    
    response = client.post("/api/export/docx", json=payload)
    assert response.status_code == 200
    assert len(mock_called) == 1
    
    _, resolved_config, _ = mock_called[0]
    # Check that config sections match the runtime template sections
    sections = resolved_config.pipeline.sections
    assert len(sections) == 2
    assert sections[0].name == "custom_intro"
    assert sections[1].name == "custom_method"
    assert resolved_config.pipeline.title == "My Dynamic Paper"


def test_export_endpoint_filters_internal_only_runtime_sections(monkeypatch, tmp_path):
    mock_called = []

    def mock_export_docx_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        from academic_pe.tools.export_qa import ExportResult, RenderResult
        return ExportResult(
            status="passed",
            filename="paper.docx",
            path=str(tmp_path / "paper.docx"),
            issues=[],
            render=RenderResult(status="skipped", message="QA skipped")
        )

    monkeypatch.setattr("academic_pe.server.export_docx_with_qa", mock_export_docx_with_qa)

    client = TestClient(app)
    payload = {
        "filename": "paper.docx",
        "topic": "Story",
        "context": {
            "development": "Private beat notes.",
            "chapter_four": "Visible chapter text.",
        },
        "runtime_template": {
            "source": "auto",
            "name": "Story Continuation",
            "category": "creative",
            "sections": [
                {
                    "name": "development",
                    "title": "Development",
                    "instruction": "Private planning block.",
                    "semantic_role": "narrative_beat",
                    "heading_policy": "internal_only",
                },
                {
                    "name": "chapter_four",
                    "title": "Chapter Four",
                    "instruction": "Visible chapter.",
                    "semantic_role": "chapter",
                    "heading_policy": "user_mandated",
                },
            ],
        },
    }

    response = client.post("/api/export/docx", json=payload)

    assert response.status_code == 200
    assert len(mock_called) == 1
    exported_context, resolved_config, _ = mock_called[0]
    assert exported_context == {"chapter_four": "Visible chapter text."}
    assert [section.name for section in resolved_config.pipeline.sections] == ["chapter_four"]


def test_export_endpoint_with_dynamic_fallback(monkeypatch, tmp_path):
    mock_called = []
    
    def mock_export_docx_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        from academic_pe.tools.export_qa import ExportResult, RenderResult
        return ExportResult(
            status="passed",
            filename="paper.docx",
            path=str(tmp_path / "paper.docx"),
            issues=[],
            render=RenderResult(status="skipped", message="QA skipped")
        )
        
    monkeypatch.setattr("academic_pe.server.export_docx_with_qa", mock_export_docx_with_qa)
    
    client = TestClient(app)
    
    # Post request with context containing dynamic keys but NO runtime_template
    payload = {
        "filename": "paper.docx",
        "topic": "Dynamic Fallback Paper",
        "context": {
            "introduction_dynamic": "Intro",
            "results_dynamic": "Results"
        }
    }
    
    response = client.post("/api/export/docx", json=payload)
    assert response.status_code == 200
    assert len(mock_called) == 1
    
    _, resolved_config, _ = mock_called[0]
    # Check that config sections were dynamically generated from context keys
    sections = resolved_config.pipeline.sections
    assert len(sections) == 2
    assert sections[0].name == "introduction_dynamic"
    assert sections[0].topic == "Introduction Dynamic"
    assert sections[1].name == "results_dynamic"
    assert sections[1].topic == "Results Dynamic"
    assert resolved_config.pipeline.title == "Dynamic Fallback Paper"


def test_export_endpoint_excludes_document_plan_from_export(monkeypatch, tmp_path):
    mock_called = []

    def mock_export_docx_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        from academic_pe.tools.export_qa import ExportResult, RenderResult
        return ExportResult(
            status="passed",
            filename="paper.docx",
            path=str(tmp_path / "paper.docx"),
            issues=[],
            render=RenderResult(status="skipped", message="QA skipped")
        )

    monkeypatch.setattr("academic_pe.server.export_docx_with_qa", mock_export_docx_with_qa)

    client = TestClient(app)

    payload = {
        "filename": "paper.docx",
        "topic": "Paper With Plan",
        "context": {
            "document_plan": "# Outline\n\n- Internal planning only",
            "introduction_dynamic": "Intro",
            "results_dynamic": "Results"
        }
    }

    response = client.post("/api/export/docx", json=payload)

    assert response.status_code == 200
    assert len(mock_called) == 1

    exported_context, resolved_config, _ = mock_called[0]
    assert "document_plan" not in exported_context
    assert [section.name for section in resolved_config.pipeline.sections] == [
        "introduction_dynamic",
        "results_dynamic",
    ]


def test_export_endpoint_moves_terminal_sections_to_end(monkeypatch, tmp_path):
    import copy
    from academic_pe.core.config import load_config

    mock_called = []
    base_config = load_config("config/agents.yaml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("academic_pe.server.load_config", lambda path: copy.deepcopy(base_config))

    def mock_export_docx_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        from academic_pe.tools.export_qa import ExportResult, RenderResult
        return ExportResult(
            status="passed",
            filename="paper.docx",
            path=str(tmp_path / "paper.docx"),
            issues=[],
            render=RenderResult(status="skipped", message="QA skipped")
        )

    monkeypatch.setattr("academic_pe.server.export_docx_with_qa", mock_export_docx_with_qa)

    client = TestClient(app)
    payload = {
        "filename": "paper.docx",
        "topic": "Continuation Export",
        "context": {
            "analysis": "Analysis body.",
            "references": "1. Existing source.",
            "continuation": "Continuation body.",
            "appendix_a": "Appendix material.",
        },
        "runtime_template": {
            "source": "auto",
            "name": "Continuation Template",
            "category": "academic",
            "metadata": {
                "document_state": {
                    "terminal_sections": ["references", "appendix_a"],
                },
            },
            "sections": [
                {"name": "analysis", "title": "Analysis", "instruction": ""},
                {"name": "references", "title": "References", "instruction": "", "semantic_role": "reference_section"},
                {"name": "continuation", "title": "Continuation", "instruction": ""},
                {"name": "appendix_a", "title": "Appendix A", "instruction": "", "semantic_role": "appendix"},
            ],
        },
    }

    response = client.post("/api/export/docx", json=payload)

    assert response.status_code == 200
    assert len(mock_called) == 1
    exported_context, resolved_config, _ = mock_called[0]
    assert list(exported_context.keys()) == ["analysis", "continuation", "references", "appendix_a"]
    assert [section.name for section in resolved_config.pipeline.sections] == [
        "analysis",
        "continuation",
        "references",
        "appendix_a",
    ]


def test_pdf_export_endpoint_with_runtime_template(monkeypatch, tmp_path):
    import copy
    from academic_pe.core.config import load_config

    mock_called = []
    base_config = load_config("config/agents.yaml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("academic_pe.server.load_config", lambda path: copy.deepcopy(base_config))

    def mock_export_pdf_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        from academic_pe.tools.export_qa import ExportResult, RenderResult
        return ExportResult(
            status="passed",
            filename="paper.pdf",
            path=str(tmp_path / "paper.pdf"),
            issues=[],
            render=RenderResult(status="passed", pdf_path=str(tmp_path / "paper.pdf"), message="PDF exported")
        )

    monkeypatch.setattr("academic_pe.server.export_pdf_with_qa", mock_export_pdf_with_qa)

    client = TestClient(app)
    payload = {
        "topic": "My PDF Paper",
        "context": {
            "custom_intro": "Hello custom intro",
        },
        "runtime_template": {
            "source": "auto",
            "name": "PDF Outline",
            "category": "science",
            "sections": [
                {"name": "custom_intro", "title": "Custom Intro", "instruction": ""},
            ]
        }
    }

    response = client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.json()["filename"] == "paper.pdf"
    assert len(mock_called) == 1
    _, resolved_config, output_filename = mock_called[0]
    assert output_filename is None
    assert resolved_config.pipeline.title == "My PDF Paper"


def test_pdf_export_endpoint_uses_payload_run_directory(monkeypatch, tmp_path):
    import copy
    from academic_pe.core.config import load_config

    base_config = load_config("config/agents.yaml")
    monkeypatch.chdir(tmp_path)
    mock_called = []
    monkeypatch.setattr("academic_pe.server.load_config", lambda path: copy.deepcopy(base_config))

    def mock_export_pdf_with_qa(context, config, output_filename=None):
        mock_called.append((context, config, output_filename))
        from academic_pe.tools.export_qa import ExportResult, RenderResult
        return ExportResult(
            status="passed",
            filename="paper.pdf",
            path=str(tmp_path / "exports" / "run_20260613_120000" / "paper.pdf"),
            issues=[],
            render=RenderResult(
                status="passed",
                pdf_path=str(tmp_path / "exports" / "run_20260613_120000" / "paper.pdf"),
                message="PDF exported",
            ),
        )

    monkeypatch.setattr("academic_pe.server.export_pdf_with_qa", mock_export_pdf_with_qa)

    client = TestClient(app)
    response = client.post("/api/export/pdf", json={
        "topic": "Archived PDF Paper",
        "context": {"intro": "Intro"},
        "run_id": "run_20260613_120000",
    })

    assert response.status_code == 200
    assert response.json()["filename"] == "run_20260613_120000/paper.pdf"
    assert len(mock_called) == 1
    _, resolved_config, _ = mock_called[0]
    assert resolved_config.pipeline.output_dir == os.path.join("exports", "run_20260613_120000")
    assert (tmp_path / "exports" / "run_20260613_120000").is_dir()


def test_pdf_export_endpoint_rejects_invalid_run_id(monkeypatch):
    client = TestClient(app)
    response = client.post("/api/export/pdf", json={
        "topic": "Invalid Run",
        "context": {"intro": "Intro"},
        "run_id": "../bad",
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid run_id"


def test_pdf_export_endpoint_reports_missing_converter(monkeypatch):
    def mock_export_pdf_with_qa(context, config, output_filename=None):
        from academic_pe.tools.export_qa import ExportIssue, ExportResult, RenderResult
        return ExportResult(
            status="failed",
            filename="paper.pdf",
            path="exports/paper.pdf",
            issues=[ExportIssue("error", "LibreOffice/soffice not found.")],
            render=RenderResult(status="skipped", message="LibreOffice/soffice not found.")
        )

    monkeypatch.setattr("academic_pe.server.export_pdf_with_qa", mock_export_pdf_with_qa)

    client = TestClient(app)
    response = client.post("/api/export/pdf", json={
        "topic": "Missing Converter",
        "context": {"intro": "Intro"},
    })

    assert response.status_code == 503
    assert "LibreOffice" in response.json()["detail"]


def test_history_archive_unarchive_preserves_author(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    metadata_dir = tmp_path / "exports" / "_metadata"
    metadata_dir.mkdir(parents=True)
    metadata_path = metadata_dir / "paper.20260613120000.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "topic": "Archive Me",
                "timestamp": "2026-06-13 12:00:00",
                "author": "Lotargo",
                "status": "COMPLETED",
                "docx_filename": None,
                "context": {"intro": "Hello"},
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)

    archive_response = client.post(f"/api/history/{metadata_path.name}/archive")
    assert archive_response.status_code == 200
    archived_item = archive_response.json()
    assert archived_item["archived"] is True
    assert archived_item["author"] == "Lotargo"

    visible_response = client.get("/api/history")
    assert visible_response.status_code == 200
    assert visible_response.json() == []

    archived_response = client.get("/api/history?archived=true")
    assert archived_response.status_code == 200
    assert archived_response.json()[0]["author"] == "Lotargo"

    unarchive_response = client.post(f"/api/history/{metadata_path.name}/unarchive")
    assert unarchive_response.status_code == 200
    assert unarchive_response.json()["author"] == "Lotargo"

    restored_response = client.get("/api/history")
    assert restored_response.status_code == 200
    assert restored_response.json()[0]["author"] == "Lotargo"


def test_history_delete_removes_metadata_and_docx(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    export_dir = tmp_path / "exports"
    metadata_dir = export_dir / "_metadata"
    metadata_dir.mkdir(parents=True)
    docx_path = export_dir / "paper.docx"
    docx_path.write_bytes(b"docx")
    metadata_path = metadata_dir / "paper.20260613120000.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "topic": "Delete Me",
                "timestamp": "2026-06-13 12:00:00",
                "author": "Lotargo",
                "status": "COMPLETED",
                "docx_filename": "paper.docx",
                "context": {"intro": "Hello"},
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.delete(f"/api/history/{metadata_path.name}")

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert not metadata_path.exists()
    assert not docx_path.exists()


def test_history_delete_removes_run_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    export_dir = tmp_path / "exports"
    metadata_dir = export_dir / "_metadata"
    metadata_dir.mkdir(parents=True)
    
    # Create run directory
    run_dir = export_dir / "run_20260613_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "plot.png").write_bytes(b"plot")
    (run_dir / "Final_Academic_Paper.docx").write_bytes(b"docx")
    
    metadata_path = metadata_dir / "run_20260613_120000.20260613120000.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "topic": "Delete Run Dir",
                "timestamp": "2026-06-13 12:00:00",
                "author": "Lotargo",
                "status": "COMPLETED",
                "docx_filename": "run_20260613_120000/Final_Academic_Paper.docx",
                "context": {"intro": "Hello"},
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.delete(f"/api/history/{metadata_path.name}")

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert not metadata_path.exists()
    assert not run_dir.exists()


def test_cleanup_run_directory_on_failure_and_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir(parents=True)
    
    from academic_pe.server import _cleanup_run_directory
    
    # 1. Test success=False deletes directory completely
    run_dir_fail = export_dir / "run_20260613_111111"
    run_dir_fail.mkdir(parents=True)
    (run_dir_fail / "temp.png").write_bytes(b"temp")
    
    _cleanup_run_directory("run_20260613_111111", success=False)
    assert not run_dir_fail.exists()
    
    # 2. Test success=True on empty directory deletes it
    run_dir_empty = export_dir / "run_20260613_222222"
    run_dir_empty.mkdir(parents=True)
    
    _cleanup_run_directory("run_20260613_222222", success=True)
    assert not run_dir_empty.exists()
    
    # 3. Test success=True on non-empty directory keeps it
    run_dir_nonempty = export_dir / "run_20260613_333333"
    run_dir_nonempty.mkdir(parents=True)
    (run_dir_nonempty / "plot.png").write_bytes(b"plot")
    
    _cleanup_run_directory("run_20260613_333333", success=True)
    assert run_dir_nonempty.exists()
    assert (run_dir_nonempty / "plot.png").exists()


def test_startup_cleanup_empty_run_directories(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    export_dir = tmp_path / "exports"
    export_dir.mkdir(parents=True)
    
    from academic_pe.server import cleanup_empty_run_directories
    
    # Create empty run directory
    run_empty = export_dir / "run_20260613_444444"
    run_empty.mkdir(parents=True)
    
    # Create non-empty run directory
    run_nonempty = export_dir / "run_20260613_555555"
    run_nonempty.mkdir(parents=True)
    (run_nonempty / "keep.txt").write_text("keep")
    
    # Create non-matching directory
    other_dir = export_dir / "some_other_directory"
    other_dir.mkdir(parents=True)
    
    cleanup_empty_run_directories()
    
    assert not run_empty.exists()
    assert run_nonempty.exists()
    assert other_dir.exists()
