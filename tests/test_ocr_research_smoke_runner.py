import pytest
from argparse import Namespace

from scripts import ocr_research_smoke_runner as runner


@pytest.fixture(autouse=True)
def mock_runner_root(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "exports" / "_smoke_ocr_research")
    monkeypatch.setattr(runner, "NOTE_PATH", tmp_path / "exports" / "OCR_RESEARCH_SMOKE_NOTES.md")



def _args(tmp_path):
    return Namespace(
        note=str(tmp_path / "notes.md"),
        log_path=str(tmp_path / "stage_log.jsonl"),
    )


def test_scenario_catalog_contains_ocr_and_research_scenarios():
    scenarios = runner.scenario_catalog()

    assert set(scenarios) == {
        "web_search_off_standard_pipeline",
        "web_search_on_researcher_boundary",
        "reference_attachment_planner_only",
        "uploaded_continuation_source",
        "mistral_ocr_direct",
        "real_llm_web_research",
    }


def test_web_search_off_smoke_passes_without_researcher_call(tmp_path):
    scenario = runner.scenario_catalog()["web_search_off_standard_pipeline"]

    assert runner.run_scenario(scenario, _args(tmp_path)) == 0

    note = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert "Result: PASS" in note
    assert "web_search_off_standard_pipeline" in note


def test_web_search_on_boundary_smoke_catches_planner_writer_split(tmp_path):
    scenario = runner.scenario_catalog()["web_search_on_researcher_boundary"]

    assert runner.run_scenario(scenario, _args(tmp_path)) == 0

    log = (tmp_path / "stage_log.jsonl").read_text(encoding="utf-8")
    assert "web search boundary checks completed" in log
    assert "PASS" in log


def test_reference_attachment_smoke_keeps_raw_text_out_of_writer(tmp_path):
    scenario = runner.scenario_catalog()["reference_attachment_planner_only"]

    assert runner.run_scenario(scenario, _args(tmp_path)) == 0

    log = (tmp_path / "stage_log.jsonl").read_text(encoding="utf-8")
    assert "reference attachment boundary checks completed" in log


def test_uploaded_continuation_source_smoke_validates_sections(tmp_path):
    scenario = runner.scenario_catalog()["uploaded_continuation_source"]

    assert runner.run_scenario(scenario, _args(tmp_path)) == 0

    log = (tmp_path / "stage_log.jsonl").read_text(encoding="utf-8")
    assert "introduction" in log
    assert "references" in log


def test_mistral_ocr_smoke_blocks_without_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "is_secret_configured", lambda provider: False)
    scenario = runner.scenario_catalog()["mistral_ocr_direct"]

    assert runner.run_scenario(scenario, _args(tmp_path)) == 2

    note = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert "Result: BLOCKED" in note
    assert "mistral secret is not configured" in note


def test_mistral_ocr_smoke_passes_with_mocked_ocr(monkeypatch, tmp_path):
    marker = "APE-OCR-SCENARIO-MARKER-20260616"
    monkeypatch.setattr(runner, "is_secret_configured", lambda provider: True)
    monkeypatch.setattr(runner, "_make_tiny_pdf", lambda path, marker: path.write_bytes(b"%PDF-pretend"))
    monkeypatch.setattr(runner, "process_file_via_mistral_ocr", lambda filename, file_bytes, mime_type: f"Text {marker}")
    scenario = runner.scenario_catalog()["mistral_ocr_direct"]

    assert runner.run_scenario(scenario, _args(tmp_path)) == 0

    note = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert "Result: PASS" in note
