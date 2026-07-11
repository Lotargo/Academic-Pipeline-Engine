from __future__ import annotations

from typing import Any, Dict

from jinja2 import BaseLoader, Environment, StrictUndefined


_env = Environment(
    loader=BaseLoader(),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


DEFAULT_DRAFT_TEMPLATE = """Write the final text for section `{{ section_brief.section_id }}`.

Purpose: {{ section_brief.purpose }}.
Output form: {{ section_brief.output_form }}.
{% if section_brief.writing_constraints %}Active section constraints:
{% for constraint in section_brief.writing_constraints %}- {{ constraint }}
{% endfor %}{% endif %}

{{ language_instruction }}
Follow the document plan and continuity context when provided.
Preserve Markdown structure, the requested tone/register, and existing LaTeX formulas when present.
Do not call sections "chapters" unless the user explicitly requested chapter-based output.
{% if not section_brief.visible_heading %}Do not print a section title or expose internal planning labels such as exposition, development, conflict analysis, risks, red_flags, or pacing notes.
{% endif %}
Avoid forward references to sections, tables, formulas, or chapters that do not exist in the current document.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}
{% if continuation_context|default("") %}

[Continuation Mode]
You are continuing an existing document, not starting a separate paper.
Use the previous document as the semantic base: preserve its topic, argument chain, terminology, style, and useful structure unless the user explicitly requests a change.
Infer the previous document's genre, narrator/voice, audience level, register, pacing, and formatting from the continuation source and keep them. If the source is a children's story, school essay, informal narrative, report, poem, or other non-academic genre, continue in that same genre instead of converting it into academic prose.
Produce the current section as part of one coherent revised/continued document. You may revise or replace closing/transition material from the previous work when needed to avoid duplicated introductions, duplicated conclusions, or a disconnected second document.
The continuation source is available in the context data.
{% endif %}

{% if academic_mode|default(false) %}
Academic Mode: strengthen conceptual rigor, definitions, assumptions, evidence discipline, and limitations where they fit this artifact. Preserve the requested genre, audience, structure, and voice; do not turn a non-academic artifact into a research paper.
{% endif %}
{% if visualization_required|default(false) %}
Visualization Requirement: include a data visualization only because this artifact contract explicitly requires it. Write a python code block marked specifically as ` ```python-run ` (do not omit the "-run" suffix).
The code inside this block will be executed in a sandbox. It MUST:
1. Set the matplotlib backend to non-interactive:
   import matplotlib
   matplotlib.use("Agg")
   import matplotlib.pyplot as plt
2. Generate the plot/chart based on the section's data or formulas.
3. Save the plot to a unique png file in the `{{ output_dir | default('exports') }}` directory, e.g., `{{ output_dir | default('exports') }}/plot_{{ section.name }}.png`.
4. Use `print()` to output a standard Markdown image tag referencing the saved image, e.g.:
    print("![Description of the plot]({{ output_dir | default('exports') }}/plot_{{ section_brief.section_id }}.png)")
This output tag will automatically embed the figure in the final Word document.
Ensure your code is clean and executable, and does not print any document text besides the Markdown image tag.
If this sandbox block also produces a material calculation used in the section, emit one single-line machine-readable record with `print("CALCULATION_LEDGER_JSON:" + json.dumps({"entries": [...]}, ensure_ascii=False))`. Import `json`; each entry must include calculation_id (`CALC-001` format), expression, inputs (`value`, `unit`, optional `source`), expected_result, and section_owner equal to `{{ section_brief.section_id }}`. This transport line is stored as internal audit data and is not rendered in the document.
{% endif %}

"""


DEFAULT_PLAN_TEMPLATE = """Create a compact writing plan for the requested artifact.

{{ language_instruction }}
User topic: {{ user_topic }}
{% if user_instructions %}User instructions: {{ user_instructions }}{% endif %}
{% if continuation_context|default("") %}

[Continuation Source]
{{ continuation_context }}

Continuation planning rules:
- Treat the previous document as the existing state of the work, not as a generic citation source.
- Preserve the established topic, argument chain, terminology, style, and structure unless the new user instructions explicitly change them.
- Preserve the previous genre, narrator/voice, audience level, register, pacing, and formatting. Do not make the continuation more academic, technical, formal, or adult than the previous work unless the new user explicitly asks for that change.
- Use the previous user prompt, previous instructions, previous plan, and previous runtime template/manifest to infer why the document was written that way.
- Decide which previous sections should be preserved, which terminal parts need trimming or rewriting, and what bridge is needed before new material.
- Plan one coherent revised/continued document, not two detached documents.
- Avoid duplicated introductions, duplicated conclusions, repeated bibliography blocks, and abrupt restarts.
{% endif %}

Configured sections:
{% for section in sections -%}
- {{ loop.index }}. {{ section.name }}: {{ section.topic }}. role={{ section.semantic_role|default("body") }}, heading_policy={{ section.heading_policy|default("render_required") }}. {{ section.instruction }}
{% endfor %}

{% if academic_mode|default(false) %}
Academic Mode: plan for stronger reasoning, clearer assumptions, evidence discipline, and limitations where they fit this artifact. Preserve the requested artifact type and do not add charts, formulas, citations, or research-paper sections unless they naturally support the artifact or were explicitly requested.
{% endif %}
{% if visualization_required|default(false) %}
[Visualization Requirement]: The artifact contract requires data visualization. Plan which sections will include matplotlib charts (using ` ```python-run ` code blocks) and specify the variables/data they should display.
{% endif %}

{% if reference_materials %}
[Reference Materials / Background Documents]
{% for ref in reference_materials %}
File: {{ ref.filename }} (Type: Reference)
Content:
{{ ref.content }}
---
{% endfor %}
{% endif %}

{% if search_findings %}
[Web Search Findings / Current Literature]
{{ search_findings }}

Research planning rules:
- Build the outline specifically around the retrieved research data and embed the citations (links) so the writer can output them.
- Reference the URLs of the sources where appropriate.
{% endif %}

Return a concise Markdown plan with:
- core intent / central claim when applicable;
- section-by-section goals;
- which headings are final-document headings and which blocks are internal-only;
- terminology and style choices that must stay consistent;
- continuation actions for preserved, revised, bridge, and newly expanded material when a continuation source is provided;
- facts, formulas, or complexity claims that must not contradict each other;
- forbidden inconsistencies, including missing section numbers or references to unavailable document parts.
"""


DEFAULT_MERGE_OPERATION_TEMPLATE = """Produce merge-operation payloads for continuing or editing the existing artifact.

{{ language_instruction }}
User topic: {{ user_topic }}
{% if user_instructions %}User instructions: {{ user_instructions }}{% endif %}

[Edit Plan JSON]
{{ edit_plan_json }}

[Document State JSON]
{{ document_state_json }}

Rules:
- Treat the previous document as the current artifact state.
- Return ONLY valid JSON. Do not include Markdown fences, commentary, a full document, or editorial changelog text.
- Write only payload text for the operation content roles required by the edit plan.
- Preserve the source genre, voice/register, tense, terminology, heading style, and citation style.
- Use `reference_registry` from Document State as the source registry when it exists: preserve existing entries, avoid duplicates, and add new source entries only through a `references` operation payload.
- If the edit plan includes `smooth_bridge`, rewrite only the requested closing/tail bridge text.
- If the edit plan includes `continuation`, write only the new continuation body fragment.
- If the edit plan includes `references`, write only bare reference entries to merge. Do not include headings or editorial labels such as "References", "New references", "Added sources", or "Sources added".
- Do not include internal planning headings such as exposition, development, risks, red_flags, continuity notes, or pacing notes.
- Do not put body continuation after terminal sections such as references or appendices.

Required JSON shape:
{
  "operation_outputs": {
    "content_role_from_edit_plan": "payload text"
  },
  "reviewer_notes": []
}
"""


DEFAULT_REVISION_TEMPLATE = """Revise section `{{ section_brief.section_id }}`.
Purpose: {{ section_brief.purpose }}.
Address these reviewer issues: {{ reviewer_reason }}
{% if section_brief.writing_constraints %}Active section constraints:
{% for constraint in section_brief.writing_constraints %}- {{ constraint }}
{% endfor %}{% endif %}

{{ language_instruction }}
Make the smallest possible targeted edits to the existing section.
Preserve unaffected paragraphs, wording, Markdown structure, requested tone/register, and existing LaTeX formulas whenever they are not part of the reviewer issue.
Do not introduce new chapter numbering schemes, new missing references, or unrelated claims.
Output form: {{ section_brief.output_form }}. {% if not section_brief.visible_heading %}Do not expose its title or internal planning labels in the corrected final text.{% endif %}
Context may include other document sections for continuity. Treat those other sections as read-only reference material; do not include or rewrite them in your output.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}
{% if continuation_context|default("") %}

[Continuation Mode]
This revision is part of a continued document. Preserve continuity with the previous work and make only the changes needed to create one coherent revised/continued document.
Preserve the previous genre, narrator/voice, audience level, register, pacing, and formatting. Do not upgrade the prose into academic style unless that style is already present in the source or explicitly requested now.
If the current section is a terminal section from the old work, rewrite or trim final-sounding paragraphs so the new continuation does not read like a second document after a completed first document.
{% endif %}

{% if academic_mode|default(false) %}
Academic Mode: preserve compatible rigor and evidence discipline while keeping this artifact's genre, audience, and structure intact.
{% endif %}
{% if visualization_required|default(false) %}
IMPORTANT: Preserve or correct the python-run code block used for visualization.
If correcting a visualization error, ensure the block starts with ` ```python-run `, sets `matplotlib.use("Agg")`, saves to `{{ output_dir | default('exports') }}/plot_{{ section_brief.section_id }}.png`, and prints the Markdown image tag `![Caption]({{ output_dir | default('exports') }}/plot_{{ section_brief.section_id }}.png)`.
{% endif %}

IMPORTANT: Return only the final corrected Markdown text of the current section. Do not return the full document, other sections, diffs, search/replace blocks, edit instructions, or explanations.
"""


DEFAULT_PATCH_REVISION_TEMPLATE = """Edit the current section by returning a minimal patch.
Section: `{{ section_brief.section_id }}`
Purpose: {{ section_brief.purpose }}
Reviewer issues to address: {{ reviewer_reason }}
{% if section_brief.writing_constraints %}Active section constraints:
{% for constraint in section_brief.writing_constraints %}- {{ constraint }}
{% endfor %}{% endif %}

{{ language_instruction }}

You will receive the existing section with line numbers in context (e.g., "1: text\n2: text\n..."). Do not rewrite the full section.
If this section does not need changes (or if the reviewer issues do not apply to this section), return exactly:
NO_CHANGES

If changes are needed, return one or more REPLACE blocks specifying the range of lines to replace (1-based, inclusive):
<<<<<<< REPLACE <start_line>-<end_line>
new content for this range of lines (do not include line numbers here)
>>>>>>>

Rules:
- If the reviewer issues do not mention or affect this section, you MUST return exactly: NO_CHANGES
- Line range <start_line>-<end_line> is inclusive. For example, to replace line 15 only, use `15-15`.
- Do not include the line numbers (e.g., "15: ") inside the replacement content. Just output the clean text.
- Replace only the smallest line range needed to fix the issue.
- Preserve unaffected paragraphs, Markdown headings, LaTeX formulas, and wording.
- Do not add explanations outside the blocks.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}
{% if continuation_context|default("") %}

[Continuation Mode]
When patching, preserve useful previous-work continuity and only replace the smallest lines needed to remove duplicated endings, disconnected transitions, contradictions, or stale final summaries.
Do not change the source genre, narrator/voice, audience level, register, pacing, or formatting unless the current user request explicitly requires it.
{% endif %}

{% if academic_mode|default(false) %}
Academic Mode: preserve compatible rigor and evidence discipline while keeping this artifact's genre, audience, and structure intact.
{% endif %}
{% if visualization_required|default(false) %}
IMPORTANT: Ensure any visualizations (plots/charts) generated via ` ```python-run ` code blocks are preserved or correctly updated. Do not break the python-run structure.
{% endif %}
"""


DEFAULT_REVIEW_TEMPLATE = """Check the provided text for material quality issues against the active artifact contract and user request.
Expected document language: {{ language }}.
{% if review_focus %}Review focus from the previous attempt: {{ review_focus }}{% endif %}
{% if continuation_context|default("") %}

[Continuation Review]
The document was generated in continuation mode. Reject if it reads as two separate documents, restarts the topic without need, duplicates introductions/conclusions, contradicts the previous work, loses the user's continuation request, changes genre or audience level without explicit instruction, turns a non-academic source into academic prose, or has an abrupt style/terminology shift.
{% endif %}

The text is provided with line numbers (e.g., "1: text") and section headers (e.g., "=== Section: section_name ===") for your convenience so you can refer to precise lines and sections. Do not complain about or try to fix the line numbers or section headers themselves, as they are added by the environment.

If the text passes, return exactly: APPROVED

Reject only for concrete issues that materially harm correctness, coherence, or renderability.
Do not reject for minor preference, harmless wording, or label differences such as "section" vs "chapter" unless they create an actual broken reference.
Reject visible internal planning labels in final text, including exposition, development, conflict analysis, red_flags, pacing notes, continuity notes, or editorial risk labels, unless the user explicitly requested an outline or editorial changelog.

{% if academic_mode|default(false) %}
Academic Mode: check for weak assumptions, unsupported claims, shallow definitions, conceptual contradictions, and missing limitations where those checks fit this artifact. Do not reject a non-academic artifact merely because it lacks charts, formulas, citations, or research-paper sections.
{% endif %}
{% if visualization_required|default(false) %}
[Visualization Requirement]: Check if the document contains at least one generated data visualization, chart, or plot (represented by markdown image tags like `![Figure]({{ output_dir | default('exports') }}/...)` or ` ```python-run ` code blocks). If no visualization is present, reject it with a concrete issue.
{% endif %}

If a review focus is provided, first verify whether those issues are fixed. You MUST carefully verify whether all those issues are completely fixed. If any of those issues are still present (even partially), you MUST reject again. Add new issues only when they are severe regressions or major contradictions.

If the text fails, start your response with the line "REJECTED" (without quotes) and then list the specific actionable issues.
You MUST group the issues by the section they occur in using the tag `[section_name]` (from the list below).
For each issue, specify the line number(s) if possible.

{% if sections is defined and sections -%}
Valid section names you MUST use in square brackets:
{% for section in sections -%}
- [{{ section.name }}] (Topic: {{ section.topic }})
{% endfor %}
{%- endif %}
- [general] (for general issues affecting the whole document or multiple sections)

Return a machine-readable JSON object and no Markdown fences:
{
  "approved": true,
  "reviewer_role": "evidence|editorial|general",
  "summary": "短кое пояснение",
  "issues": [
    {
      "section": "section_name or general",
      "line": 83,
      "severity": "blocker|major|minor",
      "code": "STABLE_UPPER_SNAKE_CASE",
      "message": "specific actionable issue"
    }
  ]
}
Set approved=false when any blocker or material issue remains. Use an empty issues array when approved=true. Do not invent line numbers; use null for a document-level issue.
"""


DEFAULT_VERIFY_TEMPLATE = """You are the Writer agent. Your task is to verify if the text of section '{{ section.topic }}' is free of the specific errors identified by the reviewer in their first rejection:
{{ first_attempt_reason }}

Do not look for or fix any other issues; focus only on the errors listed above.
If the section text is completely free of those errors, reply with exactly:
VERIFIED

If any of those errors are still present, correct them and return the final corrected Markdown text of this section. Do not return diffs, search/replace blocks, edit instructions, or explanations.
Context may include other document sections for continuity. Treat those other sections as read-only reference material; do not include or rewrite them in your output.

{% if academic_mode|default(false) %}
Academic Mode: verify the specific reviewer feedback while preserving compatible rigor and the artifact's requested genre.
{% endif %}
{% if visualization_required|default(false) %}
IMPORTANT: Ensure any visualizations (plots/charts) generated via ` ```python-run ` code blocks are preserved and successfully executed.
{% endif %}
"""


def render_template(template: str, context: Dict[str, Any]) -> str:
    merged = {
        "reference_materials": None,
        "search_findings": None,
        **context
    }
    return _env.from_string(template).render(**merged).strip()
