from academic_pe.core.config import AgentConfig, AppConfig, PipelineConfig, SectionPrompt
from academic_pe.tools.export_qa import export_docx_with_qa, export_pdf_with_qa, render_docx_pages, resolve_export_filename, sanitize_filename
from academic_pe.tools.libreoffice import discover_soffice


def test_discover_soffice_not_found(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr("pathlib.Path.exists", lambda _: False)

    result = discover_soffice()

    assert result.available is False
    assert result.executable is None
    assert "Install LibreOffice" in result.install_hint


def test_render_docx_pages_skips_without_soffice(monkeypatch, tmp_path):
    monkeypatch.setattr("academic_pe.tools.libreoffice.shutil.which", lambda _: None)
    monkeypatch.setattr("academic_pe.tools.libreoffice.Path.exists", lambda _: False)

    docx_path = tmp_path / "missing.docx"
    result = render_docx_pages(str(docx_path), str(tmp_path / "qa"))

    assert result.status == "skipped"
    assert "LibreOffice" in result.message


def test_sanitize_filename():
    assert sanitize_filename('  .Topic: A/B\\C *?"<>|.  ') == "Topic - A-B-C"
    assert sanitize_filename("Normal Word Spaces") == "Normal Word Spaces"
    assert sanitize_filename("Bad\x00Name\x1f") == "BadName"
    assert sanitize_filename("...") == "Untitled"
    assert sanitize_filename("CON.docx") == "_CON.docx"
    assert sanitize_filename("LPT1") == "_LPT1"


def test_resolve_export_filename_sanitizes_explicit_filename():
    assert resolve_export_filename("Ignored", r"nested\bad:name?.docx") == "bad -name.docx"
    assert resolve_export_filename("Ignored", "AUX") == "_AUX.docx"


def test_export_docx_with_qa_creates_docx_when_visual_qa_skipped(monkeypatch, tmp_path):
    monkeypatch.setattr("academic_pe.tools.export_qa.discover_soffice", lambda: type(
        "Discovery",
        (),
        {
            "available": False,
            "executable": None,
            "install_hint": "Install LibreOffice",
        },
    )())

    config = AppConfig(
        agents={
            "writer": AgentConfig(role="Writer", model="mock", temperature=0, system_prompt="test"),
        },
        pipeline=PipelineConfig(
            sections=[SectionPrompt(name="theory", topic="Theory", instruction="")],
            output_dir=str(tmp_path),
            output_filename="paper.docx",
        ),
    )

    result = export_docx_with_qa({"theory": "## Heading\n\nBody text."}, config)

    assert result.filename == "paper.docx"
    assert (tmp_path / "paper.docx").exists()
    assert result.status == "passed"
    assert result.render.status == "skipped"
    assert any(issue.severity == "warning" for issue in result.issues)


def test_export_docx_with_qa_uses_title_for_default_filename(monkeypatch, tmp_path):
    monkeypatch.setattr("academic_pe.tools.export_qa.discover_soffice", lambda: type(
        "Discovery",
        (),
        {
            "available": False,
            "executable": None,
            "install_hint": "Install LibreOffice",
        },
    )())

    config = AppConfig(
        agents={
            "writer": AgentConfig(role="Writer", model="mock", temperature=0, system_prompt="test"),
        },
        pipeline=PipelineConfig(
            sections=[SectionPrompt(name="theory", topic="Theory", instruction="")],
            output_dir=str(tmp_path),
            title='Количественный анализ: A/B "C"',
        ),
    )

    result = export_docx_with_qa({"theory": "## Heading\n\nBody text."}, config)

    assert result.filename == "Количественный анализ - A-B C.docx"
    assert (tmp_path / result.filename).exists()


def test_export_pdf_with_qa_uses_local_docx_conversion(monkeypatch, tmp_path):
    import fitz
    from academic_pe.tools.export_qa import RenderResult

    def fake_convert(docx_path, output_dir, output_filename=None):
        pdf_path = tmp_path / (output_filename or "paper.pdf")
        pdf_doc = fitz.open()
        pdf_doc.new_page()
        pdf_doc.save(pdf_path)
        pdf_doc.close()
        return RenderResult(status="passed", soffice_path="soffice", pdf_path=str(pdf_path), message="ok")

    monkeypatch.setattr("academic_pe.tools.export_qa.convert_docx_to_pdf", fake_convert)

    config = AppConfig(
        agents={
            "writer": AgentConfig(role="Writer", model="mock", temperature=0, system_prompt="test"),
        },
        pipeline=PipelineConfig(
            sections=[SectionPrompt(name="theory", topic="Theory", instruction="")],
            output_dir=str(tmp_path),
            title="Local PDF Experiment",
        ),
    )

    result = export_pdf_with_qa({"theory": "## Heading\n\nBody text."}, config)

    assert result.status == "passed"
    assert result.filename == "Local PDF Experiment.pdf"
    assert (tmp_path / result.filename).exists()
