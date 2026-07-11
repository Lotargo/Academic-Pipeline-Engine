import os
import json
import pytest
import shutil
from unittest.mock import MagicMock, patch

from academic_pe.agents.researcher import ResearcherAgent
from academic_pe.core.config import AgentConfig
from academic_pe.core.llm import MockProvider
from academic_pe.core.researcher import (
    Researcher,
    run_researcher_pool,
    load_research_findings,
    _extract_clean_text,
    _fetch_url_text,
)

TEMP_RUN_DIR = "tests_run_dir"


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup: remove temp dir if exists
    if os.path.exists(TEMP_RUN_DIR):
        shutil.rmtree(TEMP_RUN_DIR)
    yield
    # Teardown: clean up temp dir
    if os.path.exists(TEMP_RUN_DIR):
        shutil.rmtree(TEMP_RUN_DIR)


def test_researcher_initialization():
    researcher = Researcher(TEMP_RUN_DIR)
    assert researcher.run_dir == TEMP_RUN_DIR
    assert os.path.exists(researcher.research_dir)


@patch("academic_pe.agents.researcher.load_research_findings", return_value="Loaded findings")
@patch("academic_pe.agents.researcher.run_researcher_pool")
def test_researcher_agent_runs_deterministic_research(mock_run_pool, mock_load):
    cfg = AgentConfig(
        role="Researcher",
        model="deterministic-search",
        temperature=0.0,
        system_prompt="Researcher.",
        agent_type="researcher",
    )
    agent = ResearcherAgent(cfg, MockProvider())

    findings = agent.run_research([" query A ", "", "query B"], TEMP_RUN_DIR)

    assert findings == "Loaded findings"
    mock_run_pool.assert_called_once_with(["query A", "query B"], TEMP_RUN_DIR)
    mock_load.assert_called_once_with(TEMP_RUN_DIR)


@patch("academic_pe.agents.researcher.load_research_findings", return_value="Raw finding with https://example.com")
@patch("academic_pe.agents.researcher.run_researcher_pool")
def test_researcher_agent_curates_findings_with_llm_for_real_provider(mock_run_pool, mock_load):
    class CapturingProvider:
        def __init__(self):
            self.calls = []

        def generate(self, system_prompt, user_prompt, model, temperature, on_delta=None):
            self.calls.append((system_prompt, user_prompt, model, temperature))
            return "Curated finding: Example source - https://example.com"

    cfg = AgentConfig(
        role="Researcher",
        provider="zen",
        model="research-model",
        temperature=0.1,
        system_prompt="Curate source findings.",
        agent_type="researcher",
    )
    provider = CapturingProvider()
    agent = ResearcherAgent(cfg, provider)

    findings = agent.run_research([" query A "], TEMP_RUN_DIR)

    assert findings == "Curated finding: Example source - https://example.com"
    mock_run_pool.assert_called_once_with(["query A"], TEMP_RUN_DIR)
    mock_load.assert_called_once_with(TEMP_RUN_DIR)
    assert provider.calls
    assert "[Raw Findings]" in provider.calls[0][1]
    assert "Raw finding with https://example.com" in provider.calls[0][1]


@patch("academic_pe.agents.researcher.load_research_findings", return_value="Raw findings")
@patch("academic_pe.agents.researcher.run_researcher_pool")
def test_researcher_agent_exposes_structured_curation_claims(mock_run_pool, mock_load):
    class StructuredProvider:
        def generate(self, *args, **kwargs):
            return json.dumps({
                "notes": "Use the official report.",
                "claims": [{
                    "text": "The baseline increased.",
                    "source_urls": ["https://example.com/report"],
                    "status": "supported",
                    "section_owner": "analysis",
                }],
            })

    cfg = AgentConfig(role="Researcher", provider="zen", model="research", temperature=0.0, system_prompt="Researcher")
    agent = ResearcherAgent(cfg, StructuredProvider())

    assert agent.run_research(["query"], TEMP_RUN_DIR) == "Use the official report."
    assert agent.last_curation is not None
    assert agent.last_curation.claims[0].source_urls == ["https://example.com/report"]


@patch("requests.get")
def test_search_and_crawl(mock_get):
    # Mock DuckDuckGo response HTML
    ddg_html = """
    <html>
      <body>
        <div class="result results_links">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage1">Example Page 1</a>
          <a class="result__url" href="https://example.com/page1">example.com/page1</a>
          <a class="result__snippet">This is snippet 1.</a>
        </div>
        <div class="result results_links">
          <a class="result__a" href="https://example.com/page2">Example Page 2</a>
          <a class="result__url" href="https://example.com/page2">example.com/page2</a>
          <a class="result__snippet">This is snippet 2.</a>
        </div>
      </body>
    </html>
    """
    
    mock_ddg_res = MagicMock()
    mock_ddg_res.ok = True
    mock_ddg_res.text = ddg_html
    
    # Mock page 1 content
    page1_html = "<html><body><h1>Page 1 Header</h1><p>Page 1 actual content paragraphs.</p></body></html>"
    mock_page1_res = MagicMock()
    mock_page1_res.ok = True
    mock_page1_res.text = page1_html
    
    # Mock page 2 content
    page2_html = "<html><body><style>body { color: red; }</style><script>alert('x');</script><p>Page 2 actual content.</p></body></html>"
    mock_page2_res = MagicMock()
    mock_page2_res.ok = True
    mock_page2_res.text = page2_html
    
    mock_get.side_effect = [mock_ddg_res, mock_page1_res, mock_page2_res]
    
    researcher = Researcher(TEMP_RUN_DIR)
    data = researcher.search_and_crawl("test query", 0)
    
    assert data["query"] == "test query"
    assert len(data["results"]) == 2
    
    # Verify first page crawled text
    r0 = data["results"][0]
    assert r0["title"] == "Example Page 1"
    assert r0["url"] == "https://example.com/page1"
    assert r0["snippet"] == "This is snippet 1."
    assert "Page 1 Header" in r0["content"]
    assert "Page 1 actual content" in r0["content"]
    
    # Verify script/style tags were removed in second page
    r1 = data["results"][1]
    assert "alert" not in r1["content"]
    assert "color: red" not in r1["content"]
    assert "Page 2 actual content" in r1["content"]
    
    # Check if file was saved
    saved_file = os.path.join(researcher.research_dir, "query_0.json")
    assert os.path.exists(saved_file)
    with open(saved_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
        assert saved_data["query"] == "test query"
        assert len(saved_data["results"]) == 2


@patch("requests.get")
def test_search_and_crawl_connection_errors(mock_get):
    # Mock DDG OK but target pages raising errors
    ddg_html = """
    <html>
      <body>
        <div class="result results_links">
          <a class="result__a" href="https://example.com/page1">Example Page 1</a>
          <a class="result__snippet">Snippet 1.</a>
        </div>
      </body>
    </html>
    """
    mock_ddg_res = MagicMock()
    mock_ddg_res.ok = True
    mock_ddg_res.text = ddg_html
    
    # Mock error for crawling
    mock_get.side_effect = [mock_ddg_res, Exception("Connection refused")]
    
    researcher = Researcher(TEMP_RUN_DIR)
    data = researcher.search_and_crawl("test query error", 0)
    
    assert len(data["results"]) == 1
    assert "Error crawling webpage" in data["results"][0]["content"]


def test_extract_clean_text_removes_boilerplate_and_prefers_article():
    html = """
    <html>
      <body>
        <nav>Menu Search Subscribe</nav>
        <div class="cookie-banner">Accept all cookies</div>
        <article>
          <h1>Important Research Result</h1>
          <p>The source reports a concrete finding with a date, method, and limitation.</p>
          <p>The finding is relevant to the planning agent and should survive extraction.</p>
        </article>
        <footer>Privacy Policy All rights reserved</footer>
      </body>
    </html>
    """

    text = _extract_clean_text(html)

    assert "Important Research Result" in text
    assert "concrete finding" in text
    assert "Accept all cookies" not in text
    assert "Privacy Policy" not in text
    assert "Menu Search Subscribe" not in text


@patch("academic_pe.core.researcher._get_with_retries")
def test_fetch_url_text_uses_reader_fallback_for_blocked_page(mock_get):
    blocked_res = MagicMock()
    blocked_res.ok = False
    blocked_res.status_code = 403
    blocked_res.text = "Access denied"
    blocked_res.headers = {"content-type": "text/html"}

    reader_res = MagicMock()
    reader_res.ok = True
    reader_res.status_code = 200
    reader_res.text = "# Reader title\n\nClean markdown text from the page."
    reader_res.headers = {"content-type": "text/plain"}

    mock_get.side_effect = [blocked_res, reader_res]

    text, method = _fetch_url_text("https://example.com/blocked", headers={})

    assert method == "reader"
    assert "Clean markdown text" in text
    assert mock_get.call_args_list[1].args[0] == "https://r.jina.ai/https://example.com/blocked"


@patch("requests.get")
def test_run_researcher_pool(mock_get):
    ddg_html = """<html><body></body></html>"""
    mock_res = MagicMock()
    mock_res.ok = True
    mock_res.text = ddg_html
    mock_get.return_value = mock_res
    
    results = run_researcher_pool(["query A", "query B"], TEMP_RUN_DIR)
    assert len(results) == 2
    assert any(r["query"] == "query A" for r in results)
    assert any(r["query"] == "query B" for r in results)


@patch("academic_pe.core.researcher.time.sleep", return_value=None)
@patch("requests.get")
def test_search_retries_blocked_duckduckgo_page_and_handles_empty_results(mock_get, mock_sleep):
    blocked_res = MagicMock()
    blocked_res.ok = False
    blocked_res.status_code = 429
    blocked_res.text = "Too Many Requests"

    empty_res = MagicMock()
    empty_res.ok = True
    empty_res.status_code = 200
    empty_res.text = "<html><body>No results here</body></html>"

    mock_get.side_effect = [blocked_res, empty_res]

    researcher = Researcher(TEMP_RUN_DIR)
    data = researcher.search_and_crawl("blocked query", 0)

    assert data["query"] == "blocked query"
    assert data["results"] == []
    assert mock_get.call_count == 2


@patch("academic_pe.core.researcher.time.sleep", return_value=None)
@patch("requests.get")
def test_search_retries_retryable_target_page_status(mock_get, mock_sleep):
    ddg_html = """
    <html>
      <body>
        <div class="result results_links">
          <a class="result__a" href="https://example.com/retry">Retry Source</a>
          <a class="result__snippet">Retry snippet.</a>
        </div>
      </body>
    </html>
    """
    ddg_res = MagicMock()
    ddg_res.ok = True
    ddg_res.status_code = 200
    ddg_res.text = ddg_html

    retryable_res = MagicMock()
    retryable_res.ok = False
    retryable_res.status_code = 503
    retryable_res.text = "Service unavailable"

    page_res = MagicMock()
    page_res.ok = True
    page_res.status_code = 200
    page_res.text = "<html><body><p>Recovered page content.</p></body></html>"

    mock_get.side_effect = [ddg_res, retryable_res, page_res]

    researcher = Researcher(TEMP_RUN_DIR)
    data = researcher.search_and_crawl("retry query", 0)

    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Retry Source"
    assert "Recovered page content" in data["results"][0]["content"]
    assert mock_get.call_count == 3


def test_load_research_findings():
    researcher = Researcher(TEMP_RUN_DIR)
    # Manually create mock json results
    results_a = {
        "query": "Topic A",
        "results": [
            {
                "title": "Title A",
                "url": "http://a.com",
                "snippet": "Snippet A",
                "content": "Content A text detail",
                "extraction_method": "reader",
            }
        ]
    }
    results_b = {
        "query": "Topic B",
        "results": [
            {
                "title": "Title B",
                "url": "http://b.com",
                "snippet": "Snippet B",
                "content": "Content B text detail"
            }
        ]
    }
    
    with open(os.path.join(researcher.research_dir, "query_0.json"), "w", encoding="utf-8") as f:
        json.dump(results_a, f)
    with open(os.path.join(researcher.research_dir, "query_1.json"), "w", encoding="utf-8") as f:
        json.dump(results_b, f)
        
    findings = load_research_findings(TEMP_RUN_DIR)
    assert "Research query: 'Topic A'" in findings
    assert "Title A" in findings
    assert "http://a.com" in findings
    assert "Extraction: reader" in findings
    assert "Snippet A" in findings
    assert "Relevant excerpt: Content A text detail" in findings
    
    assert "Research query: 'Topic B'" in findings
    assert "Title B" in findings
    assert "http://b.com" in findings
    assert "Snippet B" in findings
    assert "Relevant excerpt: Content B text detail" in findings


def test_load_research_findings_compacts_long_content_and_skips_error_excerpt():
    researcher = Researcher(TEMP_RUN_DIR)
    long_content = " ".join(["detail"] * 300)
    results = {
        "query": "Topic",
        "results": [
            {
                "title": "Long Source",
                "url": "http://source.com",
                "snippet": "Snippet",
                "content": long_content,
            },
            {
                "title": "Failed Source",
                "url": "http://failed.com",
                "snippet": "Snippet",
                "content": "Error crawling webpage: timeout",
            },
        ],
    }

    with open(os.path.join(researcher.research_dir, "query_0.json"), "w", encoding="utf-8") as f:
        json.dump(results, f)

    findings = load_research_findings(TEMP_RUN_DIR)

    assert "URL: http://source.com" in findings
    assert "Relevant excerpt:" in findings
    assert len(findings) < len(long_content)
    assert "Error crawling webpage: timeout" not in findings
