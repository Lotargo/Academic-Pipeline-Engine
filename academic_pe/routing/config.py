from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RoutingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_name: str = Field(..., min_length=1)
    candidate_top_k: int = Field(ge=1)
    rerank_top_k: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    fusion: Literal["reciprocal_rank", "dbsf"] = "reciprocal_rank"


class JinaSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dense_model: str = Field(..., min_length=1)
    challenger_dense_model: str | None = None
    web_reranker_model: str = Field(..., min_length=1)


class QdrantSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    multilingual_dense_model_id: str | None = None
    sparse_model_id: str | None = None
    late_interaction_model_id: str | None = None


class LangSearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    web_search_enabled: bool = True
    fallback_reranker_model_id: str | None = None


class RetrievalProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jina: JinaSettings
    qdrant: QdrantSettings
    langsearch: LangSearchSettings


class ProviderInfrastructureConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    routing: RoutingSettings
    providers: RetrievalProviderSettings

    @classmethod
    def from_yaml(cls, path: str | Path = "config/providers.yaml") -> "ProviderInfrastructureConfig":
        file_path = Path(path)
        if not file_path.exists():
            raise ValueError(f"provider configuration does not exist: {file_path}")
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw)
