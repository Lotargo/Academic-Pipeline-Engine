# Uploaded continuation micro-report

Scenario: `uploaded_continuation_micro_report`
Elapsed: 47.6s
Config: writer=zen/deepseek-v4-flash-free, planner=zen/big-pickle, researcher=mock/deterministic-search
Search findings chars: 0

## Rubric
- [ ] continues the existing report instead of restarting with a new introduction
- [ ] preserves formal report style
- [ ] adds useful recommendations
- [ ] does not duplicate references or place new body content after references
- [ ] does not expose internal continuation/planning labels

## Document Plan
**Core Intent**  
Deliver a concise, actionable set of recommendations that directly follow from the mini‑report’s findings on OCR quality control, without altering the original structure or tone.

**Section‑by‑Section Goals**  

| Final Heading | Type | Goal |
|---------------|------|------|
| Overview | preserved (no change) | Keep the existing summary of OCR quality control principles. |
| Findings | preserved (no change) | Retain the reported results verbatim. |
| Recommendations | **new** body section | Provide practical, evidence‑based recommendations (e.g., normalisation procedures, human review triggers, confidence‑score thresholds). |
| References | preserved (no change) | Maintain the original short reference list exactly as written. No new references added (unless a new source is cited in Recommendations, in which case only that source is appended). |

**Headings**  
- All four headings (Overview, Findings, Recommendations, References) are final‑document headings.  
- No internal‑only blocks are needed.

**Terminology & Style Consistency**  
- **Key terms** (unchanged): `OCR output`, `LLM processing`, `human review`, `confidence thresholds`, `mixed layouts`, `normalised`.  
- **Register**: formal, concise, evidence‑aware, with no AI‑filler or meta‑text.  
- **Voice**: third‑person, impartial (e.g., “It is recommended that…”).  
- **Numbering**: no section numbers (plain headings only, consistent with the original mini‑report).

**Continuation Actions**  

| Action | Details |
|--------|---------|
| **Preserve** | Overview and Findings remain exactly as provided. |
| **Bridge** | Recommendations opens with a single bridging sentence (e.g., “In light of the findings above, the following practical recommendations are made.”) to avoid a new introduction. |
| **New material** | Recommendations: 3–5 bullet points or short paragraphs, each directly connected to a specific finding. |
| **Revise** | None needed; the original sections require no editing. |
| **References** | If a recommendation cites a source not already listed, append it after the existing references; otherwise leave the reference section untouched. |

**Factual & Logical Consistency**  
- Every recommendation must tie explicitly to one of the stated findings (e.g., “Human review remains important” → “Establish a mandatory human review step for documents with mixed layouts”).  
- No new claims that contradict the findings (e.g., do not claim that normalisation alone is sufficient if the findings say human review is still needed).  
- Confidence‑threshold values or normalisation steps mentioned in Recommendations must match the language used in Findings (no arbitrary new numbers).

**Forbidden Inconsistencies**  
- Do not add a new introductory paragraph or repeat the Overview.  
- Do not re‑word, trim, or expand the preserved sections.  
- Do not introduce section numbers unless they were used in the original mini‑report (they were not).  
- Do not reference any non‑existent document parts (e.g., “as discussed in section 2” does not exist).  
- Do not include AI‑specific markers or placeholders.  
- Do not append a duplicate References block.

## Output
## overview
OCR quality control depends on comparing extracted text with source layout, checking headings and tables, and flagging low-confidence sections for review.

## findings
The strongest results appear when OCR output is normalized before LLM processing. Human review remains important for scanned documents with mixed layouts.

## continuation
## Recommendations

Establish consistent preprocessing steps for OCR output before any LLM-based analysis. Normalization, including character correction and layout reclassification, reduces downstream errors.

Define confidence thresholds that trigger automatic human review for sections flagged during extraction. This applies especially to documents with mixed layouts, tables, and nonstandard headings.

Retain the original scanned image alongside the extracted text to support verification of high-risk fields. Pairing image context with text output improves the reliability of QA checks.

Document each deviation between extracted text and source layout as part of the review log. Standardized logging supports future model tuning and audit requirements.

## references
1. Internal OCR QA checklist.
2. Document AI deployment notes.
