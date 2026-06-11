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
"""


DEFAULT_REVIEW_TEMPLATE = """Check the provided text for academic tone, logic, formatting errors, and AI markers.
Return exactly one line: APPROVED if the text passes, or REJECTED followed by a brief reason.
Expected document language: {{ language }}.
"""


def render_template(template: str, context: Dict[str, Any]) -> str:
    return _env.from_string(template).render(**context).strip()
