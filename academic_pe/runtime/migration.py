from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable


class BackupError(RuntimeError): pass


@dataclass(frozen=True)
class MigrationResult:
    backup_path: Path
    imported_items: int


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""): value.update(chunk)
    return value.hexdigest()


def backup_local_data(source_dir: str | Path, backup_path: str | Path) -> Path:
    source, destination = Path(source_dir).resolve(), Path(backup_path).resolve()
    if not source.is_dir(): raise BackupError("local data directory does not exist")
    if destination == source or source in destination.parents: raise BackupError("backup must be outside source directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in source.rglob("*") if path.is_file())
    manifest = {path.relative_to(source).as_posix(): _digest(path) for path in files}
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files: archive.write(path, path.relative_to(source).as_posix())
            archive.writestr(".ape-backup-manifest.json", json.dumps(manifest, sort_keys=True))
        temporary.replace(destination)
    finally: temporary.unlink(missing_ok=True)
    return destination


def _verified_members(archive: zipfile.ZipFile) -> dict[str, str]:
    try: manifest = json.loads(archive.read(".ape-backup-manifest.json"))
    except (KeyError, json.JSONDecodeError) as exc: raise BackupError("invalid backup manifest") from exc
    if not isinstance(manifest, dict): raise BackupError("invalid backup manifest")
    for name, expected in manifest.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts: raise BackupError("unsafe backup path")
        try: actual = hashlib.sha256(archive.read(name)).hexdigest()
        except KeyError as exc: raise BackupError("backup file missing") from exc
        if actual != expected: raise BackupError(f"backup checksum mismatch: {name}")
    return manifest


def rollback_local_data(backup_path: str | Path, target_dir: str | Path) -> None:
    target = Path(target_dir).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup_path) as archive:
        manifest = _verified_members(archive)
        staging = Path(tempfile.mkdtemp(prefix="ape-rollback-", dir=target.parent))
        try:
            for name in manifest:
                destination = staging / Path(*PurePosixPath(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
            previous = target.with_name(target.name + ".pre-rollback")
            if previous.exists(): shutil.rmtree(previous)
            if target.exists(): target.replace(previous)
            staging.replace(target)
            if previous.exists(): shutil.rmtree(previous)
        finally:
            if staging.exists(): shutil.rmtree(staging)


def migrate_local_data(source_dir: str | Path, backup_path: str | Path,
                       importer: Callable[[Path], int]) -> MigrationResult:
    backup = backup_local_data(source_dir, backup_path)
    imported = importer(Path(source_dir).resolve())
    if imported < 0: raise ValueError("importer returned invalid item count")
    return MigrationResult(backup, imported)
