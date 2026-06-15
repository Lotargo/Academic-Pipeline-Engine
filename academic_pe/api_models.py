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
    intent_override: Optional[str] = None
    metadata_id: Optional[str] = None
    run_id: Optional[str] = None


class Attachment(BaseModel):
    filename: str
    content: str
    attachment_type: str  # "passive_reference" or "continuation_source"
    token_count: int


class RunRequest(BaseModel):
    topic: str
    instructions: Optional[str] = None
    template_mode: Optional[TemplateMode] = None
    template_id: Optional[str] = None
    academic_mode: Optional[bool] = None
    author: Optional[str] = None
    continuation_source: Optional[ContinuationSource] = None
    artifact_override: Optional[str] = None
    web_search_enabled: Optional[bool] = None
    attachments: Optional[List[Attachment]] = None


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
    artifact_override: Optional[str] = None


class PromptEnhanceResponse(BaseModel):
    topic: str
    instructions: str
    self_critique_summary: Optional[str] = None
    artifact_override: Optional[str] = None
    resolved_manifest: Optional[dict] = None
    resolved_contract: Optional[dict] = None
    contract_sexpr: Optional[str] = None
    manifest_selection: Optional[dict] = None
    decision_summary: Optional[dict] = None
