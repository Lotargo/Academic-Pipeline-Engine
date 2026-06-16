from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import ValidationError

from academic_pe.api_models import Attachment
from academic_pe.server import app


def test_upload_attachment_success(monkeypatch):
    monkeypatch.setattr(
        "academic_pe.core.ocr.parse_document",
        lambda filename, file_bytes, mime_type: "# Parsed Markdown\n\nBody text.",
    )
    monkeypatch.setattr("academic_pe.core.ocr.count_tokens", lambda text: 7)
    monkeypatch.setattr("academic_pe.server.load_config", lambda path: SimpleNamespace(ocr_token_limit=20))

    client = TestClient(app)
    response = client.post(
        "/api/attachments/upload",
        data={"attachment_type": "continuation_source"},
        files={"file": ("source.md", b"# Source", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "filename": "source.md",
        "content": "# Parsed Markdown\n\nBody text.",
        "attachment_type": "continuation_source",
        "token_count": 7,
    }


def test_upload_reference_allows_tabular_and_presentation_formats(monkeypatch):
    seen = {}

    def parse_document(filename, file_bytes, mime_type):
        seen["filename"] = filename
        return "# Parsed"

    monkeypatch.setattr("academic_pe.core.ocr.parse_document", parse_document)
    monkeypatch.setattr("academic_pe.core.ocr.count_tokens", lambda text: 3)
    monkeypatch.setattr("academic_pe.server.load_config", lambda path: SimpleNamespace(ocr_token_limit=20))

    client = TestClient(app)
    response = client.post(
        "/api/attachments/upload",
        data={"attachment_type": "passive_reference"},
        files={"file": ("slides.pptx", b"pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "# Parsed"
    assert seen["filename"] == "slides.pptx"


def test_upload_continuation_rejects_tabular_and_presentation_formats(monkeypatch):
    def fail_parse(filename, file_bytes, mime_type):
        raise AssertionError("parse_document should not be called")

    monkeypatch.setattr("academic_pe.core.ocr.parse_document", fail_parse)

    client = TestClient(app)
    response = client.post(
        "/api/attachments/upload",
        data={"attachment_type": "continuation_source"},
        files={"file": ("sheet.xlsx", b"xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 400
    assert "Unsupported continuation source format: .xlsx" in response.json()["detail"]


def test_upload_attachment_returns_parse_error(monkeypatch):
    def fail_parse(filename, file_bytes, mime_type):
        raise ValueError("Unsupported file format: .txt")

    monkeypatch.setattr("academic_pe.core.ocr.parse_document", fail_parse)

    client = TestClient(app)
    response = client.post(
        "/api/attachments/upload",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file format: .txt"


def test_upload_attachment_rejects_unknown_attachment_type(monkeypatch):
    client = TestClient(app)
    response = client.post(
        "/api/attachments/upload",
        data={"attachment_type": "mystery"},
        files={"file": ("source.md", b"# Source", "text/markdown")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "attachment_type must be 'passive_reference' or 'continuation_source'"


def test_upload_attachment_rejects_token_limit(monkeypatch):
    monkeypatch.setattr("academic_pe.core.ocr.parse_document", lambda filename, file_bytes, mime_type: "too long")
    monkeypatch.setattr("academic_pe.core.ocr.count_tokens", lambda text: 21)
    monkeypatch.setattr("academic_pe.server.load_config", lambda path: SimpleNamespace(ocr_token_limit=20))

    client = TestClient(app)
    response = client.post(
        "/api/attachments/upload",
        files={"file": ("long.md", b"too long", "text/markdown")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File 'long.md' exceeds the configured token limit of 20 tokens (contains 21 tokens)."


def test_attachment_model_rejects_unknown_attachment_type():
    try:
        Attachment(
            filename="source.md",
            content="content",
            attachment_type="mystery",
            token_count=1,
        )
        assert False, "Attachment should reject unsupported attachment_type"
    except ValidationError:
        pass
