from __future__ import annotations

import json
import re
from typing import Tuple

from pydantic import ValidationError

from academic_pe.core.config import AgentConfig
from academic_pe.core.llm import LLMProvider, _call_provider_generate
from academic_pe.core.templates import (
    PromptManifest,
    RuntimePromptManifest,
    RuntimeTemplate,
    RuntimeTemplateSource,
    TemplateLanguagePolicy,
    TemplateSection,
)


PLANNER_SYSTEM_PROMPT = """You are a document template planner.

Plan the document structure and prompt behavior contract only.
Do not write the document content.
Return valid JSON only, with no Markdown fences and no explanatory text.
"""


PLANNER_USER_TEMPLATE = """Create a temporary runtime document template for this request.

User topic:
{topic}

User instructions:
{instructions}

Return JSON with this exact shape:
{{
  "document_type": "short stable type id",
  "name": "human readable template name",
  "description": "one sentence",
  "category": "academic | general | creative | technical | writing | education",
  "language_policy": "auto | en | ru | zh",
  "sections": [
    {{
      "name": "stable_snake_case",
      "title": "Human Title",
      "instruction": "what this section must do",
      "topic": "optional section topic"
    }}
  ],
  "prompt_manifest": {{
    "planner_role": "planner role",
    "writer_role": "writer role",
    "reviewer_role": "reviewer role",
    "writer_task": "writer task",
    "reviewer_task": "reviewer task",
    "style_contract": {{
      "tone": "formal or neutral or creative",
      "structure": "paragraphs or stanzas or essay etc"
    }},
    "review_rubric": {{
      "required": [
        "list of mandatory criteria"
      ],
      "forbidden": [
        "list of disallowed elements"
      ]
    }},
    "output_constraints": {{
      "markdown_allowed": true,
      "latex_allowed": false
    }}
  }}
}}

Rules:
- sections must contain at least one item;
- every section needs name, title, and instruction;
- prompt_manifest must define writer_role and reviewer_role;
- choose a structure that matches the user request, not a hardcoded academic outline;
- review_rubric values must be lists of strings, not plain strings;
- do not include document body text.
"""


class PlannerAgentError(Exception):
    pass


class PlannerAgent:
    def __init__(self, config: AgentConfig, llm: LLMProvider):
        self.config = config
        self.llm = llm

    def plan(
        self,
        topic: str,
        instructions: str = "",
    ) -> Tuple[RuntimeTemplate, RuntimePromptManifest]:
        raw = _call_provider_generate(
            self.llm,
            system_prompt=self._system_prompt(),
            user_prompt=PLANNER_USER_TEMPLATE.format(
                topic=topic or "(not provided)",
                instructions=instructions or "(none)",
            ),
            model=self.config.model,
            temperature=self.config.temperature,
        )
        return self.parse_plan(raw)

    def parse_plan(self, raw: str) -> Tuple[RuntimeTemplate, RuntimePromptManifest]:
        try:
            extracted = _extract_json_object(raw)
            sanitized = fix_json_escapes(extracted)
            data = json.loads(sanitized)
        except json.JSONDecodeError as exc:
            raise PlannerAgentError(f"Planner returned invalid JSON: {exc}") from exc

        try:
            language_policy = TemplateLanguagePolicy(data.get("language_policy", "auto"))
            sections = [
                TemplateSection(**section)
                for section in data["sections"]
            ]
            prompt_manifest = PromptManifest(**data["prompt_manifest"])
            runtime_template = RuntimeTemplate(
                source=RuntimeTemplateSource.auto,
                source_template_id=None,
                name=data["name"],
                description=data.get("description", ""),
                category=data["category"],
                language_policy=language_policy,
                sections=sections,
                metadata={"document_type": data.get("document_type")},
            )
            runtime_manifest = RuntimePromptManifest(
                source=RuntimeTemplateSource.auto,
                source_template_id=None,
                prompt_manifest=prompt_manifest,
                metadata={"document_type": data.get("document_type")},
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise PlannerAgentError(f"Planner output does not match runtime template schema: {exc}") from exc

        return runtime_template, runtime_manifest

    def _system_prompt(self) -> str:
        base_prompt = self.config.system_prompt.strip() if self.config.system_prompt else ""
        if not base_prompt:
            return PLANNER_SYSTEM_PROMPT
        return f"{base_prompt}\n\n{PLANNER_SYSTEM_PROMPT}"


def fix_json_escapes(raw_json: str) -> str:
    result = []
    in_string = False
    i = 0
    n = len(raw_json)
    while i < n:
        char = raw_json[i]
        if not in_string:
            if char == '"':
                in_string = True
            result.append(char)
            i += 1
        else:
            if char == '"':
                in_string = False
                result.append(char)
                i += 1
            elif char == '\\':
                if i + 1 < n:
                    next_char = raw_json[i + 1]
                    is_latex_or_invalid = False
                    if next_char in ('t', 'r', 'b', 'f'):
                        if i + 2 < n and raw_json[i + 2].isalpha():
                            is_latex_or_invalid = True
                    
                    if next_char in ('"', '\\', '/', 'n'):
                        result.append(char)
                        result.append(next_char)
                        i += 2
                    elif next_char == 'u':
                        is_unicode = False
                        if i + 5 < n and all(c in '0123456789abcdefABCDEF' for c in raw_json[i+2:i+6]):
                            is_unicode = True
                        if is_unicode:
                            result.append('\\')
                            result.append('u')
                            i += 2
                        else:
                            result.append('\\\\')
                            i += 1
                    elif next_char in ('t', 'r', 'b', 'f') and not is_latex_or_invalid:
                        result.append(char)
                        result.append(next_char)
                        i += 2
                    else:
                        result.append('\\\\')
                        i += 1
                else:
                    result.append('\\\\')
                    i += 1
            else:
                result.append(char)
                i += 1
    return "".join(result)


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start:end + 1]
