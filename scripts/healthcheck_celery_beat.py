#!/usr/bin/env python3
"""Return success only while the container's Celery Beat process is alive."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            command = (process / "cmdline").read_bytes()
        except OSError:
            continue
        if b"celery" in command and b"beat" in command:
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
