from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


class RuntimeMode(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass(frozen=True)
class AdapterSelection:
    persistence: str
    storage: str
    dispatcher: str
    secrets: str


@dataclass(frozen=True)
class RuntimeProfile:
    mode: RuntimeMode
    adapters: AdapterSelection
    database_url: str
    storage_root: str | None = None
    broker_url: str | None = None
    object_endpoint: str | None = None
    object_bucket: str | None = None
    kms_key_id: str | None = None

    @property
    def is_local(self) -> bool: return self.mode == RuntimeMode.LOCAL


def load_runtime_profile(env: Mapping[str, str] | None = None) -> RuntimeProfile:
    values = os.environ if env is None else env
    try: mode = RuntimeMode(values.get("APE_RUNTIME_PROFILE", "local").lower())
    except ValueError as exc: raise ValueError("APE_RUNTIME_PROFILE must be local or cloud") from exc
    if mode == RuntimeMode.LOCAL:
        root = values.get("APE_LOCAL_DATA_DIR", "exports/_metadata")
        return RuntimeProfile(mode, AdapterSelection("sqlite", "local", "background", "local_aes"),
            values.get("APE_LOCAL_DATABASE_URL", f"sqlite:///{Path(root) / 'academic_pe.sqlite3'}"),
            storage_root=values.get("APE_LOCAL_STORAGE_DIR", "exports"))
    required = {
        "database_url": values.get("APE_DATABASE_SYNC_URL"),
        "broker_url": values.get("APE_BROKER_URL"),
        "object_endpoint": values.get("APE_OBJECT_ENDPOINT"),
        "object_bucket": values.get("APE_OBJECT_BUCKET"),
        "kms_key_id": values.get("APE_KMS_KEY_ID"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing: raise RuntimeError(f"cloud profile missing settings: {', '.join(missing)}")
    return RuntimeProfile(mode, AdapterSelection("postgresql", "object", "celery", "kms"), **required)
