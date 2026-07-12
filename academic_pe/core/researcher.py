import asyncio
import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import logging
import re

from academic_pe.routing.retrieval import JinaClient, LangSearchClient, RetrievalProviderError, WebSearchHit

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_BLOCKED_STATUS_CODES = {401, 403, 406, 409, 418, 429, 451}
_MAX_CRAWLED_CHARS = 5000
_MIN_USEFUL_TEXT_CHARS = 180

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Connection": "keep-alive",
}

_JUNK_SELECTORS = [
    "script", "style", "noscript", "template", "svg", "canvas", "iframe",
    "nav", "footer", "header", "aside", "form", "button", "input", "select",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
    "[aria-hidden='true']", ".cookie", ".cookies", ".cookie-banner", ".cookiebar",
    ".newsletter", ".subscribe", ".subscription", ".advertisement", ".ad", ".ads",
    ".social", ".share", ".sharing", ".breadcrumb", ".breadcrumbs", ".related",
    ".comments", ".comment", ".promo", ".modal", ".overlay", ".popup",
]

_JUNK_LINE_PATTERNS = [
    r"^(accept|agree|reject|manage|allow|decline)( all)?( cookies)?$",
    r"^(sign in|log in|subscribe|newsletter|advertisement|skip to content)$",
    r"^(share|tweet|copy link|print|read more|learn more)$",
    r"^(privacy policy|terms of use|cookie policy|all rights reserved)$",
    r"^\s*(menu|close|open|search)\s*$",
]

_BLOCKED_TEXT_PATTERNS = [
    r"captcha",
    r"cloudflare",
    r"access denied",
    r"enable javascript",
    r"verify you are human",
    r"checking your browser",
    r"too many requests",
    r"unusual traffic",
]


def _resolve_duckduckgo_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/"):
        href = "https://duckduckgo.com" + href

    parsed = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query_params:
        return query_params["uddg"][0]
    return href


def _compact_text(text: str, limit: int = 700) -> str:
    compacted = " ".join(str(text or "").split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 1].rstrip() + "..."


def _browser_headers(referer: str = "https://duckduckgo.com/") -> dict:
    headers = dict(_BROWSER_HEADERS)
    headers["Referer"] = referer
    return headers


def _reader_url(url: str) -> str:
    return "https://r.jina.ai/" + url


def _is_probably_blocked_response(response) -> bool:
    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code in _BLOCKED_STATUS_CODES:
        return True
    text = str(getattr(response, "text", "") or "")[:5000].lower()
    return any(re.search(pattern, text) for pattern in _BLOCKED_TEXT_PATTERNS)


def _is_junk_line(line: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(line or "")).strip()
    if len(normalized) < 3:
        return True
    if len(normalized) <= 80 and any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _JUNK_LINE_PATTERNS):
        return True
    if normalized.count("|") >= 8 or normalized.count("•") >= 8:
        return True
    return False


def _clean_lines(text: str, *, limit: int = _MAX_CRAWLED_CHARS) -> str:
    lines = []
    seen = set()
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if _is_junk_line(line):
            continue
        fingerprint = line.casefold()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        lines.append(line)
        if sum(len(item) + 1 for item in lines) >= limit:
            break
    return "\n".join(lines)[:limit].strip()


def _extract_clean_text(html: str, *, limit: int = _MAX_CRAWLED_CHARS) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.select(",".join(_JUNK_SELECTORS)):
        tag.decompose()

    candidates = []
    for selector in ["article", "main", "[role='main']", ".article", ".post", ".content", "#content"]:
        for node in soup.select(selector):
            text = _clean_lines(node.get_text(separator="\n"), limit=limit)
            if len(text) >= _MIN_USEFUL_TEXT_CHARS:
                candidates.append(text)

    if candidates:
        return max(candidates, key=len)[:limit].strip()
    return _clean_lines(soup.get_text(separator="\n"), limit=limit)


def _fetch_reader_text(url: str, *, headers: dict) -> str:
    reader_headers = {
        **headers,
        "Accept": "text/plain, text/markdown;q=0.9, */*;q=0.5",
        "X-Return-Format": "markdown",
    }
    response = _get_with_retries(_reader_url(url), headers=reader_headers, timeout=25, attempts=2)
    if response.ok and not _is_probably_blocked_response(response):
        return _clean_lines(response.text, limit=_MAX_CRAWLED_CHARS)
    return ""


def _fetch_url_text(url: str, *, headers: dict) -> tuple[str, str]:
    response = _get_with_retries(url, headers=headers, timeout=15, attempts=3)
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).lower()
    if response.ok and not _is_probably_blocked_response(response):
        if "text/plain" in content_type or "markdown" in content_type:
            content = _clean_lines(response.text, limit=_MAX_CRAWLED_CHARS)
        else:
            content = _extract_clean_text(response.text, limit=_MAX_CRAWLED_CHARS)
        if content:
            return content, "direct"

    reader_text = _fetch_reader_text(url, headers=headers)
    if reader_text:
        return reader_text, "reader"
    if response.ok:
        return _extract_clean_text(response.text, limit=_MAX_CRAWLED_CHARS), "direct_low_confidence"
    return f"Error: Failed to fetch (Status {response.status_code})", "error"


def _get_with_retries(
    url: str,
    *,
    headers: dict,
    timeout: int,
    attempts: int = 2,
    backoff_seconds: float = 0.5,
):
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            return response
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            raise
    if last_error:
        raise last_error


class Researcher:
    def __init__(
        self,
        run_dir: str,
        *,
        web_search_client: LangSearchClient | None = None,
        reranker: JinaClient | None = None,
    ):
        self.run_dir = run_dir
        self.research_dir = os.path.join(run_dir, "research")
        os.makedirs(self.research_dir, exist_ok=True)
        self.web_search_client = web_search_client
        self.reranker = reranker

    def search_and_crawl(self, query: str, idx: int) -> dict:
        """
        Search with LangSearch when configured, otherwise DuckDuckGo; crawl the top matches.
        """
        logger.info("Researcher searching for query: '%s'", query)

        headers = _browser_headers()

        # Add a polite delay to respect the site's rate limits
        time.sleep(1.0)

        results = self._search_with_configured_providers(query)
        if not results:
            results = _search_duckduckgo(query, headers=headers)

        # Crawl top matches in this query.
        findings = []
        for r in results:
            logger.info("Crawling URL: %s", r["url"])
            time.sleep(1.0)  # Rate limit/polite scraping delay
            content = ""
            extraction_method = "direct"
            try:
                content, extraction_method = _fetch_url_text(r["url"], headers=_browser_headers(r["url"]))
            except Exception as e:
                logger.warning("Error crawling webpage %s: %s", r["url"], e)
                content = f"Error crawling webpage: {e}"
                extraction_method = "error"

            findings.append({
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
                "content": content,
                "extraction_method": extraction_method,
            })

        # Save findings as a local JSON file in the run/research directory
        filename = f"query_{idx}.json"
        filepath = os.path.join(self.research_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "query": query,
                    "results": findings
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to write research results to file %s: %s", filepath, e)

        return {
            "query": query,
            "filepath": filepath,
            "results": findings
        }

    def _search_with_configured_providers(self, query: str) -> list[dict]:
        if self.web_search_client is None:
            return []
        try:
            hits = asyncio.run(self.web_search_client.search(query, count=10))
        except (RetrievalProviderError, ValueError) as exc:
            logger.warning("LangSearch failed for '%s'; using local fallback. Error: %s", query, exc)
            return []
        if not hits:
            return []

        ranked_hits = self._rerank_hits(query, hits)
        return [
            {
                "title": hit.title,
                "url": hit.url,
                "snippet": hit.summary or hit.snippet,
            }
            for hit in ranked_hits[:3]
        ]

    def _rerank_hits(self, query: str, hits: list[WebSearchHit]) -> list[WebSearchHit]:
        if self.reranker is None:
            return hits
        try:
            ranked = asyncio.run(self.reranker.rerank(
                query,
                [hit.rerank_text for hit in hits],
                top_n=min(3, len(hits)),
            ))
        except (RetrievalProviderError, ValueError) as exc:
            logger.warning("Jina rerank failed for '%s'; preserving LangSearch order. Error: %s", query, exc)
            return hits
        selected = [hits[result.index] for result in ranked if result.index < len(hits)]
        return selected or hits


def run_researcher_pool(
    queries: list[str],
    run_dir: str,
    *,
    web_search_client: LangSearchClient | None = None,
    reranker: JinaClient | None = None,
) -> list[dict]:
    """
    Spawns a pool of parallel search agents to search and crawl websites.
    """
    researcher = Researcher(
        run_dir,
        web_search_client=web_search_client,
        reranker=reranker,
    )
    results = []
    # Spawn thread pool to run parallel queries
    with ThreadPoolExecutor(max_workers=min(3, len(queries) or 1)) as executor:
        futures = {executor.submit(researcher.search_and_crawl, q, i): q for i, q in enumerate(queries)}
        for future in as_completed(futures):
            q = futures[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as e:
                logger.error("Researcher worker failed for query '%s': %s", q, e)
    return results


def _search_duckduckgo(query: str, *, headers: dict) -> list[dict]:
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
        res = _get_with_retries(url, headers=headers, timeout=15, attempts=3)
        if res.ok and not _is_probably_blocked_response(res):
            soup = BeautifulSoup(res.text, "html.parser")
            for result_div in soup.find_all("div", class_=lambda x: x and "result" in x):
                if "results_links" not in result_div.get("class", []):
                    continue
                result_a = result_div.find("a", class_="result__a")
                display_url_a = result_div.find("a", class_="result__url")
                snippet_a = result_div.find("a", class_="result__snippet")
                link_a = result_a or display_url_a
                if link_a:
                    title = (result_a or link_a).get_text(strip=True)
                    href = link_a.get("href", "")
                    actual_url = _resolve_duckduckgo_url(href)
                    if not actual_url.startswith(("http://", "https://")):
                        continue

                    results.append({
                        "title": title,
                        "url": actual_url,
                        "snippet": snippet_a.get_text(strip=True) if snippet_a else "",
                    })
                    if len(results) >= 3:
                        break
    except Exception as exc:
        logger.error("DuckDuckGo search failed for '%s': %s", query, exc)
    return results


def load_research_findings(run_dir: str) -> str:
    """
    Read temporary search files inside the run/research directory
    and format them into a summarized report for the Planner agent context.
    """
    research_dir = os.path.join(run_dir, "research")
    if not os.path.exists(research_dir):
        return ""

    summary_parts = []
    try:
        filenames = sorted(os.listdir(research_dir))
    except Exception as e:
        logger.error("Failed to list research directory %s: %s", research_dir, e)
        return ""

    for filename in filenames:
        if filename.endswith(".json"):
            filepath = os.path.join(research_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                query = data.get("query")
                results = data.get("results", [])

                part = f"### Research query: '{query}'\n"
                for idx, r in enumerate(results):
                    title = _compact_text(r.get("title", ""), limit=160)
                    url = str(r.get("url", "")).strip()
                    snippet = _compact_text(r.get("snippet", ""), limit=350)
                    excerpt = _compact_text(r.get("content", ""), limit=700)
                    extraction_method = str(r.get("extraction_method", "")).strip()
                    part += f"Source {idx+1}: {title}\n"
                    part += f"URL: {url}\n"
                    if extraction_method:
                        part += f"Extraction: {extraction_method}\n"
                    if snippet:
                        part += f"Snippet: {snippet}\n"
                    if excerpt and not excerpt.lower().startswith("error"):
                        part += f"Relevant excerpt: {excerpt}\n"
                    part += "\n"
                summary_parts.append(part)
            except Exception as e:
                logger.warning("Failed to load research file %s: %s", filename, e)

    return "\n\n".join(summary_parts)
