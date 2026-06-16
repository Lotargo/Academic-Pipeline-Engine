from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academic_pe.core.config import ExportQAConfig, ProviderEnum
from academic_pe.core.secrets import is_secret_configured
from academic_pe.tools.export_vision_qa import run_export_vision_qa

LOG_DIR = ROOT / "exports" / "_smoke_export_vision_qa"
NOTE_PATH = ROOT / "dev_docs" / "EXPORT_VISION_QA_SMOKE_NOTES.md"


def _write_note(line: str = "") -> None:
    NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTE_PATH.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def _write_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _make_smoke_png(path: Path, *, broken: bool) -> None:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=900, height=1200)
    page.insert_text((72, 72), "Academic PE Export QA Smoke", fontsize=24, fontname="helv")
    if broken:
        page.insert_text((72, 145), "Visible defect candidate:", fontsize=14, fontname="helv")
        page.insert_text((72, 185), "[Contributor Covenant](https://example.test/code_of_conduct)", fontsize=16, fontname="cour")
        page.insert_text((72, 235), "| Parameter | Type | Description |", fontsize=14, fontname="cour")
        page.insert_text((72, 265), "|---|---|---|", fontsize=14, fontname="cour")
        page.insert_text((72, 295), "```python", fontsize=14, fontname="cour")
    else:
        page.insert_text((72, 145), "No obvious rendering defects are present.", fontsize=14, fontname="helv")
        page.insert_text((72, 190), "Code of conduct: Contributor Covenant", fontsize=14, fontname="helv")
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(path)
    pdf.close()


def run_smoke(*, provider: str, model: str, broken: bool) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scenario = "broken_export_visual" if broken else "clean_export_visual"
    run_dir = LOG_DIR / timestamp / scenario
    image_path = run_dir / "page-1.png"
    log_path = run_dir / "events.jsonl"

    _make_smoke_png(image_path, broken=broken)
    _write_event(log_path, {"ts": datetime.now().isoformat(timespec="seconds"), "kind": "image", "path": str(image_path)})

    if provider != "mock" and not is_secret_configured(provider):
        message = f"Blocked: missing configured provider secret for {provider}."
        _write_event(log_path, {"ts": datetime.now().isoformat(timespec="seconds"), "kind": "blocked", "message": message})
        print(message, flush=True)
        return 2

    cfg = ExportQAConfig(
        provider=ProviderEnum(provider) if provider in ProviderEnum._value2member_map_ else ProviderEnum.mock,
        model=model,
        temperature=0.1,
    )
    report = run_export_vision_qa([str(image_path)], config=cfg, provider=provider, model=model)
    _write_event(
        log_path,
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "kind": "vision_qa_report",
            "report": report.to_dict(),
        },
    )

    _write_note(f"## {datetime.now().isoformat(timespec='seconds')} - {scenario}")
    _write_note(f"- Provider: `{provider}`")
    _write_note(f"- Model: `{model}`")
    _write_note(f"- Image: `{image_path}`")
    _write_note(f"- Status: `{report.status}`")
    _write_note(f"- Summary: {report.summary}")
    for finding in report.findings:
        _write_note(f"- Finding: `{finding.severity}` `{finding.category}` page={finding.page}: {finding.message}")
    _write_note()

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), flush=True)
    return 0 if report.status in {"passed", "warning", "failed"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Export Vision QA smoke test.")
    parser.add_argument("--provider", default="mock", choices=["mock", "zen", "openai", "custom_openai"])
    parser.add_argument("--model", default="mimo-v2.5-free")
    parser.add_argument("--clean", action="store_true", help="Use a clean synthetic export image instead of a visibly broken one.")
    args = parser.parse_args()
    return run_smoke(provider=args.provider, model=args.model, broken=not args.clean)


if __name__ == "__main__":
    raise SystemExit(main())
