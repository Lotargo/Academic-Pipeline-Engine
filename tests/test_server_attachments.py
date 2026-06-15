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
