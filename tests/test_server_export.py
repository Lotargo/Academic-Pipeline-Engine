from fastapi.testclient import TestClient
from academic_pe.server import app, current_run, run_lock
from academic_pe.api_models import ExportRequest

def test_export_request_validation():
    # Verify that ExportRequest accepts runtime_template
    req = ExportRequest(
        filename="test.docx",
        topic="Dynamic Topic",
        author="Lotargo",
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
