import zipfile

import pytest

from academic_pe.runtime import (
    BackupError, RuntimeMode, load_runtime_profile, migrate_local_data, rollback_local_data,
)


def test_local_profile_has_no_cloud_dependencies():
    profile = load_runtime_profile({})
    assert profile.mode == RuntimeMode.LOCAL
    assert (profile.adapters.persistence, profile.adapters.storage, profile.adapters.dispatcher) == (
        "sqlite", "local", "background")
    assert profile.broker_url is None and profile.object_endpoint is None and profile.kms_key_id is None


def test_cloud_profile_selects_cloud_adapters_and_validates_settings():
    with pytest.raises(RuntimeError): load_runtime_profile({"APE_RUNTIME_PROFILE": "cloud"})
    profile = load_runtime_profile({"APE_RUNTIME_PROFILE": "cloud", "APE_DATABASE_SYNC_URL": "postgresql://db",
        "APE_BROKER_URL": "amqp://broker", "APE_OBJECT_ENDPOINT": "https://objects.example",
        "APE_OBJECT_BUCKET": "artifacts", "APE_KMS_KEY_ID": "kms/key"})
    assert profile.adapters.persistence == "postgresql" and profile.adapters.dispatcher == "celery"
    assert profile.adapters.storage == "object" and profile.adapters.secrets == "kms"


def test_migration_creates_verified_backup_before_import_and_rollback(tmp_path):
    source = tmp_path / "local"; source.mkdir(); (source / "registry.sqlite3").write_bytes(b"sqlite")
    exports = source / "exports"; exports.mkdir(); (exports / "paper.pdf").write_bytes(b"pdf")
    backup = tmp_path / "backup.zip"; observed = []
    result = migrate_local_data(source, backup, lambda path: observed.append(backup.exists()) or 2)
    assert observed == [True] and result.imported_items == 2
    (source / "registry.sqlite3").write_bytes(b"changed"); (source / "new.txt").write_text("new")
    rollback_local_data(backup, source)
    assert (source / "registry.sqlite3").read_bytes() == b"sqlite"
    assert (source / "exports" / "paper.pdf").read_bytes() == b"pdf"
    assert not (source / "new.txt").exists()


def test_rollback_rejects_tampered_backup(tmp_path):
    backup = tmp_path / "bad.zip"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("data.txt", b"tampered")
        archive.writestr(".ape-backup-manifest.json", '{"data.txt":"wrong"}')
    with pytest.raises(BackupError): rollback_local_data(backup, tmp_path / "restore")
