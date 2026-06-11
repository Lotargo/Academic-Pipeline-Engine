import os
import tempfile

import pytest
from docx import Document

from src.tools.docx_renderer import render_paper, set_font_style, set_paragraph_format


@pytest.fixture
def tmp_doc():
    with tempfile.TemporaryDirectory() as d:
        yield os.path.join(d, "test.docx")


class TestRenderPaper:
    def test_creates_file(self, tmp_doc):
        result = render_paper({"theory": "Hello world"}, tmp_doc)
        assert result == tmp_doc
        assert os.path.exists(tmp_doc)

    def test_all_sections_present(self, tmp_doc):
        content = {
            "theory": "Theory content here.",
            "calculation": "Calculation content here.",
            "conclusion": "Conclusion content here.",
        }
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Theory content here." in full_text
        assert "Calculation content here." in full_text
        assert "Conclusion content here." in full_text

    def test_missing_keys_rendered(self, tmp_doc):
        content = {"theory": "Only theory."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Only theory." in full_text

    def test_empty_content(self, tmp_doc):
        render_paper({}, tmp_doc)
        assert os.path.exists(tmp_doc)
        doc = Document(tmp_doc)
        assert len(doc.paragraphs) > 0

    def test_empty_section_string(self, tmp_doc):
        content = {"theory": "", "calculation": "  ", "conclusion": "OK"}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "OK" in full_text

    def test_heading_rendered(self, tmp_doc):
        content = {"theory": "# My Heading\n\nParagraph text."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "My Heading" in full_text

    def test_bold_text(self, tmp_doc):
        content = {"theory": "This is **bold** text."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        found_bold = False
        for p in doc.paragraphs:
            for run in p.runs:
                if run.bold and "bold" in run.text:
                    found_bold = True
        assert found_bold

    def test_italic_text(self, tmp_doc):
        content = {"theory": "This is *italic* text."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        found_italic = False
        for p in doc.paragraphs:
            for run in p.runs:
                if run.italic and "italic" in run.text:
                    found_italic = True
        assert found_italic

    def test_latex_inline_math(self, tmp_doc):
        content = {"calculation": r"Formula $E=mc^2$ here."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "E=mc^2" in full_text or "E=mc2" in full_text

    def test_latex_display_math(self, tmp_doc):
        content = {"calculation": r"Display $$\sum_{i=1}^{n} i$$ end."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "sum" in full_text.lower() or r"\sum" in full_text

    def test_subscript_rendered(self, tmp_doc):
        content = {"calculation": r"Variable $x_{1}$ and $x_2$."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        found_sub = False
        for p in doc.paragraphs:
            for run in p.runs:
                if run.font.subscript:
                    found_sub = True
        assert found_sub

    def test_times_new_roman_font(self, tmp_doc):
        content = {"theory": "Check font."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        for p in doc.paragraphs:
            for run in p.runs:
                if run.text.strip():
                    assert run.font.name == "Times New Roman"

    def test_justified_alignment(self, tmp_doc):
        content = {"theory": "Paragraph for alignment."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        found_justified = False
        for p in doc.paragraphs:
            if p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
                found_justified = True
        assert found_justified

    def test_default_filename(self):
        with tempfile.TemporaryDirectory() as d:
            old_cwd = os.getcwd()
            os.chdir(d)
            try:
                result = render_paper({"theory": "test"})
                assert os.path.exists(result)
            finally:
                os.chdir(old_cwd)

    def test_page_break_after_title(self, tmp_doc):
        content = {"theory": "Content."}
        render_paper(content, tmp_doc)
        doc = Document(tmp_doc)
        found_break = False
        for p in doc.paragraphs:
            for run in p.runs:
                if run._element.xml.find("w:br") != -1 and 'type="page"' in run._element.xml:
                    found_break = True
        assert found_break


class TestSetFontStyle:
    def test_sets_font_name(self):
        from docx import Document
        doc = Document()
        p = doc.add_paragraph()
        run = p.add_run("test")
        set_font_style(run, font_name="Arial", font_size=12)
        assert run.font.name == "Arial"
        assert run.font.size.pt == 12

    def test_sets_bold(self):
        from docx import Document
        doc = Document()
        p = doc.add_paragraph()
        run = p.add_run("test")
        set_font_style(run, bold=True)
        assert run.bold is True

    def test_sets_italic(self):
        from docx import Document
        doc = Document()
        p = doc.add_paragraph()
        run = p.add_run("test")
        set_font_style(run, italic=True)
        assert run.italic is True

    def test_sets_subscript(self):
        from docx import Document
        doc = Document()
        p = doc.add_paragraph()
        run = p.add_run("test")
        set_font_style(run, subscript=True)
        assert run.font.subscript is True


class TestSetParagraphFormat:
    def test_sets_alignment(self):
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        doc = Document()
        p = doc.add_paragraph()
        set_paragraph_format(p, alignment=WD_ALIGN_PARAGRAPH.CENTER)
        assert p.alignment == WD_ALIGN_PARAGRAPH.CENTER

    def test_sets_line_spacing(self):
        from docx import Document
        doc = Document()
        p = doc.add_paragraph()
        set_paragraph_format(p, line_spacing=2.0)
        assert p.paragraph_format.line_spacing == 2.0
