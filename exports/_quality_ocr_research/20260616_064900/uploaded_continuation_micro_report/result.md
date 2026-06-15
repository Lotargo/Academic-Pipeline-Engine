# Uploaded continuation micro-report

Scenario: `uploaded_continuation_micro_report`
Elapsed: 48.9s
Config: writer=zen/deepseek-v4-flash-free, planner=zen/big-pickle, researcher=mock/deterministic-search
Search findings chars: 0

## Rubric
- [ ] continues the existing report instead of restarting with a new introduction
- [ ] preserves formal report style
- [ ] adds useful recommendations
- [ ] does not duplicate references or place new body content after references
- [ ] does not expose internal continuation/planning labels

## Document Plan
# Writing Plan: Mini-report on OCR Quality Control - Practical Recommendations

## Core Intent / Central Claim
 - Provide actionable, evidence-based recommendations for improving OCR quality control, building directly on the findings already presented in the mini-report.
 - The recommendations must be practical, specific to the report's context (normalization before LLM processing, human review for mixed layouts), and maintain the formal report style.

---

## Section-by-Section Goals

### 1. Overview (preserved exactly)
**Final-document heading:** `## overview` 
**Goal:** Retain the existing, concise introduction to OCR quality control as the opening of the report. No changes.

### 2. Findings (preserved exactly)
**Final-document heading:** `## findings` 
**Goal:** Keep the two findings as they stand. They form the evidence base for the new recommendations.

### 3. Recommendations (new - bridge and expansion)
**Final-document heading:** `## recommendations` 
**Goal:** Present practical steps that operationalize the findings:
 - How to implement output normalization before LLM processing (e.g., specific normalization rules, tooling).
 - When and how to apply human review for mixed-layout documents (e.g., criteria for flagging, review workflow).
 - Optionally, a brief note on integrating these steps into existing QA pipelines.
 - Do **not** re-introduce the topic; begin directly after the findings with a natural transition (e.g., "Based on these findings, the following recommendations are proposed:").

### 4. References (preserved exactly)
**Final-document heading:** `## references` 
**Goal:** Keep the original two references. Do **not** duplicate this block.

---

## Terminology and Style Consistency
 - Use the same technical register as the original: 
 - "OCR quality control," "extracted text," "source layout," "low-confidence sections" 
 - "normalized before LLM processing," "scanned documents with mixed layouts"
 - Maintain formal, declarative sentences; avoid colloquialisms or AI-markers.
 - No section numbers (the original uses none).
 - Keep "overview," "findings," "recommendations," "references" as H2 headings exactly.

---

## Continuation Actions

| Material | Action |
|----------|--------|
| **Preserved** | `## overview` and `## findings` - keep as-is. |
| **Revised** | None - no changes to existing content. |
| **Bridge** | The beginning of `## recommendations` must flow from the last sentence of findings. A short one-sentence transition is sufficient (e.g., "The following recommendations follow from these findings."). |
| **Newly expanded** | `## recommendations` - create a short list of 2-3 actionable items, each with a brief rationale. |
| **Duplication prevention** | Do **not** reprint the references section or reintroduce the topic with a new "Overview." |

---

## Facts / Claims That Must Not Contradict
 - Recommendations must **support** (not question) the finding that "OCR output is normalized before LLM processing" and that "human review remains important for scanned documents with mixed layouts."
 - Do not suggest removing or replacing human review entirely.
 - Do not claim a guaranteed accuracy improvement; use cautious language (e.g., "can reduce...," "is recommended when...").

---

## Forbidden Inconsistencies
 - No missing sections: overview, findings, recommendations, references all present.
 - No reference to "Section 1" or numbered parts (the original uses none).
 - No AI meta-text (e.g., "As an AI...").
 - No placeholder text (e.g., "insert recommendation here").
 - No new references unless truly needed; avoid extending the reference list.

## Output
## Overview
OCR quality control depends on comparing extracted text with source layout, checking headings and tables, and flagging low-confidence sections for review.

## Findings
The strongest results appear when OCR output is normalized before LLM processing. Human review remains important for scanned documents with mixed layouts.

## Practical Recommendations
OCR output should be normalized by correcting hyphenation and encoding mismatches before LLM processing. Pages with confidence scores below a defined threshold should be flagged for mandatory human review, particularly in documents with mixed layouts. Periodic audits of the OCR pipeline against gold-standard transcriptions help calibrate layout comparison rules and table extraction routines.

## References
1. Internal OCR QA checklist.
2. Document AI deployment notes.
