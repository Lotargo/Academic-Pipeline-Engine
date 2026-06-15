# OCR & Research Smoke Notes

Date: 2026-06-16
Commit/branch: local working tree
Secrets: mistral configured; keys not recorded.

## Runner

Command format:

```powershell
poetry run python scripts/ocr_research_smoke_runner.py web_search_off_standard_pipeline
poetry run python scripts/ocr_research_smoke_runner.py web_search_on_researcher_boundary
poetry run python scripts/ocr_research_smoke_runner.py reference_attachment_planner_only
poetry run python scripts/ocr_research_smoke_runner.py uploaded_continuation_source
poetry run python scripts/ocr_research_smoke_runner.py mistral_ocr_direct
poetry run python scripts/ocr_research_smoke_runner.py real_llm_web_research
```

The runner executes exactly one scenario per command, appends a concise result to this note, and writes flushed JSONL logs under `exports/_smoke_ocr_research/`. Prompts, secrets, and full generated documents are intentionally not logged.

## Run 2026-06-16T06:10 - OCR/Research Smoke Set

Result: PASS

- `web_search_off_standard_pipeline`: PASS. Researcher was not called when the activator was off, and Planner still created the document plan. Log: `exports/_smoke_ocr_research/20260616_061019/web_search_off_standard_pipeline/stage_log.jsonl`
- `web_search_on_researcher_boundary`: PASS. Researcher was called once with the planned query; raw findings reached Planner but did not reach Writer. Log: `exports/_smoke_ocr_research/20260616_061023/web_search_on_researcher_boundary/stage_log.jsonl`
- `reference_attachment_planner_only`: PASS. Raw reference material reached Planner but did not reach Writer; Writer received the curated plan. Log: `exports/_smoke_ocr_research/20260616_061026/reference_attachment_planner_only/stage_log.jsonl`
- `uploaded_continuation_source`: PASS. Uploaded Markdown split into source sections and terminal references were recognized. Log: `exports/_smoke_ocr_research/20260616_061030/uploaded_continuation_source/stage_log.jsonl`
- `mistral_ocr_direct`: PASS. Generated PDF was OCR'd through Mistral and the unique marker survived. Log: `exports/_smoke_ocr_research/20260616_061034/mistral_ocr_direct/stage_log.jsonl`

## Run 2026-06-16T06:13:46 - real_llm_web_research

Date: 2026-06-16
Commit/branch: local working tree
Scenario: Real Planner/Writer LLM web research smoke (real_llm_web_research)
Expected checks: configured real Planner/Writer secrets are available; Researcher returns non-empty search findings; Planner creates a source-aware plan; Writer drafts from planner-curated context without raw reference leakage
Stage log: see exports/_smoke_ocr_research JSONL log for flushed checkpoints.
Result: PASS
Elapsed: 95.0s
Observed issue: none
Follow-up: exports\_smoke_ocr_research\20260616_061346\real_llm_web_research\stage_log.jsonl

Details: real Planner/Writer calls completed with `writer=zen/deepseek-v4-flash-free`, `planner=zen/big-pickle`, and `researcher=mock/deterministic-search`. Search findings were non-empty (`12125` chars), Planner produced a source-aware plan (`3051` chars), and Writer produced a brief (`1163` chars) without leaking the raw reference marker.
