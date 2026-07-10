from io import BytesIO
from uuid import uuid4

import pytest

from academic_pe.storage import (
    LocalArtifactStorage, ObjectArtifactStorage, StorageAuthorizationError,
    authorize_signed_url, temporary_artifact,
)


class FakeObjectClient:
    def __init__(self): self.objects = {}
    def put(self, key, data, content_type, checksum_sha256): self.objects[key] = data
    def get(self, key): return self.objects[key]
    def delete(self, key): self.objects.pop(key, None)
    def presign_get(self, key, expires_seconds): return f"https://objects.example/{key}?ttl={expires_seconds}"


@pytest.fixture(params=["local", "object"])
def storage(request, tmp_path):
    return (LocalArtifactStorage(tmp_path, b"test-secret") if request.param == "local"
            else ObjectArtifactStorage(FakeObjectClient()))


def test_storage_contract_upload_download_delete_and_checksum(storage):
    workspace = uuid4(); payload = b"artifact body"
    metadata = storage.upload(workspace, "../paper.pdf", BytesIO(payload), "application/pdf")
    assert metadata.storage_key.startswith(f"workspaces/{workspace}/artifacts/")
    assert metadata.filename == "paper.pdf" and metadata.size_bytes == len(payload)
    assert len(metadata.checksum_sha256) == 64
    assert storage.download(workspace, metadata.storage_key) == payload
    storage.delete(workspace, metadata.storage_key)
    with pytest.raises((FileNotFoundError, KeyError)): storage.download(workspace, metadata.storage_key)


def test_cross_tenant_access_and_signed_url_are_protected(storage):
    owner, intruder, user = uuid4(), uuid4(), uuid4()
    metadata = storage.upload(owner, "chart.png", BytesIO(b"png"), "image/png")
    with pytest.raises(StorageAuthorizationError): storage.download(intruder, metadata.storage_key)
    with pytest.raises(StorageAuthorizationError): authorize_signed_url(
        storage, user, owner, metadata.storage_key, lambda *_: False)
    url = authorize_signed_url(storage, user, owner, metadata.storage_key, lambda *_: True, 60)
    assert url
    with pytest.raises(ValueError): storage.signed_url(owner, metadata.storage_key, 3600)


def test_local_signed_url_rejects_tampering_and_expiry(tmp_path):
    storage = LocalArtifactStorage(tmp_path, b"secret")
    workspace = uuid4(); metadata = storage.upload(workspace, "x.txt", BytesIO(b"x"))
    url = storage.signed_url(workspace, metadata.storage_key, 60)
    assert storage.verify_signed_url(url) == metadata.storage_key
    with pytest.raises(StorageAuthorizationError): storage.verify_signed_url(url + "bad")
    with pytest.raises(StorageAuthorizationError): storage.verify_signed_url(url, now=10**12)


def test_temporary_artifact_is_removed_after_success_and_failure(tmp_path):
    with temporary_artifact(".docx", tmp_path) as path:
        path.write_bytes(b"docx"); first = path
    assert not first.exists()
    with pytest.raises(RuntimeError):
        with temporary_artifact(".pdf", tmp_path) as path:
            second = path; raise RuntimeError("render failed")
    assert not second.exists()
