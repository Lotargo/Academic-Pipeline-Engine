from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class LibreOfficeDiscovery:
    available: bool
    executable: Optional[str]
    source: str
    install_hint: str


def _candidate_paths() -> List[str]:
    system = platform.system().lower()
    candidates: List[str] = []

    env_path = os.environ.get("LIBREOFFICE_PATH")
    if env_path:
        candidates.append(env_path)

    if system == "windows":
        candidates.extend(
            [
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ]
        )
    elif system == "darwin":
        candidates.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    else:
        candidates.extend(
            [
                "/usr/bin/soffice",
                "/usr/bin/libreoffice",
                "/usr/local/bin/soffice",
                "/usr/local/bin/libreoffice",
                "/snap/bin/libreoffice",
            ]
        )

    return candidates


def install_hint() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "Install LibreOffice with: winget install TheDocumentFoundation.LibreOffice"
    if system == "darwin":
        return "Install LibreOffice with: brew install --cask libreoffice"
    return "Install LibreOffice with your package manager, e.g. sudo apt install libreoffice"


def discover_soffice() -> LibreOfficeDiscovery:
    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return LibreOfficeDiscovery(True, found, "PATH", install_hint())

    for candidate in _candidate_paths():
        path = Path(candidate)
        if path.exists() and path.is_file():
            return LibreOfficeDiscovery(True, str(path), "known_path", install_hint())

    return LibreOfficeDiscovery(False, None, "not_found", install_hint())
