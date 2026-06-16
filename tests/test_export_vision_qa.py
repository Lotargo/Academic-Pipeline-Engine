import json

from academic_pe.tools.export_vision_qa import _parse_vision_report, run_export_vision_qa
from scripts.export_vision_qa_smoke_runner import run_smoke


def test_parse_vision_report_json():
    raw = json.dumps(
        {
            "status": "warning",
            "summary": "One minor layout issue.",
            "findings": [
                {
                    "severity": "warning",
                    "category": "minor_visual",
                    "page": 1,
                    "message": "A table is close to the page boundary.",
                    "suggested_owner": "renderer",
                }
            ],
        }
    )

    report = _parse_vision_report(raw)

    assert report.status == "warning"
    assert report.summary == "One minor layout issue."
    assert len(report.findings) == 1
    assert report.findings[0].category == "minor_visual"


def test_parse_vision_report_non_json_is_warning():
    report = _parse_vision_report("Looks fine to me.")

    assert report.status == "warning"
    assert report.findings[0].message == "Vision QA response could not be parsed as JSON."


def test_mock_export_vision_qa(tmp_path):
    image_path = tmp_path / "page-1.png"
    image_path.write_bytes(b"not really an image but mock does not inspect it")

    report = run_export_vision_qa([str(image_path)], provider="mock", model="mock")

    assert report.status == "passed"
    assert "Mock vision QA inspected" in report.summary


def test_export_vision_qa_smoke_runner_mock(tmp_path, monkeypatch):
    import scripts.export_vision_qa_smoke_runner as runner

    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "exports" / "_smoke_export_vision_qa")
    monkeypatch.setattr(runner, "NOTE_PATH", tmp_path / "dev_docs" / "EXPORT_VISION_QA_SMOKE_NOTES.md")

    exit_code = run_smoke(provider="mock", model="mock", broken=True)

    assert exit_code == 0
    assert runner.NOTE_PATH.exists()
    assert list(runner.LOG_DIR.glob("**/events.jsonl"))
