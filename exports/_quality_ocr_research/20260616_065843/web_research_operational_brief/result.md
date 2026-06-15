# Source-aware operational brief

Scenario: `web_research_operational_brief`
Elapsed: 162.4s
Config: writer=zen/deepseek-v4-flash-free, planner=zen/big-pickle, researcher=zen/big-pickle
Search findings chars: 4944

## Rubric
- [ ] uses current/source-aware context without fabricating unsupported certainty
- [ ] reads as a coherent user-facing brief rather than a plan dump
- [ ] includes practical workflow steps and at least one limitation
- [ ] does not leak QUALITY_RAW_REFERENCE_MARKER
- [ ] does not expose internal labels such as red_flags, exposition, or development notes

## Document Plan
## Writing Plan for the Operational Brief

### Core Intent / Central Claim
The brief advances that systematically pairing AI OCR digitization with purpose-driven web research yields academically rigorous drafts more efficiently than either method alone. The workflow is actionable, not theoretical.

### Section-by-Section Goals
 - **Opening (no heading)** - Framing: the difficulty of synthesising non-digital sources with the latest online context; the value of a unified pipeline. 
 - **Workflow Steps (subheading: "Workflow")** - Three sequential stages: 
 1. *Digitise with AI OCR* - Use tools such as Nutrient SDK (www.nutrient.io) or ML-based OCR (IJSAT, 2025 https://www.ijsat.org/papers/2025/1/1890.pdf) to extract structured text from scans. 
 2. *Gather current context* - Leverage academic search engines, citation generators (e.g., Scribbr, www.scribbr.com/citation/generator/), and AI-assisted discovery (SCI Journal, 2026 https://www.scijournal.org/articles/best-academic-writing-tools; Ponder.ing, 2026 https://ponder.ing/blog/ai-tools-for-academic-research-writing). 
 3. *Integrate systematically* - Map extracted facts against web-gathered context, then weave both into a draft while tracking provenance inline. 
 - **Limitation (subheading: "Limitation")** - Acknowledge that OCR quality (especially on complex layouts or degraded originals) can introduce errors that propagate into the draft if not reviewed (IJSAT). 
 - **Closing (optional subheading: "Summary")** - Recapitulate that the integration adds credibility and completeness without requiring a separate References section.

### Headings Overview
| Type | Content | Notes |
|------|---------|-------|
| **Final-document heading** | `Operational Brief` (or `1. Brief` per config) | Must be rendered; no "References", "Literature Review", or "Methodology" |
| **Final-document sub-headings** | `Workflow`, `Limitation` | Optional `Summary` |
| **Internal-only blocks** | None | All planning notes stay outside the final prose |

### Terminology and Style Choices
 - **Consistent terms:** 
 - "AI OCR" (not "OCR with AI" or "intelligent OCR") 
 - "web research tools" as a collective for search engines, citation generators, etc. 
 - "digitization" rather than "scanning" or "digitalization" 
 - **Sources:** always cited inline with a short author/venue and URL (e.g., "(Nutrient SDK; www.nutrient.io)"). Never use a reference list. 
 - **Tone:** formal, concise, directive - as an operational guide, not a literature review. 
 - **Register:** academic professional; avoid first-person. 

### Continuation Actions
 - **Preserved, revised, bridge, expanded material:** Not applicable - no continuation source was provided. The brief is a *de novo* plan based solely on the retrieved research.

### Factual Consistency Requirements
1. Digitisation challenges (scalability, complex layouts, multi-language) are real and must be noted (IJSAT URL). 
2. AI does not replace human oversight; it *assists* with OCR integration and summarisation (IJRTI https://ijrti.org/papers/IJRTI2503220.pdf). 
3. Web research tools speed context gathering but still require critical evaluation (SCI Journal, Ponder.ing). 
4. Digital collections are transformative for humanities/SSH research (USC LibGuides https://libguides.usc.edu/c.php?g=1394669&p=10649349). 
5. All source URls must link to the exact pages provided in the research findings; do not fabricate additional citations.

### Forbidden Inconsistencies
 - Do **not** include a separate `References`, `Works Cited`, or `Bibliography` section. 
 - Do **not** reference any document parts that are not present (e.g., a "Methodology" section). 
 - Do **not** use section numbers other than the configured "1. brief" (and that only if required by the heading policy). 
 - Do **not** mention internal planner/agent mechanics (e.g., "pipeline", "configuration"). 
 - Do **not** output placeholders like `[TO-DO]` or `insert citation`. 
 - Avoid contradictory claims - e.g., do not say both "OCR is perfect" and "OCR has limitations".

## Output
Operational Brief

A persistent challenge in academic drafting is the difficulty of synthesising non-digital source materials with the most current online scholarship. A unified workflow that sequentially applies AI OCR digitisation and purpose-driven web research can resolve this bottleneck more efficiently than either method applied in isolation.

Workflow

*Digitise with AI OCR*
The process begins by converting scanned or otherwise non-digital documents into structured, editable text. AI OCR systems such as the Nutrient SDK (www.nutrient.io) and machine-learning-based OCR engines (IJSAT, 2025; https://www.ijsat.org/papers/2025/1/1890.pdf) are capable of handling complex layouts and multi-language documents at scale. The resulting digitised text forms the stable factual base for the subsequent integration stage.

*Gather Current Context*
Concurrently, the researcher collects up-to-date scholarly context from the web. Academic search engines, curated digital collections (USC LibGuides; https://libguides.usc.edu/c.php?g=1394669&p=10649349), citation generators (e.g., Scribbr; www.scribbr.com/citation/generator/), and AI-assisted discovery tools (SCI Journal, 2026; https://www.scijournal.org/articles/best-academic-writing-tools; Ponder.ing, 2026; https://ponder.ing/blog/ai-tools-for-academic-research-writing) enable rapid identification of relevant contemporary sources. Because automated retrieval does not guarantee relevance, every result must be critically evaluated for authority and fit.

*Integrate Systematically*
With both streams in hand, the drafter maps extracted facts from the digitised sources against the web-gathered context. The two strands are woven into a single narrative while provenance is tracked inline. This approach maintains source awareness directly in the text and obviates the need for a separate reference apparatus.

Limitation

The principal limitation of the pipeline concerns OCR accuracy. Complex layouts, degraded originals, and non-standard typefaces can introduce textual errors that propagate into the draft if not manually corrected (IJSAT). AI OCR is an assistive tool that accelerates the digitisation process, but it does not substitute for critical human editorial oversight (IJRTI; https://ijrti.org/papers/IJRTI2503220.pdf).

Summary

Systematically integrating AI OCR digitisation with web research tools results in a rigorous drafting process. The combined workflow enhances completeness and credibility by grounding the draft simultaneously in preserved source material and current scholarship. Human review remains the essential gatekeeper against machine-introduced errors.
