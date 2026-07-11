from __future__ import annotations

import os
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List

from academic_pe.core.calculation_audit import CalculationEntry


class SandboxExecutionError(Exception):
    def __init__(self, message: str, code: str, stderr: str):
        super().__init__(message)
        self.code = code
        self.stderr = stderr


@dataclass(frozen=True)
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int


@dataclass(frozen=True)
class SandboxDocumentResult:
    """Rendered sandbox output plus calculation records kept out of document text."""

    text: str
    calculation_entries: list[CalculationEntry]


_SANDBOX_BLOCK_RE = re.compile(r"```python-run\s*\n(?P<code>.*?)\n```", re.DOTALL)
_CALCULATION_LEDGER_PREFIX = "CALCULATION_LEDGER_JSON:"


def run_code_in_sandbox(code: str, timeout_seconds: int = 15) -> SandboxResult:
    # Use mkstemp to safely create a temp file on Windows
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(code)

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, "-X", "utf8", path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return SandboxResult(
            success=(result.returncode == 0),
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired as e:
        # In python subprocess, TimeoutExpired has stdout and stderr attributes (as bytes or str depending on text=True)
        stdout_val = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", errors="replace")
        stderr_val = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", errors="replace")
        if not stderr_val:
            stderr_val = "TimeoutExpired: execution took longer than limit."
        return SandboxResult(
            success=False,
            stdout=stdout_val,
            stderr=stderr_val,
            exit_code=-1,
        )
    except Exception as e:
        return SandboxResult(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=-1,
        )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def execute_sandbox_blocks(text: str, timeout_seconds: int = 15) -> str:
    return execute_sandbox_blocks_with_metadata(text, timeout_seconds=timeout_seconds).text


def execute_sandbox_blocks_with_metadata(
    text: str,
    timeout_seconds: int = 15,
) -> SandboxDocumentResult:
    """Execute document code blocks and retain declared calculations as metadata.

    A block can emit one line in the form ``CALCULATION_LEDGER_JSON:{...}``.
    The JSON object must contain an ``entries`` list compatible with
    :class:`CalculationEntry`.  The marker is removed from the rendered text so
    calculation transport metadata never reaches the exported document.
    """
    matches = list(_SANDBOX_BLOCK_RE.finditer(text))
    if not matches:
        return SandboxDocumentResult(text=text, calculation_entries=[])

    updated_text = text
    calculation_entries: list[CalculationEntry] = []
    for match in reversed(matches):
        code = match.group("code")
        res = run_code_in_sandbox(code, timeout_seconds=timeout_seconds)
        if not res.success:
            error_msg = f"Execution failed with exit code {res.exit_code}.\n"
            if res.stderr:
                error_msg += f"Traceback:\n{res.stderr}"
            raise SandboxExecutionError(error_msg, code, res.stderr)

        replacement, entries = _split_calculation_ledger_output(res.stdout, code)
        calculation_entries[0:0] = entries
        start, end = match.span()
        updated_text = updated_text[:start] + replacement + updated_text[end:]

    return SandboxDocumentResult(text=updated_text, calculation_entries=calculation_entries)


def _split_calculation_ledger_output(stdout: str, code: str) -> tuple[str, list[CalculationEntry]]:
    rendered_lines: list[str] = []
    entries: list[CalculationEntry] = []
    for line in stdout.splitlines():
        if not line.startswith(_CALCULATION_LEDGER_PREFIX):
            rendered_lines.append(line)
            continue
        raw_payload = line[len(_CALCULATION_LEDGER_PREFIX):].strip()
        try:
            payload = json.loads(raw_payload)
            raw_entries = payload.get("entries") if isinstance(payload, dict) else None
            if not isinstance(raw_entries, list):
                raise ValueError("payload must be an object with an 'entries' list")
            entries.extend(CalculationEntry.model_validate(item) for item in raw_entries)
        except (TypeError, ValueError) as exc:
            raise SandboxExecutionError(
                f"Invalid CALCULATION_LEDGER_JSON output: {exc}",
                code,
                str(exc),
            ) from exc
    return "\n".join(rendered_lines).rstrip("\n"), entries
