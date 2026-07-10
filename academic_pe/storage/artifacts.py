from __future__ import annotations

import hashlib
import hmac
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Callable, Iterator, Protocol
from urllib.parse import parse_qs, quote, unquote, urlparse
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ArtifactMetadata:
    storage_key: str
    filename: str
    media_type: str | None
    size_bytes: int
    checksum_sha256: str


class ArtifactStorage(Protocol):
    def upload(self, workspace_id: UUID, filename: str, source: BinaryIO,
               media_type: str | None = None) -> ArtifactMetadata: ...
    def download(self, workspace_id: UUID, storage_key: str) -> bytes: ...
    def delete(self, workspace_id: UUID, storage_key: str) -> None: ...
    def signed_url(self, workspace_id: UUID, storage_key: str, expires_seconds: int = 300) -> str: ...


class StorageAuthorizationError(PermissionError): pass


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}: raise ValueError("invalid artifact filename")
    return name


def _key(workspace_id: UUID, filename: str) -> str:
    return f"workspaces/{workspace_id}/artifacts/{uuid4()}/{_safe_filename(filename)}"


def _authorize_key(workspace_id: UUID, storage_key: str) -> None:
    path = PurePosixPath(storage_key)
    if path.is_absolute() or ".." in path.parts or tuple(path.parts[:2]) != ("workspaces", str(workspace_id)):
        raise StorageAuthorizationError("artifact does not belong to workspace")


def _read(source: BinaryIO) -> tuple[bytes, str]:
    data = source.read()
    if not isinstance(data, bytes): raise TypeError("artifact source must be binary")
    return data, hashlib.sha256(data).hexdigest()


class LocalArtifactStorage:
    def __init__(self, root: str | Path, signing_secret: bytes = b"local-development-only"):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.signing_secret = signing_secret

    def _path(self, workspace_id: UUID, storage_key: str) -> Path:
        _authorize_key(workspace_id, storage_key)
        path = (self.root / Path(*PurePosixPath(storage_key).parts)).resolve()
        if self.root not in path.parents: raise StorageAuthorizationError("invalid storage key")
        return path

    def upload(self, workspace_id: UUID, filename: str, source: BinaryIO,
               media_type: str | None = None) -> ArtifactMetadata:
        key = _key(workspace_id, filename); data, checksum = _read(source); path = self._path(workspace_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".uploading")
        try:
            temporary.write_bytes(data); os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return ArtifactMetadata(key, _safe_filename(filename), media_type, len(data), checksum)

    def download(self, workspace_id: UUID, storage_key: str) -> bytes:
        return self._path(workspace_id, storage_key).read_bytes()

    def delete(self, workspace_id: UUID, storage_key: str) -> None:
        self._path(workspace_id, storage_key).unlink(missing_ok=True)

    def signed_url(self, workspace_id: UUID, storage_key: str, expires_seconds: int = 300) -> str:
        _authorize_key(workspace_id, storage_key)
        if not 1 <= expires_seconds <= 900: raise ValueError("signed URL expiry must be 1..900 seconds")
        # Local URLs are opaque application routes; authorization is checked before issuance.
        expires = int(time.time()) + expires_seconds
        token = hmac.new(self.signing_secret, f"{storage_key}:{expires}".encode(), hashlib.sha256).hexdigest()
        return f"/api/artifacts/local/{quote(storage_key, safe='')}?expires={expires}&token={token}"

    def verify_signed_url(self, url: str, now: int | None = None) -> str:
        parsed = urlparse(url); prefix = "/api/artifacts/local/"
        if not parsed.path.startswith(prefix): raise StorageAuthorizationError("invalid signed URL")
        query = parse_qs(parsed.query)
        try: expires = int(query["expires"][0]); supplied = query["token"][0]
        except (KeyError, IndexError, ValueError) as exc: raise StorageAuthorizationError("invalid signed URL") from exc
        if expires < (int(time.time()) if now is None else now): raise StorageAuthorizationError("signed URL expired")
        key = unquote(parsed.path[len(prefix):])
        expected = hmac.new(self.signing_secret, f"{key}:{expires}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied, expected): raise StorageAuthorizationError("invalid signed URL")
        return key


class ObjectClient(Protocol):
    def put(self, key: str, data: bytes, content_type: str | None, checksum_sha256: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def presign_get(self, key: str, expires_seconds: int) -> str: ...


class ObjectArtifactStorage:
    """S3-compatible storage boundary backed by an injected object client."""
    def __init__(self, client: ObjectClient): self.client = client

    def upload(self, workspace_id: UUID, filename: str, source: BinaryIO,
               media_type: str | None = None) -> ArtifactMetadata:
        key = _key(workspace_id, filename); data, checksum = _read(source)
        self.client.put(key, data, media_type, checksum)
        return ArtifactMetadata(key, _safe_filename(filename), media_type, len(data), checksum)

    def download(self, workspace_id: UUID, storage_key: str) -> bytes:
        _authorize_key(workspace_id, storage_key); return self.client.get(storage_key)

    def delete(self, workspace_id: UUID, storage_key: str) -> None:
        _authorize_key(workspace_id, storage_key); self.client.delete(storage_key)

    def signed_url(self, workspace_id: UUID, storage_key: str, expires_seconds: int = 300) -> str:
        _authorize_key(workspace_id, storage_key)
        if not 1 <= expires_seconds <= 900: raise ValueError("signed URL expiry must be 1..900 seconds")
        return self.client.presign_get(storage_key, expires_seconds)


MembershipCheck = Callable[[UUID, UUID], bool]


def authorize_signed_url(storage: ArtifactStorage, user_id: UUID, workspace_id: UUID,
                         storage_key: str, membership: MembershipCheck,
                         expires_seconds: int = 300) -> str:
    if not membership(user_id, workspace_id):
        raise StorageAuthorizationError("workspace membership required")
    return storage.signed_url(workspace_id, storage_key, expires_seconds)


@contextmanager
def temporary_artifact(suffix: str = "", directory: str | Path | None = None) -> Iterator[Path]:
    """Create a worker temp file and remove it on success or failure."""
    root = Path(directory) if directory else Path(tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix="ape-", suffix=suffix, dir=root)
    os.close(descriptor)
    path = Path(filename)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
