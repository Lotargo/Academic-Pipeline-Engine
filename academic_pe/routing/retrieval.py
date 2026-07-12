from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from academic_pe.core.secrets import SecretResolver
from academic_pe.routing.config import ProviderInfrastructureConfig


class RetrievalProviderError(RuntimeError):
    """A provider response that cannot safely be used for retrieval."""


class WebSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    snippet: str = ""
    summary: str = ""
    published_at: str | None = None

    @property
    def rerank_text(self) -> str:
        return self.summary or self.snippet or self.title


class RerankResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    relevance_score: float
    document: str | None = None


class LangSearchClient:
    """Typed LangSearch Web Search client; no key or response body is logged."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.langsearch.com",
        freshness: str = "noLimit",
        timeout_seconds: int = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("LangSearch API key is not configured")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._freshness = freshness
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_provider_config(
        cls,
        configuration: ProviderInfrastructureConfig,
        *,
        secret_resolver: SecretResolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "LangSearchClient":
        settings = configuration.providers.langsearch
        if not settings.web_search_enabled:
            raise ValueError("LangSearch web search is disabled")
        api_key = (secret_resolver or SecretResolver()).resolve("LANGSEARCH_API_KEY")
        if not api_key:
            raise ValueError("LangSearch API key is not configured")
        return cls(
            api_key=api_key,
            base_url=settings.api_base_url,
            freshness=settings.default_freshness,
            timeout_seconds=configuration.routing.timeout_seconds,
            transport=transport,
        )

    async def search(self, query: str, *, count: int = 10) -> list[WebSearchHit]:
        if not query.strip():
            return []
        if not 1 <= count <= 10:
            raise ValueError("LangSearch count must be between 1 and 10")
        payload = await self._post(
            "/v1/web-search",
            {
                "query": query,
                "freshness": self._freshness,
                "summary": True,
                "count": count,
            },
        )
        if payload.get("code") != 200:
            raise RetrievalProviderError("LangSearch returned an unsuccessful response")
        data = payload.get("data")
        pages = data.get("webPages") if isinstance(data, dict) else None
        values = pages.get("value") if isinstance(pages, dict) else None
        if not isinstance(values, list):
            raise RetrievalProviderError("LangSearch response has no web pages")

        hits: list[WebSearchHit] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            url = value.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            title = value.get("name")
            if not isinstance(title, str) or not title.strip():
                title = url
            hits.append(WebSearchHit(
                title=title.strip(),
                url=url,
                snippet=_text(value.get("snippet")),
                summary=_text(value.get("summary")),
                published_at=_optional_text(value.get("datePublished")),
            ))
        return hits

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post(path, json=body)
            except httpx.HTTPError as exc:
                raise RetrievalProviderError("LangSearch request failed") from exc
        if response.is_error:
            raise RetrievalProviderError(f"LangSearch returned HTTP {response.status_code}")
        return _json_object(response, "LangSearch")


class JinaClient:
    """Typed Jina embeddings and reranking client for routing and web research."""

    def __init__(
        self,
        *,
        api_key: str,
        dense_model: str,
        reranker_model: str,
        base_url: str = "https://api.jina.ai",
        timeout_seconds: int = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Jina API key is not configured")
        self._api_key = api_key
        self._dense_model = dense_model
        self._reranker_model = reranker_model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_provider_config(
        cls,
        configuration: ProviderInfrastructureConfig,
        *,
        secret_resolver: SecretResolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "JinaClient":
        settings = configuration.providers.jina
        api_key = (secret_resolver or SecretResolver()).resolve("JINA_API_KEY")
        if not api_key:
            raise ValueError("Jina API key is not configured")
        return cls(
            api_key=api_key,
            dense_model=settings.dense_model,
            reranker_model=settings.web_reranker_model,
            base_url=settings.api_base_url,
            timeout_seconds=configuration.routing.timeout_seconds,
            transport=transport,
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        clean_texts = [text for text in texts if text.strip()]
        if not clean_texts:
            return []
        payload = await self._post("/v1/embeddings", {
            "model": self._dense_model,
            "input": clean_texts,
            "normalized": True,
        })
        raw_data = payload.get("data")
        if not isinstance(raw_data, list):
            raise RetrievalProviderError("Jina embeddings response has no data")
        by_index: dict[int, list[float]] = {}
        for item in raw_data:
            if not isinstance(item, dict) or not isinstance(item.get("index"), int):
                continue
            embedding = item.get("embedding")
            if isinstance(embedding, list) and all(isinstance(value, (int, float)) for value in embedding):
                by_index[item["index"]] = [float(value) for value in embedding]
        if set(by_index) != set(range(len(clean_texts))):
            raise RetrievalProviderError("Jina embeddings response is incomplete")
        return [by_index[index] for index in range(len(clean_texts))]

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int | None = None,
    ) -> list[RerankResult]:
        clean_documents = [document for document in documents if document.strip()]
        if not query.strip() or not clean_documents:
            return []
        limit = min(top_n or len(clean_documents), len(clean_documents))
        payload = await self._post("/v1/rerank", {
            "model": self._reranker_model,
            "query": query,
            "documents": clean_documents,
            "top_n": limit,
            "return_documents": True,
        })
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise RetrievalProviderError("Jina rerank response has no results")
        results: list[RerankResult] = []
        for item in raw_results:
            if not isinstance(item, dict) or not isinstance(item.get("index"), int):
                continue
            score = item.get("relevance_score", item.get("score"))
            if not isinstance(score, (int, float)):
                continue
            document = item.get("document")
            if isinstance(document, dict):
                document = document.get("text")
            results.append(RerankResult(
                index=item["index"],
                relevance_score=float(score),
                document=document if isinstance(document, str) else None,
            ))
        if not results:
            raise RetrievalProviderError("Jina rerank response has no valid results")
        return sorted(results, key=lambda item: (-item.relevance_score, item.index))

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post(path, json=body)
            except httpx.HTTPError as exc:
                raise RetrievalProviderError("Jina request failed") from exc
        if response.is_error:
            raise RetrievalProviderError(f"Jina returned HTTP {response.status_code}")
        return _json_object(response, "Jina")


def _json_object(response: httpx.Response, provider: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RetrievalProviderError(f"{provider} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RetrievalProviderError(f"{provider} returned an invalid JSON object")
    return payload


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None
