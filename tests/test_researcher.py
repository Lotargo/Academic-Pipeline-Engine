import os
import json
import pytest
import shutil
from unittest.mock import MagicMock, patch

from academic_pe.core.researcher import (
    Researcher,
    run_researcher_pool,
    load_research_findings,
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
                "content": "Content A text detail"
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
    assert "Snippet A" in findings
    assert "Content A text detail" in findings
    
    assert "Research query: 'Topic B'" in findings
    assert "Title B" in findings
    assert "http://b.com" in findings
    assert "Snippet B" in findings
    assert "Content B text detail" in findings
