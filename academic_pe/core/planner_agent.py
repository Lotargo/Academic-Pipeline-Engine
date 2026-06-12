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
  "language_policy": "auto | en | ru",
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
    "style_contract": {{}},
    "review_rubric": {{}},
    "output_constraints": {{}}
  }}
}}

Rules:
- sections must contain at least one item;
- every section needs name, title, and instruction;
- prompt_manifest must define writer_role and reviewer_role;
- choose a structure that matches the user request, not a hardcoded academic outline;
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
            data = json.loads(_extract_json_object(raw))
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
