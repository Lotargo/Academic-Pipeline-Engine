# Source-aware operational brief

Scenario: `web_research_operational_brief`
Elapsed: 122.8s
Config: writer=zen/deepseek-v4-flash-free, planner=zen/big-pickle, researcher=mock/deterministic-search
Search findings chars: 8583

## Rubric
- [ ] uses current/source-aware context without fabricating unsupported certainty
- [ ] reads as a coherent user-facing brief rather than a plan dump
- [ ] includes practical workflow steps and at least one limitation
- [ ] does not leak QUALITY_RAW_REFERENCE_MARKER
- [ ] does not expose internal labels such as red_flags, exposition, or development notes

## Document Plan
{
 "structure": "pipeline.sections",
 "core_intent": "Outline an operational workflow that integrates AI-powered OCR and web research methods to streamline academic document drafting, emphasizing practical steps and source-aware claims.",
 "sections": [
 {
 "name": "brief",
 "title": "AI OCR and Web Research Workflow for Academic Document Drafting: An Operational Brief",
 "goal": "Deliver a compact operational brief that describes a practical workflow integrating AI OCR and web research for academic drafting. Include source-aware claims, concrete workflow steps, and exactly one limitation. Avoid academic sectioning.",
 "heading_policy": "final_document_heading",
 "internal_only": false
 }
 ],
 "writer_instructions": {
 "tone": "concise, operational",
 "audience": "general academic professionals",
 "guidelines": [
 "Use the retrieved web sources to support claims (e.g., GitHub ADHAYA OCR+LLM project, ScienceDirect article on AI in academic writing, Mistral Document AI, etc.).",
 "Structure the brief as a flowing narrative; do not use section headings other than the document heading.",
 "Include inline source notes (e.g., 'the ADHAYA OCR+LLM tool [GitHub] demonstrates...') - do not add a separate References section.",
 "Describe actionable workflow steps: OCR extraction, web research querying, integration into drafting, and human review.",
 "Include exactly one limitation (e.g., OCR accuracy for handwritten or complex layouts, or need for human oversight).",
 "Do not mention internal pipeline mechanics (e.g., model names, pipeline configuration) unless they are user-facing workflow steps.",
 "Do not use academic headings such as 'References', 'Literature Review', or 'Methodology'.",
 "Use standard terminology consistently: 'OCR extraction', 'web research integration', 'drafting workflow'."
 ],
 "math_notation": "Avoid equations unless they are essential to the workflow description."
 },
 "review_rubric": {
 "required": [
 "Must be an operational brief (not a research paper, essay, or list).",
 "Must include source-aware claims with inline references.",
 "Must include practical workflow steps and at least one limitation.",
 "Must maintain consistent terminology and register throughout."
 ],
 "forbidden": [
 "No separate References section or academic headings.",
 "No placeholders, incomplete content, or AI meta-text (e.g., 'I'm an AI model').",
 "No drift into unrelated artifact types (e.g., tutorial, literature review).",
 "No contradictory claims about capabilities of OCR or AI tools."
 ]
 },
 "continuation_actions": "Not applicable (mode new).",
 "consistency_checks": [
 "All claims about workflow steps must align with retrieved sources (e.g., OCR limitations, AI integration benefits).",
 "The single limitation must be consistent with known constraints in the cited sources."
 ],
 "forbidden_inconsistencies": [
 "Do not refer to sections that do not exist (e.g., no References heading).",
 "Do not include internal pipeline terms (e.g., 'LLM-powered summarization module') as workflow steps unless they are user-facing.",
 "Do not mix register or tone (e.g., slipping into academic passive voice)."
 ]
}

## Output
### AI OCR and Web Research Workflow for Academic Document Drafting: An Operational Brief

Producing a rigorous academic draft requires integrating evidence from diverse formats: scanned archives, born-digital PDFs, and live web resources. The following operational workflow combines AI-powered optical character recognition (OCR) with structured web research to streamline this process, moving from ingestion to a human-verified manuscript.

The first step is text capture. Tools such as Mistral Document AI and the ADHAYA OCR+LLM pipeline [GitHub] convert scanned documents into machine-readable text, preserving headings, tables, and basic layout. The user uploads the source material and retrieves a clean, editable output. This stage replaces the manual transcription of printed or handwritten sources with an automated pass that dramatically accelerates the initial extraction of content.

With core content extracted, the drafter turns to verification and enrichment. Keywords and claims from the OCR output drive targeted searches against academic databases, preprint servers, and the open web. Research on AI in academic writing [ScienceDirect] confirms that language models can help refine search queries and synthesize abstracts, but the drafter remains responsible for selecting and curating the results. The aim is a focused supplement to the base text, not an exhaustive literature review.

The OCR text and the curated web findings are then brought into the drafting environment. The author scaffolds the argument, blending direct quotes and paraphrased insights from the historical source material with contemporary evidence surfaced through web research. This hybrid approach raises the baseline coherence of the draft, provided the author retains tight control over the argumentative logic and narrative voice [ScienceDirect].

A thorough human review is the final gate for quality and integrity. Every claim must be checked against its original source, OCR artifacts corrected - especially in equations, citations, footnotes, and handwritten marginalia - and all web material properly attributed. The primary limitation of this workflow lies in OCR accuracy: complex layouts, dense mathematical notation, and degraded print can cause extraction errors that, if undetected, propagate into the final document. Automated extraction is therefore a productive first pass, but rigorous human oversight remains the critical safeguard for scholarly trustworthiness.
