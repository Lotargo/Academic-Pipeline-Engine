# Source-aware operational brief

Scenario: `web_research_operational_brief`
Elapsed: 140.7s
Config: writer=zen/deepseek-v4-flash-free, planner=zen/big-pickle, researcher=mock/deterministic-search
Search findings chars: 12717

## Rubric
- [ ] uses current/source-aware context without fabricating unsupported certainty
- [ ] reads as a coherent user-facing brief rather than a plan dump
- [ ] includes practical workflow steps and at least one limitation
- [ ] does not leak QUALITY_RAW_REFERENCE_MARKER
- [ ] does not expose internal labels such as red_flags, exposition, or development notes

## Document Plan
{
  "template_planner": {
    "sections": [
      {
        "name": "brief",
        "title": "AI OCR and Web Research Workflow for Academic Document Drafting: A Concise Operational Brief",
        "type": "body",
        "heading_required": true,
        "instruction": "Write a clear operational brief with source-aware claims, practical workflow steps, and one limitation. Keep it reasonably compact; do not optimize for an exact character count. Incorporate insights from the provided research sources: use the LlamaIndex article for agentic OCR workflows, the AI Document Workflow for Academics for writing steps, and the arXiv paper for production architecture. Reference appropriate URLs. Structure the brief with an introduction, a multi-step workflow that combines AI OCR and web research, and a practical limitation. Use an objective, concise tone suitable for academics. Use Markdown subheadings for readability (e.g., ## Introduction, ## Workflow, ## Limitation)."
      }
    ],
    "writer_instructions": "Write the entire document in English. Use current web context based on the provided research findings. Do not mention internal pipeline mechanics unless they are user-facing workflow steps. Ensure claims are supported by citations from the references. Include URLs for key sources. Adopt a concise operational tone. Structure the brief with clear, logically ordered content: start with the purpose and context, then present the workflow steps (e.g., document capture via OCR, data extraction, web research integration, drafting), then discuss one limitation (e.g., accuracy or source reliability). Use H2 or H3 Markdown headings as needed. Do not include any AI meta-text or placeholders. The main heading is required and must be exactly as given. Keep the brief self-contained and practical.",
    "review_rubric": {
      "required": [
        "Must be a concise operational brief (not a research paper or guide)",
        "Must include source-aware claims with appropriate citations from the provided references",
        "Must include practical workflow steps that combine AI OCR and web research",
        "Must include exactly one limitation",
        "Must reflect current web context as provided in the search results",
        "Must be written entirely in English",
        "Must have the required main heading rendered exactly",
        "Must be reasonably compact and avoid unnecessary verbosity",
        "Must use consistent terminology (e.g., 'AI OCR', 'web research', 'academic drafting')"
      ],
      "forbidden": [
        "Do not expand beyond the single 'brief' section; no additional sections",
        "Do not include any internal pipeline mechanics that are not user-facing",
        "Do not include AI meta-text, placeholders, or filler language",
        "Do not include empty or incomplete content",
        "Do not contradict facts from the research sources",
        "Do not use any language other than English except for necessary quotes",
        "Do not include any introductory or concluding statements that refer to the process of writing the brief itself"
      ]
    },
    "latex_allowed": true,
    "markdown_allowed": true
  }
}

## Output
# AI OCR and Web Research Workflow for Academic Document Drafting: A Concise Operational Brief

## Introduction

Producing an academic draft from a mixed set of physical documents, scanned texts, and web-based sources typically requires several disjointed manual stages. Recent advances integrate AI Optical Character Recognition (OCR) with structured web research into a single operational pipeline. Drawing on agentic OCR frameworks (LlamaIndex workflows), structured drafting sequences (AI Document Workflow for Academics), and production architecture principles, this brief outlines a practical four-step workflow that reduces manual overhead while maintaining source traceability.

## Workflow

**1. Agentic Document Ingestion.** Scanned PDFs, photographs of print sources, and handwritten notes are processed through an AI OCR layer. Unlike conventional OCR that outputs raw text, agentic pipelines perform context-aware reconstruction—preserving multi-column layouts, mathematical notation, footnotes, and table structure. The output is a machine-readable text corpus with document artifacts corrected or flagged.

**2. Semantic Chunking and Structured Extraction.** The cleaned text is segmented by semantic boundaries (abstract, methodology, results, references) rather than fixed token counts. Metadata such as authorship, publication year, citation keys, and key claims is extracted and organized into a searchable index or structured store. This step creates a queryable knowledge base from the ingested source material.

**3. Web Research and Contextual Validation.** Claims, citations, and data points extracted from the source documents serve as targeted queries for real-time web research. Following retrieval-augmented generation (RAG) patterns, the system fetches recent publications, correction notices, alternative findings, or supplementary context. Retrieved results are cross-referenced against the original extraction to identify factual conflicts or gaps in coverage.

**4. LLM Drafting with Source Attribution.** The structured document data and validated web research outputs are passed to an LLM orchestrated by a prompt that enforces academic tone, logical argument flow, and explicit attribution. Every claim in the draft is linked to its originating source chunk—either from the OCR corpus or the web retrieval—allowing rapid manual verification without abandoning the drafting speed gain.

## Limitation

**Compounded Error from Source Fidelity.** The single most significant operational constraint is the risk of cascading inaccuracy. A misread character or misinterpreted table cell in the OCR stage will propagate into the web research queries and the final draft. Similarly, web research depends on the availability and authority of online sources, which may not match the depth or specificity of original archival documents. Mitigating this requires a human-in-the-loop verification step after OCR cleanup and again at the fact-checking stage, which reintroduces manual effort into an otherwise automated pipeline. This bottleneck remains the primary practical limit on scale and speed in production academic drafting workflows.
