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


DEFAULT_DRAFT_TEMPLATE = """Write a chapter about {{ section.topic }}.
{{ section.instruction }}

{{ language_instruction }}
Preserve Markdown structure, use academic impersonal tone, and keep LaTeX formulas unchanged.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}
"""


DEFAULT_REVISION_TEMPLATE = """Revise the chapter about {{ section.topic }}.
Address these reviewer issues: {{ reviewer_reason }}
{{ section.instruction }}

{{ language_instruction }}
Preserve Markdown structure, academic tone, and LaTeX formulas.
{% if user_topic %}Original user topic: {{ user_topic }}{% endif %}
{% if user_instructions %}Original user instructions: {{ user_instructions }}{% endif %}

IMPORTANT: You must return the COMPLETE, fully rewritten text of the revised section. Do NOT return diffs, search/replace blocks, edit instructions, or explanations of what was changed. Output only the final rewritten Markdown text of the section, ready to be read.
"""


DEFAULT_REVIEW_TEMPLATE = """Check the provided text for academic tone, logic, formatting errors, and AI markers.
Expected document language: {{ language }}.

If the text passes, return exactly: APPROVED
If the text fails, return exactly one line starting with REJECTED: followed by a highly detailed, comprehensive, and exhaustive list of all identified issues (separated by semicolons, on a single line) so the writer has enough detail to fix them.
"""


def render_template(template: str, context: Dict[str, Any]) -> str:
    return _env.from_string(template).render(**context).strip()
