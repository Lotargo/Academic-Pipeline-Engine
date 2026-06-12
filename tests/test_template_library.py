import pytest

from academic_pe.core.template_library import (
    TemplateLibrary,
    TemplateLibraryError,
    TemplateNotFoundError,
)


def _write_templates(tmp_path, content: str):
    path = tmp_path / "document_templates.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_template_library_loads_templates_from_yaml(tmp_path):
    path = _write_templates(
        tmp_path,
        """
templates:
  - id: freeform_article
    name: Freeform Article
    description: General prose article.
    category: general
    sections:
      - name: body
        title: Body
        instruction: Write coherent prose.
    prompt_manifest:
      writer_role: General prose writer
      reviewer_role: General prose reviewer
      style_contract:
        tone: neutral
      review_rubric:
        required:
          - coherent flow
      output_constraints:
        markdown_allowed: true
""",
    )

    library = TemplateLibrary.from_yaml(path)

    assert library.has("freeform_article")
    assert library.get("freeform_article").name == "Freeform Article"
    assert library.list_templates()[0].prompt_manifest.writer_role == "General prose writer"


def test_template_library_rejects_duplicate_template_ids(tmp_path):
    path = _write_templates(
        tmp_path,
        """
templates:
  - id: repeated
    name: First
    category: general
    sections:
      - name: body
        title: Body
        instruction: Write the body.
    prompt_manifest:
      writer_role: Writer
      reviewer_role: Reviewer
  - id: repeated
    name: Second
    category: general
    sections:
      - name: body
        title: Body
        instruction: Write the body.
    prompt_manifest:
      writer_role: Writer
      reviewer_role: Reviewer
""",
    )

    with pytest.raises(TemplateLibraryError, match="Duplicate document template id"):
        TemplateLibrary.from_yaml(path)


def test_template_library_rejects_template_without_prompt_manifest(tmp_path):
    path = _write_templates(
        tmp_path,
        """
templates:
  - id: invalid
    name: Invalid
    category: general
    sections:
      - name: body
        title: Body
        instruction: Write the body.
""",
    )

    with pytest.raises(TemplateLibraryError, match="Invalid document template configuration"):
        TemplateLibrary.from_yaml(path)


def test_template_library_raises_for_unknown_template(tmp_path):
    path = _write_templates(
        tmp_path,
        """
templates:
  - id: known
    name: Known
    category: general
    sections:
      - name: body
        title: Body
        instruction: Write the body.
    prompt_manifest:
      writer_role: Writer
      reviewer_role: Reviewer
""",
    )

    library = TemplateLibrary.from_yaml(path)

    with pytest.raises(TemplateNotFoundError, match="Document template not found"):
        library.get("missing")


def test_builtin_document_templates_are_valid():
    library = TemplateLibrary.from_yaml("config/document_templates.yaml")

    template_ids = {template.id for template in library.list_templates()}

    assert template_ids == {
        "academic_arxiv",
        "academic_report",
        "essay",
        "school_composition",
        "poem",
        "freeform_article",
        "technical_note",
    }
    for template in library.list_templates():
        assert template.sections
        assert template.prompt_manifest.writer_role
        assert template.prompt_manifest.reviewer_role
