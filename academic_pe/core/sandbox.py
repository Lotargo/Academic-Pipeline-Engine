from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List


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


_SANDBOX_BLOCK_RE = re.compile(r"```python-run\s*\n(?P<code>.*?)\n```", re.DOTALL)


def run_code_in_sandbox(code: str, timeout_seconds: int = 15) -> SandboxResult:
    # Use mkstemp to safely create a temp file on Windows
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(code)

        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
        )
        return SandboxResult(
            success=(result.returncode == 0),
            stdout=result.stdout,
            stderr=result.stderr,
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
    matches = list(_SANDBOX_BLOCK_RE.finditer(text))
    if not matches:
        return text

    updated_text = text
    for match in reversed(matches):
        code = match.group("code")
        res = run_code_in_sandbox(code, timeout_seconds=timeout_seconds)
        if not res.success:
            error_msg = f"Execution failed with exit code {res.exit_code}.\n"
            if res.stderr:
                error_msg += f"Traceback:\n{res.stderr}"
            raise SandboxExecutionError(error_msg, code, res.stderr)

        replacement = res.stdout.rstrip("\n")
        start, end = match.span()
        updated_text = updated_text[:start] + replacement + updated_text[end:]

    return updated_text
