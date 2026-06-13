from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel

from academic_pe.core.config import TemplateMode


class RunRequest(BaseModel):
    topic: str
    instructions: Optional[str] = None
    template_mode: Optional[TemplateMode] = None
    template_id: Optional[str] = None
    academic_mode: Optional[bool] = None
    author: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    config: dict


class ExportRequest(BaseModel):
    filename: Optional[str] = None
    topic: Optional[str] = None
    context: Optional[Dict[str, str]] = None
    runtime_template: Optional[dict] = None
    author: Optional[str] = None


class SecretUpdatePayload(BaseModel):
    provider: str
    api_key: str


class BulkHistoryPayload(BaseModel):
    ids: List[str]


class PromptEnhanceRequest(BaseModel):
    topic: str
    instructions: Optional[str] = None


class PromptEnhanceResponse(BaseModel):
    topic: str
    instructions: str

