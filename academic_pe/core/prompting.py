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

{% if academic_mode|default(false) %}
IMPORTANT: Since you are in Academic Mode, you MUST support your theoretical or computational claims with data visualizations (plots, charts, graphs).
To do this, you MUST write a python code block marked specifically as ` ```python-run ` (do do not omit the "-run" suffix).
The code inside this block will be executed in a sandbox. It MUST:
1. Set the matplotlib backend to non-interactive:
   import matplotlib
   matplotlib.use("Agg")
   import matplotlib.pyplot as plt
2. Generate the plot/chart based on the section's data or formulas.
3. Save the plot to a unique png file in the `exports` directory, e.g., `exports/plot_{{ section.name }}.png`.
4. Use `print()` to output a standard Markdown image tag referencing the saved image, e.g.:
   print("![Description of the plot](exports/plot_{{ section.name }}.png)")
This output tag will automatically embed the figure in the final Word document.
Ensure your code is clean, executable, and does not print any other text besides the Markdown image tag.
{% endif %}
"""


DEFAULT_PLAN_TEMPLATE = """Create a compact writing plan for an academic document.

{{ language_instruction }}
User topic: {{ user_topic }}
{% if user_instructions %}User instructions: {{ user_instructions }}{% endif %}

Configured sections:
{% for section in sections -%}
- {{ loop.index }}. {{ section.name }}: {{ section.topic }}. {{ section.instruction }}
{% endfor %}

{% if academic_mode|default(false) %}
[Academic Mode Requirement]: The document must contain data visualizations. Plan which sections will include matplotlib charts (using ` ```python-run ` code blocks) to support the analysis, and specify the variables/data they should display.
{% endif %}

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

{% if academic_mode|default(false) %}
IMPORTANT: Since you are in Academic Mode, you MUST preserve or correct the python-run code block used for visualization. 
If correcting a visualization error, ensure the block starts with ` ```python-run `, sets `matplotlib.use("Agg")`, saves to `exports/plot_{{ section.name }}.png`, and prints the Markdown image tag `![Caption](path)`.
{% endif %}

IMPORTANT: Return only the final corrected Markdown text of this section. Do not return diffs, search/replace blocks, edit instructions, or explanations.
"""


DEFAULT_PATCH_REVISION_TEMPLATE = """Edit the current section by returning a minimal patch.
Section topic: {{ section.topic }}
Reviewer issues to address: {{ reviewer_reason }}
{{ section.instruction }}

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

{% if academic_mode|default(false) %}
IMPORTANT: Since you are in Academic Mode, ensure any visualizations (plots/charts) generated via ` ```python-run ` code blocks are preserved or correctly updated. Do not break the python-run structure.
{% endif %}
"""


DEFAULT_REVIEW_TEMPLATE = """Check the provided text for material academic quality issues.
Expected document language: {{ language }}.
{% if review_focus %}Review focus from the previous attempt: {{ review_focus }}{% endif %}

The text is provided with line numbers (e.g., "1: text") and section headers (e.g., "=== Section: section_name ===") for your convenience so you can refer to precise lines and sections. Do not complain about or try to fix the line numbers or section headers themselves, as they are added by the environment.

If the text passes, return exactly: APPROVED

Reject only for concrete issues that materially harm correctness, coherence, or renderability.
Do not reject for minor preference, harmless wording, or label differences such as "section" vs "chapter" unless they create an actual broken reference.

{% if academic_mode|default(false) %}
[Academic Mode Requirement]: You MUST check if the document contains at least one generated data visualization, chart, or plot (represented by markdown image tags like `![Figure](exports/...)` or ` ```python-run ` code blocks). If no visualization is present in the document, you MUST reject it with a comment under `[general]` or the appropriate section, demanding the addition of supporting charts/plots.
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

Use the following format for rejections:
REJECTED
- [section_name]: line <number>: <issue description>
- [section_name]: line <number>: <issue description>
- [general]: <global issue description>
"""


DEFAULT_VERIFY_TEMPLATE = """You are the Writer agent. Your task is to verify if the text of section '{{ section.topic }}' is free of the specific errors identified by the reviewer in their first rejection:
{{ first_attempt_reason }}

Do not look for or fix any other issues; focus only on the errors listed above.
If the section text is completely free of those errors, reply with exactly:
VERIFIED

If any of those errors are still present, correct them and return the final corrected Markdown text of this section. Do not return diffs, search/replace blocks, edit instructions, or explanations.

{% if academic_mode|default(false) %}
IMPORTANT: Since you are in Academic Mode, ensure any visualizations (plots/charts) generated via ` ```python-run ` code blocks are preserved and successfully executed.
{% endif %}
"""


def render_template(template: str, context: Dict[str, Any]) -> str:
    return _env.from_string(template).render(**context).strip()
