import os
import re
import requests
import logging
import io
from typing import Optional, Tuple, Dict, List, Any
import tiktoken

from academic_pe.core.secrets import get_secret
from academic_pe.core.continuation import is_terminal_section_name
from academic_pe.core.document_structure import SemanticRole

logger = logging.getLogger(__name__)


def process_file_via_mistral_ocr(filename: str, file_bytes: bytes, mime_type: str) -> str:
    """
    Upload file to Mistral AI Files API, process it using the OCR API,
    and delete the file from Mistral storage afterward.
    """
    api_key = get_secret("mistral")
    if not api_key:
        raise ValueError("Mistral API key is not configured in secrets.json")

    headers = {"Authorization": f"Bearer {api_key}"}

    # 1. Upload the file
    logger.info("Uploading file %s to Mistral API...", filename)
    files = {
        "file": (filename, file_bytes, mime_type)
    }
    data = {
        "purpose": "ocr"
    }

    upload_url = "https://api.mistral.ai/v1/files"
    upload_res = requests.post(upload_url, headers=headers, files=files, data=data)
    if not upload_res.ok:
        raise Exception(f"Mistral file upload failed: {upload_res.status_code} - {upload_res.text}")

    file_id = upload_res.json()["id"]
    logger.info("Uploaded successfully. file_id: %s. Starting OCR processing...", file_id)

    # 2. Call the OCR API
    ocr_url = "https://api.mistral.ai/v1/ocr"
    ocr_payload = {
        "model": "mistral-ocr-latest",
        "document": {
            "file_id": file_id
        }
    }

    try:
        ocr_res = requests.post(ocr_url, headers=headers, json=ocr_payload)
        if not ocr_res.ok:
            raise Exception(f"Mistral OCR processing failed: {ocr_res.status_code} - {ocr_res.text}")

        ocr_data = ocr_res.json()

        # 3. Join the markdown of all pages
        pages = ocr_data.get("pages", [])
        markdown_text = "\n".join(page.get("markdown", "") for page in pages)
        return markdown_text

    finally:
        # 4. Clean up the file from Mistral storage
        logger.info("Deleting file_id %s from Mistral...", file_id)
        delete_url = f"https://api.mistral.ai/v1/files/{file_id}"
        try:
            requests.delete(delete_url, headers=headers)
        except Exception as e:
            logger.warning("Failed to delete file %s from Mistral: %s", file_id, e)


def extract_text_locally_pdf(file_bytes: bytes) -> str:
    """
    Fallback method to parse PDF locally using PyMuPDF (fitz).
    """
    logger.info("Extracting PDF text locally using PyMuPDF...")
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = []
    for page in doc:
        text.append(page.get_text())
    return "\n".join(text)


def extract_text_locally_docx(file_bytes: bytes) -> str:
    """
    Fallback method to parse DOCX locally using python-docx.
    """
    logger.info("Extracting DOCX text locally using python-docx...")
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return "\n".join(text)


def parse_document(filename: str, file_bytes: bytes, mime_type: str) -> str:
    """
    Parse uploaded file. Uses Mistral OCR if configured, otherwise falls back to local parsing.
    Returns clean markdown/plain text.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".md":
        return file_bytes.decode("utf-8", errors="replace")

    api_key = get_secret("mistral")
    if api_key:
        try:
            return process_file_via_mistral_ocr(filename, file_bytes, mime_type)
        except Exception as e:
            logger.warning("Mistral OCR API failed, falling back to local parsing: %s", e)

    # Local fallback
    if ext == ".pdf":
        return extract_text_locally_pdf(file_bytes)
    elif ext == ".docx":
        return extract_text_locally_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def count_tokens(text: str) -> int:
    """
    Measure the token length of processed Markdown using o200k_base.
    """
    try:
        encoding = tiktoken.get_encoding("o200k_base")
    except Exception:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return len(text.split())  # crude fallback
    return len(encoding.encode(text))


def split_markdown_into_sections(text: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Split a flat markdown string into a dictionary of sections and a runtime template dict.
    Returns (context, runtime_template).
    """
    lines = text.splitlines()
    sections = []

    current_title = None
    current_level = 0
    current_lines = []

    header_regex = re.compile(r"^(#{1,3})\s+(.+)$")

    for line in lines:
        match = header_regex.match(line)
        if match:
            if current_lines or current_title:
                sections.append({
                    "title": current_title,
                    "level": current_level,
                    "content": "\n".join(current_lines).strip()
                })
            current_title = match.group(2).strip()
            current_level = len(match.group(1))
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines or current_title:
        sections.append({
            "title": current_title,
            "level": current_level,
            "content": "\n".join(current_lines).strip()
        })

    context = {}
    template_sections = []

    for i, sec in enumerate(sections):
        title = sec["title"]
        content = sec["content"]

        if not title:
            name = "preamble"
            title = "Preamble"
        else:
            name = re.sub(r"[^a-zA-Z0-9\u0400-\u04FF\s_-]", "", title)
            name = re.sub(r"[\s_-]+", "_", name).strip("_").lower()
            if not name:
                name = f"section_{i}"

        orig_name = name
        counter = 1
        while name in context:
            name = f"{orig_name}_{counter}"
            counter += 1

        context[name] = content

        semantic_role = "body"
        title_lower = title.lower()
        if is_terminal_section_name(title_lower) or is_terminal_section_name(name):
            if any(x in title_lower for x in ["ref", "bib", "source", "literat"]):
                semantic_role = SemanticRole.reference_section.value
            elif any(x in title_lower for x in ["append", "prilozh"]):
                semantic_role = SemanticRole.appendix.value
            elif any(x in title_lower for x in ["gloss", "slovar"]):
                semantic_role = SemanticRole.glossary.value
            else:
                semantic_role = SemanticRole.reference_section.value

        template_sections.append({
            "name": name,
            "title": title,
            "semantic_role": semantic_role,
            "heading_policy": "inherit_source"
        })

    return context, {"sections": template_sections}
