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
    api_base_url: str = "https://api.jina.ai"


class QdrantSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    cluster_id: str | None = None
    cloud_inference_enabled: bool = False
    multilingual_dense_model_id: str | None = None
    multilingual_dense_vector_size: int = Field(default=384, ge=1)
    sparse_model_id: str | None = None
    late_interaction_model_id: str | None = None
    late_interaction_vector_size: int = Field(default=96, ge=1)


class LangSearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    web_search_enabled: bool = True
    api_base_url: str = "https://api.langsearch.com"
    fallback_reranker_model_id: str | None = "langsearch-reranker-v1"
    default_freshness: Literal["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"] = "noLimit"


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
