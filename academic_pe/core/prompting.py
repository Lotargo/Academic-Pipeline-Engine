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


DEFAULT_DRAFT_TEMPLATE = """Write a section about {{ section.topic }}.
{{ section.instruction }}

{{ language_instruction }}
Follow the document plan and continuity context when provided.
Preserve Markdown structure, use academic impersonal tone, and keep LaTeX formulas unchanged.
Do not call sections "chapters" unless the user explicitly requested chapter-based output.
Avoid forward references to sections, tables, formulas, or chapters that do not exist in the current document.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}
"""


DEFAULT_PLAN_TEMPLATE = """Create a compact writing plan for an academic document.

{{ language_instruction }}
User topic: {{ user_topic }}
{% if user_instructions %}User instructions: {{ user_instructions }}{% endif %}

Configured sections:
{% for section in sections -%}
- {{ loop.index }}. {{ section.name }}: {{ section.topic }}. {{ section.instruction }}
{% endfor %}

Return a concise Markdown plan with:
- thesis / central claim;
- section-by-section goals;
- terminology that must stay consistent;
- formulas or complexity claims that must not contradict each other;
- forbidden inconsistencies, including missing section numbers or references to unavailable document parts.
"""


DEFAULT_REVISION_TEMPLATE = """Revise the section about {{ section.topic }}.
Address these reviewer issues: {{ reviewer_reason }}
{{ section.instruction }}

{{ language_instruction }}
Make the smallest possible targeted edits to the existing section.
Preserve unaffected paragraphs, wording, Markdown structure, academic tone, and LaTeX formulas whenever they are not part of the reviewer issue.
Do not introduce new chapter numbering schemes, new missing references, or unrelated claims.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}

IMPORTANT: Return only the final corrected Markdown text of this section. Do not return diffs, search/replace blocks, edit instructions, or explanations.
"""


DEFAULT_PATCH_REVISION_TEMPLATE = """Edit the current section by returning a minimal patch.
Section topic: {{ section.topic }}
Reviewer issues to address: {{ reviewer_reason }}
{{ section.instruction }}

{{ language_instruction }}

You will receive the existing section in context. Do not rewrite the full section.
If this section does not need changes, return exactly:
NO_CHANGES

If changes are needed, return one or more exact SEARCH/REPLACE blocks:
<<<<<<< SEARCH
exact existing text to replace
=======
replacement text
>>>>>>> REPLACE

Rules:
- SEARCH text must be copied exactly from the current section.
- Each SEARCH block must match exactly one location.
- Replace only the smallest text span needed to fix the issue.
- Preserve unaffected paragraphs, Markdown headings, LaTeX formulas, and wording.
- Do not add explanations outside the blocks.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}
"""


DEFAULT_REVIEW_TEMPLATE = """Check the provided text for material academic quality issues.
Expected document language: {{ language }}.
{% if review_focus %}Review focus from the previous attempt: {{ review_focus }}{% endif %}

If the text passes, return exactly: APPROVED
Reject only for concrete issues that materially harm correctness, coherence, or renderability.
Do not reject for minor preference, harmless wording, or label differences such as "section" vs "chapter" unless they create an actual broken reference.
If a review focus is provided, first verify whether those issues are fixed. Add new issues only when they are severe regressions or major contradictions.
If the text fails, return exactly one line starting with REJECTED: followed by at most three specific actionable issues separated by semicolons.
"""


def render_template(template: str, context: Dict[str, Any]) -> str:
    return _env.from_string(template).render(**context).strip()
