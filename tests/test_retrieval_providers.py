import asyncio
import json

import httpx

from academic_pe.core.researcher import Researcher
from academic_pe.routing import (
    JinaClient,
    LangSearchClient,
    RerankResult,
    WebSearchHit,
)


def _run(awaitable):
    return asyncio.run(awaitable)


def test_langsearch_client_uses_official_search_shape_and_normalizes_hits():
    def handler(request):
        assert request.url.path == "/v1/web-search"
        assert request.headers["authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "query": "routing evidence",
            "freshness": "noLimit",
            "summary": True,
            "count": 2,
        }
        return httpx.Response(200, json={
            "code": 200,
            "data": {"webPages": {"value": [{
                "name": "Primary source",
                "url": "https://example.test/source",
                "snippet": "short evidence",
                "summary": "long evidence",
                "datePublished": "2026-01-01",
            }]}},
        })

    client = LangSearchClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    hits = _run(client.search("routing evidence", count=2))

    assert hits == [WebSearchHit(
        title="Primary source",
        url="https://example.test/source",
        snippet="short evidence",
        summary="long evidence",
        published_at="2026-01-01",
    )]


def test_jina_client_supports_embeddings_and_reranking():
    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            assert body["model"] == "jina-embeddings-v5-text-nano"
            return httpx.Response(200, json={"data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ]})
        assert request.url.path == "/v1/rerank"
        assert body["model"] == "jina-reranker-v3"
        assert body["top_n"] == 2
        return httpx.Response(200, json={"results": [
            {"index": 1, "relevance_score": 0.9, "document": {"text": "second"}},
            {"index": 0, "relevance_score": 0.4, "document": {"text": "first"}},
        ]})

    client = JinaClient(
        api_key="test-key",
        dense_model="jina-embeddings-v5-text-nano",
        reranker_model="jina-reranker-v3",
        transport=httpx.MockTransport(handler),
    )

    assert _run(client.embed(["first", "second"])) == [[0.1, 0.2], [0.3, 0.4]]
    ranked = _run(client.rerank("query", ["first", "second"], top_n=2))
    assert ranked[0] == RerankResult(index=1, relevance_score=0.9, document="second")


def test_researcher_uses_langsearch_then_jina_order_before_crawling(tmp_path):
    class FakeSearch:
        async def search(self, _query, *, count):
            assert count == 10
            return [
                WebSearchHit(title="first", url="https://example.test/first", snippet="first"),
                WebSearchHit(title="second", url="https://example.test/second", snippet="second"),
            ]

    class FakeReranker:
        async def rerank(self, _query, _documents, *, top_n):
            assert top_n == 2
            return [RerankResult(index=1, relevance_score=0.9)]

    researcher = Researcher(
        str(tmp_path),
        web_search_client=FakeSearch(),
        reranker=FakeReranker(),
    )

    results = researcher._search_with_configured_providers("routing evidence")

    assert results == [{
        "title": "second",
        "url": "https://example.test/second",
        "snippet": "second",
    }]
