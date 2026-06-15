import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import logging

logger = logging.getLogger(__name__)


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


class Researcher:
    def __init__(self, run_dir: str):
        self.run_dir = run_dir
        self.research_dir = os.path.join(run_dir, "research")
        os.makedirs(self.research_dir, exist_ok=True)

    def search_and_crawl(self, query: str, idx: int) -> dict:
        """
        Run DuckDuckGo search for a query, crawl top 3 matches, and write findings to a file.
        """
        logger.info("Researcher searching for query: '%s'", query)

        # Simulate browser request headers to avoid bot detection blockages
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://duckduckgo.com/",
            "Connection": "keep-alive"
        }

        # Add a polite delay to respect the site's rate limits
        time.sleep(1.0)

        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            res = requests.get(url, headers=headers, timeout=15)
            if res.ok:
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

                        snippet = snippet_a.get_text(strip=True) if snippet_a else ""
                        results.append({
                            "title": title,
                            "url": actual_url,
                            "snippet": snippet
                        })
                        if len(results) >= 3:  # crawl top 3 matches
                            break
        except Exception as e:
            logger.error("DuckDuckGo search failed for '%s': %s", query, e)

        # Crawl top matches in this query
        findings = []
        for r in results:
            logger.info("Crawling URL: %s", r["url"])
            time.sleep(1.0)  # Rate limit/polite scraping delay
            content = ""
            try:
                c_res = requests.get(r["url"], headers=headers, timeout=12)
                if c_res.ok:
                    c_soup = BeautifulSoup(c_res.text, "html.parser")
                    # Clean up junk elements
                    for tag in c_soup(["script", "style", "nav", "footer", "header", "aside"]):
                        tag.decompose()
                    raw_text = c_soup.get_text(separator="\n")
                    lines = (line.strip() for line in raw_text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    # Clamp crawled content to 5,000 characters to prevent excessive context size
                    content = "\n".join(chunk for chunk in chunks if chunk)[:5000]
                else:
                    content = f"Error: Failed to fetch (Status {c_res.status_code})"
            except Exception as e:
                logger.warning("Error crawling webpage %s: %s", r["url"], e)
                content = f"Error crawling webpage: {e}"

            findings.append({
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
                "content": content
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


def run_researcher_pool(queries: list[str], run_dir: str) -> list[dict]:
    """
    Spawns a pool of parallel search agents to search and crawl websites.
    """
    researcher = Researcher(run_dir)
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
                    part += f"Source {idx+1}: {title}\n"
                    part += f"URL: {url}\n"
                    if snippet:
                        part += f"Snippet: {snippet}\n"
                    if excerpt and not excerpt.lower().startswith("error"):
                        part += f"Relevant excerpt: {excerpt}\n"
                    part += "\n"
                summary_parts.append(part)
            except Exception as e:
                logger.warning("Failed to load research file %s: %s", filename, e)

    return "\n\n".join(summary_parts)
