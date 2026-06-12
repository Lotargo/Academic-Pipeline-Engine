from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml
from pydantic import ValidationError

from academic_pe.core.templates import DocumentTemplate


class TemplateLibraryError(Exception):
    pass


class TemplateNotFoundError(TemplateLibraryError):
    pass


class TemplateLibrary:
    def __init__(self, templates: List[DocumentTemplate]):
        self._templates: Dict[str, DocumentTemplate] = {}
        for template in templates:
            if template.id in self._templates:
                raise TemplateLibraryError(f"Duplicate document template id: {template.id}")
            self._templates[template.id] = template

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TemplateLibrary":
        template_path = Path(path)
        if not template_path.exists():
            raise FileNotFoundError(f"Template library file not found at {template_path}")

        with template_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_templates = data.get("templates")
        if not isinstance(raw_templates, list):
            raise TemplateLibraryError("Template library YAML must contain a 'templates' list.")

        try:
            templates = [DocumentTemplate(**item) for item in raw_templates]
        except TypeError as exc:
            raise TemplateLibraryError("Each template entry must be a mapping.") from exc
        except ValidationError as exc:
            raise TemplateLibraryError(f"Invalid document template configuration: {exc}") from exc

        return cls(templates)

    def list_templates(self) -> List[DocumentTemplate]:
        return list(self._templates.values())

    def get(self, template_id: str) -> DocumentTemplate:
        template = self._templates.get(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Document template not found: {template_id}")
        return template

    def has(self, template_id: str) -> bool:
        return template_id in self._templates
