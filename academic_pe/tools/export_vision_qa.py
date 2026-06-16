from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional

from openai import OpenAI

from academic_pe.core.config import ExportQAConfig
from academic_pe.core.secrets import get_secret


@dataclass
class VisionQAFinding:
    severity: str
    category: str
    page: Optional[int]
    message: str
    suggested_owner: str = "renderer"


@dataclass
class VisionQAReport:
    status: str
    summary: str
    findings: List[VisionQAFinding] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": [asdict(finding) for finding in self.findings],
            "raw_response": self.raw_response,
        }


VISION_QA_SYSTEM_PROMPT = """You are Export Vision QA for DOCX/PDF rendering.
Inspect page screenshots for obvious export defects only.
Do not critique writing quality, factual correctness, style preference, or document content.
Focus on renderer/conversion defects: raw Markdown syntax, broken links, broken tables,
overlapping text, clipped content, orphan table headers, unreadable code blocks, layout corruption.
Return ONLY valid JSON with this schema:
{
  "status": "passed" | "warning" | "failed",
  "summary": "short summary",
  "findings": [
    {
      "severity": "warning" | "error",
      "category": "renderer_bug" | "conversion_issue" | "content_issue" | "minor_visual",
      "page": 1,
      "message": "specific visual issue",
      "suggested_owner": "renderer" | "converter" | "writer" | "unknown"
    }
  ]
}
Use "failed" only for obvious blocking visual defects. Use "warning" for minor issues."""


def run_export_vision_qa(
    image_paths: list[str],
    *,
    config: Optional[ExportQAConfig] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> VisionQAReport:
    cfg = config or ExportQAConfig()
    provider_name = provider or str(getattr(cfg.provider, "value", cfg.provider))
    model_name = model or cfg.model
    temp = cfg.temperature if temperature is None else temperature

    valid_paths = [path for path in image_paths if os.path.exists(path)]
    if not valid_paths:
        return VisionQAReport(status="failed", summary="No QA page images were available.")

    if provider_name == "mock":
        return VisionQAReport(
            status="passed",
            summary=f"Mock vision QA inspected {len(valid_paths)} page image(s).",
            findings=[],
            raw_response='{"status":"passed","summary":"mock"}',
        )

    client = _vision_client(provider_name)
    response_text = _call_multimodal_chat(
        client=client,
        model=model_name,
        temperature=temp,
        image_paths=valid_paths,
    )
    return _parse_vision_report(response_text)


def _vision_client(provider_name: str) -> OpenAI:
    if provider_name == "zen":
        api_key = get_secret("zen")
        if not api_key:
            raise ValueError("Zen API key is not configured.")
        return OpenAI(api_key=api_key, base_url="https://opencode.ai/zen/v1")
    if provider_name == "openai":
        api_key = get_secret("openai")
        if not api_key:
            raise ValueError("OpenAI API key is not configured.")
        return OpenAI(api_key=api_key)
    if provider_name == "custom_openai":
        api_key = get_secret("custom_openai") or os.getenv("CUSTOM_API_KEY") or "sk-placeholder"
        base_url = os.getenv("CUSTOM_OPENAI_BASE_URL")
        if not base_url:
            raise ValueError("CUSTOM_OPENAI_BASE_URL is required for custom_openai vision QA.")
        return OpenAI(api_key=api_key, base_url=base_url)
    raise ValueError(f"Provider '{provider_name}' is not supported for export vision QA.")


def _call_multimodal_chat(
    *,
    client: OpenAI,
    model: str,
    temperature: float,
    image_paths: list[str],
) -> str:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Inspect these rendered export page screenshots. "
                "Report only obvious visual export/rendering issues. "
                "Return JSON only."
            ),
        }
    ]
    for index, path in enumerate(image_paths, 1):
        content.append({"type": "text", "text": f"Page {index}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(path)},
            }
        )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VISION_QA_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def _image_data_url(path: str) -> str:
    mime_type = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _parse_vision_report(raw_response: str) -> VisionQAReport:
    text = (raw_response or "").strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
    try:
        data = json.loads(text)
    except Exception:
        return VisionQAReport(
            status="warning",
            summary="Vision QA returned non-JSON output.",
            findings=[
                VisionQAFinding(
                    severity="warning",
                    category="minor_visual",
                    page=None,
                    message="Vision QA response could not be parsed as JSON.",
                    suggested_owner="unknown",
                )
            ],
            raw_response=raw_response,
        )

    findings = []
    for item in data.get("findings", []) if isinstance(data.get("findings"), list) else []:
        if not isinstance(item, dict):
            continue
        findings.append(
            VisionQAFinding(
                severity=str(item.get("severity") or "warning"),
                category=str(item.get("category") or "minor_visual"),
                page=item.get("page") if isinstance(item.get("page"), int) else None,
                message=str(item.get("message") or "Unspecified visual QA finding."),
                suggested_owner=str(item.get("suggested_owner") or "unknown"),
            )
        )

    status = str(data.get("status") or "").lower()
    if status not in {"passed", "warning", "failed"}:
        status = "failed" if any(f.severity == "error" for f in findings) else ("warning" if findings else "passed")
    summary = str(data.get("summary") or ("No visual export issues found." if status == "passed" else "Vision QA completed."))
    return VisionQAReport(status=status, summary=summary, findings=findings, raw_response=raw_response)
