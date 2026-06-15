# Uploaded continuation micro-report

Scenario: `uploaded_continuation_micro_report`
Elapsed: 73.7s
Config: writer=zen/deepseek-v4-flash-free, planner=zen/big-pickle, researcher=mock/deterministic-search
Search findings chars: 0

## Rubric
- [ ] continues the existing report instead of restarting with a new introduction
- [ ] preserves formal report style
- [ ] adds useful recommendations
- [ ] does not duplicate references or place new body content after references
- [ ] does not expose internal continuation/planning labels

## Document Plan
# Drafting Plan: Practical Recommendations (Report Continuation)

## Core Intent / Central Claim
The continuation expands the existing mini-report by converting its central findings into actionable procedural steps. The recommendations section serves as the natural implications phase of the report, keeping the existing tone, structure, and voice without restarting or adding introductory material.

## Section-by-Section Goals

### 1. `## Overview` (Preserved)
 - **Status:** Kept exactly as drafted. No changes or revisions.

### 2. `## Findings` (Preserved)
 - **Status:** Kept exactly as drafted.
 - **Bridge Logic:** The final sentence ("Human review remains important for scanned documents with mixed layouts") flows directly into the need for explicit protocols, acting as the implicit transition.

### 3. `## Recommendations` (New / Inserted Section)
 - **Position:** Inserted directly between `Findings` and `References`.
 - **Content derived from Findings:**
 1. **Normalization protocol** — translate “OCR output normalized before LLM processing” into a prescriptive step: *implement a dedicated normalization pre-processing pipeline (whitespace, hyphenation, special characters).*
 2. **Confidence-based triage** — translate “flagging low-confidence sections for review” into a specific action: *define a confidence-score threshold; route flagged blocks to human review before acceptance.*
 3. **Manual review guidelines** — translate “human review remains important for mixed layouts” into a structured check: *for scanned documents with mixed layouts, prioritize human verification of headings, tables, and non-standard formatting zones.*
 - **Style:** Concise, active, formal. Third-person imperative or declarative tone matching the source (“Normalize OCR output…”, “Route low-confidence sections…”).

### 4. `## References` (Preserved)
 - **Status:** Kept exactly as drafted. Terminal section. Not duplicated.

## Heading Policy (Final Document)
 - `## Overview`
 - `## Findings`
 - `## Recommendations`
 - `## References`
*(All rendered as H2 headings. No additional H3 headers required unless the writer chooses internal structuring.)*

## Terminology and Style Choices
 - **Style:** Formal mini-report register. Short, declarative sentences.
 - **Voice:** Third person / impersonal imperative.
 - **Key terms (must match):** `OCR output`, `source layout`, `normalization`, `LLM processing`, `human review`, `confidence score`, `scanned documents`, `mixed layouts`.
 - **Consistency rule:** Terms introduced in `Findings` must be reused in `Recommendations` without redefinition or contradiction.

## Continuation Actions
| Action | Section |
|---|---|
| **Preserved** | Overview, Findings, References |
| **Inserted** | Recommendations (between Findings and References) |
| **Revised** | None |
| **Removed** | None |

## Forewarning: Contradictions & Forbidden Moves
 - **Do not** restart or reintroduce the report (no “This section provides recommendations…” or “Based on the above…” framing that re-establishes topic).
 - **Do not** duplicate the References section.
 - **Do not** contradict the Findings (e.g., recommending fully automated review when Findings mandate human review).
 - **Do not** shift register (keep formal, evidence-aware, no academic apparatus).
 - **Do not** include AI meta-text, placeholders, or empty filler.

## Output
## Overview
OCR quality control depends on comparing extracted text with source layout, checking headings and tables, and flagging low-confidence sections for review.

## Findings
The strongest results appear when OCR output is normalized before LLM processing. Human review remains important for scanned documents with mixed layouts.

## Practical Recommendations
To improve OCR quality control outcomes, implement the following practices:

1. Normalize OCR output before feeding it into an LLM: standardize line breaks, repair character-level errors, and filter out artifacts such as page numbers and running headers.

2. Establish layout-aware verification: compare extracted heading hierarchies and table structures against the original document layout before passing content to downstream processing.

3. Define low-confidence thresholds derived from OCR engine confidence scores; flag any segment below the threshold for mandatory human review.

4. For scanned documents with mixed layouts (multi-column, embedded figures, footnotes), schedule a human quality pass after the automated stage.

5. Maintain a versioned QA checklist that records the specific checks applied, the confidence thresholds used, and the outcome of each review cycle.

## References
1. Internal OCR QA checklist.
2. Document AI deployment notes.
