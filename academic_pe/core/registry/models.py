from pydantic import BaseModel
from typing import Optional

class Run(BaseModel):
    id: Optional[int] = None
    run_id: str
    kind: str
    status: str
    topic: Optional[str] = None
    instructions_preview: Optional[str] = None
    pipeline_mode: Optional[str] = None
    web_search_enabled: bool = False
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output_dir: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    metadata_json: Optional[str] = None

class RunAgent(BaseModel):
    id: Optional[int] = None
    run_id: str
    role: str
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    agent_type: Optional[str] = None
    self_critique_enabled: bool = False
    metadata_json: Optional[str] = None

class Artifact(BaseModel):
    id: Optional[int] = None
    run_id: str
    artifact_type: str
    path: str
    relative_path: str
    filename: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    created_at: str
    is_diagnostic: bool = False
    metadata_json: Optional[str] = None

class RuntimeSnapshot(BaseModel):
    id: Optional[int] = None
    run_id: str
    snapshot_type: str
    version: Optional[str] = None
    fingerprint: Optional[str] = None
    metadata_json: Optional[str] = None

class Section(BaseModel):
    id: Optional[int] = None
    run_id: str
    name: str
    title: Optional[str] = None
    semantic_role: Optional[str] = None
    heading_policy: Optional[str] = None
    char_count: Optional[int] = None
    order_index: Optional[int] = None
    content_path: Optional[str] = None
    content_sha256: Optional[str] = None
    metadata_json: Optional[str] = None

class Source(BaseModel):
    id: Optional[int] = None
    run_id: str
    source_type: str
    title: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    sha256: Optional[str] = None
    used_by: Optional[str] = None
    metadata_json: Optional[str] = None

class Evaluation(BaseModel):
    id: Optional[int] = None
    run_id: str
    eval_type: str
    status: str
    summary: Optional[str] = None
    result_path: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: str

class Event(BaseModel):
    id: Optional[int] = None
    run_id: str
    event_type: str
    stage: Optional[str] = None
    message: Optional[str] = None
    created_at: str
    metadata_json: Optional[str] = None
