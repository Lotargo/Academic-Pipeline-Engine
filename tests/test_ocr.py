import io
import pytest
from unittest.mock import MagicMock, patch

from academic_pe.core.ocr import (
    count_tokens,
    split_markdown_into_sections,
    parse_document,
    process_file_via_mistral_ocr,
)


def test_count_tokens():
    # Test typical English text
    text = "Hello world! This is a test of the token counter."
    assert count_tokens(text) > 0
    
    # Test empty string
    assert count_tokens("") == 0
    
    # Test Cyrillic text
    assert count_tokens("Привет, мир! Тест счетчика токенов.") > 0


def test_split_markdown_into_sections():
    md = """# Introduction
This is the intro.

## Background
Some background info.

# References
1. Paper A
2. Paper B
"""
    context, template = split_markdown_into_sections(md)
    assert "introduction" in context
    assert "background" in context
    assert "references" in context
    assert "intro" in context["introduction"]
    assert "background info" in context["background"]
    assert "Paper A" in context["references"]
    
    sections = template["sections"]
    assert len(sections) == 3
    assert sections[0]["name"] == "introduction"
    assert sections[0]["title"] == "Introduction"
    assert sections[0]["semantic_role"] == "body"
    
    assert sections[1]["name"] == "background"
    assert sections[1]["title"] == "Background"
    assert sections[1]["semantic_role"] == "body"
    
    assert sections[2]["name"] == "references"
    assert sections[2]["title"] == "References"
    assert sections[2]["semantic_role"] == "reference_section"


def test_split_markdown_into_sections_duplicate_headers():
    md = """# Header
Content 1
# Header
Content 2
"""
    context, template = split_markdown_into_sections(md)
    assert "header" in context
    assert "header_1" in context
    assert context["header"] == "Content 1"
    assert context["header_1"] == "Content 2"


def test_split_markdown_into_sections_empty_header():
    md = """This is a pre-header preamble text.
# !?
No name header
"""
    context, template = split_markdown_into_sections(md)
    assert "preamble" in context
    assert "section_1" in context
    assert "pre-header preamble" in context["preamble"]



def test_parse_document_markdown():
    content = "# Test Markdown"
    res = parse_document("test.md", content.encode("utf-8"), "text/markdown")
    assert res == content


@patch("academic_pe.core.ocr.process_file_via_mistral_ocr")
@patch("academic_pe.core.ocr.get_secret", return_value="fake_mistral_key")
def test_parse_document_text_formats_skip_mistral(mock_get_secret, mock_mistral):
    assert parse_document("notes.txt", b"plain text", "text/plain") == "plain text"
    assert parse_document("data.csv", b"name,value\nA,1", "text/csv") == "name | value\nA | 1"
    mock_mistral.assert_not_called()


@patch("academic_pe.core.ocr.process_file_via_mistral_ocr", return_value="# Parsed")
@patch("academic_pe.core.ocr.get_secret", return_value="fake_mistral_key")
def test_parse_document_office_reference_formats_use_mistral(mock_get_secret, mock_mistral):
    assert parse_document("slides.pptx", b"pptx_bytes", "application/vnd.openxmlformats-officedocument.presentationml.presentation") == "# Parsed"
    assert parse_document("sheet.xlsx", b"xlsx_bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == "# Parsed"
    assert mock_mistral.call_count == 2


@patch("academic_pe.core.ocr.get_secret", return_value=None)
@patch("fitz.open")
def test_parse_document_pdf_fallback(mock_fitz_open, mock_get_secret):
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "PDF Content"
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    res = parse_document("test.pdf", b"pdf_bytes", "application/pdf")
    assert res == "PDF Content"
    mock_fitz_open.assert_called_once()


@patch("academic_pe.core.ocr.get_secret", return_value=None)
@patch("docx.Document")
def test_parse_document_docx_fallback(mock_docx_doc, mock_get_secret):
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.text = "DOCX Content"
    mock_doc.paragraphs = [mock_para]
    mock_docx_doc.return_value = mock_doc

    res = parse_document("test.docx", b"docx_bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert res == "DOCX Content"
    mock_docx_doc.assert_called_once()


@patch("academic_pe.core.ocr.get_secret", return_value="fake_mistral_key")
@patch("requests.post")
@patch("requests.delete")
def test_process_file_via_mistral_ocr(mock_delete, mock_post, mock_get_secret):
    # Mock the upload response
    mock_upload_res = MagicMock()
    mock_upload_res.ok = True
    mock_upload_res.json.return_value = {"id": "file_123"}
    
    # Mock the ocr response
    mock_ocr_res = MagicMock()
    mock_ocr_res.ok = True
    mock_ocr_res.json.return_value = {
        "pages": [
            {"markdown": "Page 1 Markdown"},
            {"markdown": "Page 2 Markdown"}
        ]
    }
    
    mock_post.side_effect = [mock_upload_res, mock_ocr_res]
    
    # Mock the delete response
    mock_delete_res = MagicMock()
    mock_delete_res.ok = True
    mock_delete.return_value = mock_delete_res
    
    res = process_file_via_mistral_ocr("test.pdf", b"pdf_bytes", "application/pdf")
    assert res == "Page 1 Markdown\nPage 2 Markdown"
    
    # Verify calls
    assert mock_post.call_count == 2
    mock_delete.assert_called_once_with("https://api.mistral.ai/v1/files/file_123", headers={"Authorization": "Bearer fake_mistral_key"})


@patch("academic_pe.core.ocr.get_secret", return_value="fake_mistral_key")
@patch("requests.post")
@patch("requests.delete")
def test_process_file_via_mistral_ocr_failures(mock_delete, mock_post, mock_get_secret):
    # Mock a failed upload response
    mock_upload_res = MagicMock()
    mock_upload_res.ok = False
    mock_upload_res.status_code = 400
    mock_upload_res.text = "Bad Request"
    mock_post.return_value = mock_upload_res
    
    with pytest.raises(Exception) as excinfo:
        process_file_via_mistral_ocr("test.pdf", b"pdf_bytes", "application/pdf")
    assert "Mistral file upload failed: 400" in str(excinfo.value)
