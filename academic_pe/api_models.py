from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel

from academic_pe.core.config import TemplateMode


class ContinuationSource(BaseModel):
    source_type: str = "generated"
    topic: Optional[str] = None
    instructions: Optional[str] = None
    previous_prompt: Optional[str] = None
    context: Dict[str, str]
    document_plan: Optional[str] = None
    runtime_template: Optional[dict] = None
    runtime_prompt_manifest: Optional[dict] = None
    template_mode: Optional[TemplateMode] = None
    template_id: Optional[str] = None
    metadata_id: Optional[str] = None
    run_id: Optional[str] = None


class RunRequest(BaseModel):
    topic: str
    instructions: Optional[str] = None
    template_mode: Optional[TemplateMode] = None
    template_id: Optional[str] = None
    academic_mode: Optional[bool] = None
    author: Optional[str] = None
    continuation_source: Optional[ContinuationSource] = None


class ConfigUpdateRequest(BaseModel):
    config: dict


class ExportRequest(BaseModel):
    filename: Optional[str] = None
    topic: Optional[str] = None
    context: Optional[Dict[str, str]] = None
    runtime_template: Optional[dict] = None
    author: Optional[str] = None
    run_id: Optional[str] = None


class SecretUpdatePayload(BaseModel):
    provider: str
    api_key: str


class BulkHistoryPayload(BaseModel):
    ids: List[str]


class PromptEnhanceRequest(BaseModel):
    topic: str
    instructions: Optional[str] = None
    academic_mode: Optional[bool] = None


class PromptEnhanceResponse(BaseModel):
    topic: str
    instructions: str
