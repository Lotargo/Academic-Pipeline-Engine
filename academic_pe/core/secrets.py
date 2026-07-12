from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping, Optional


SECRETS_PATH = "config/secrets.json"

# Public compatibility names map to canonical environment variable names.  The
# resolver itself is provider-agnostic: new providers can use a standard name
# such as ``JINA_API_KEY`` without adding another conditional branch.
_COMPATIBILITY_NAMES: Mapping[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "custom_openai": ("CUSTOM_API_KEY",),
    "lm_studio": ("LM_STUDIO_API_KEY",),
    "zen": ("ZEN_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "jina": ("JINA_API_KEY",),
    "langsearch": ("LANGSEARCH_API_KEY",),
    "qdrant": ("QDRANT_API_KEY",),
}


class SecretResolver:
    """Resolve a named secret from environment first, then a local JSON file."""

    def __init__(self, path: str | Path = SECRETS_PATH) -> None:
        self.path = Path(path)

    def resolve(self, secret_name: str) -> Optional[str]:
        names = self.candidate_names(secret_name)
        for name in names:
            value = os.getenv(name)
            if value and value.strip():
                return value

        stored = self._load()
        for name in (*names, secret_name):
            value = stored.get(name)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def save(self, secret_name: str, value: str) -> None:
        canonical_name = self.candidate_names(secret_name)[0]
        stored = self._load()
        stored[canonical_name] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(stored, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def configured(self, secret_name: str) -> bool:
        return bool(self.resolve(secret_name))

    @staticmethod
    def candidate_names(secret_name: str) -> tuple[str, ...]:
        normalized = secret_name.strip()
        if not normalized:
            raise ValueError("secret name must not be empty")
        compatibility = _COMPATIBILITY_NAMES.get(normalized.casefold())
        if compatibility:
            return compatibility
        if normalized == normalized.upper() and "_" in normalized:
            return (normalized,)
        return (f"{normalized.upper().replace('-', '_')}_API_KEY",)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): value for key, value in payload.items() if isinstance(value, str)}


def get_secret(provider_name: str) -> Optional[str]:
    """Compatibility API for existing provider callers."""

    value = SecretResolver().resolve(provider_name)
    if value is None and provider_name.casefold() == "lm_studio":
        return "lm-studio"
    return value


def save_secret(provider_name: str, key: str) -> None:
    SecretResolver().save(provider_name, key)


def is_secret_configured(provider_name: str) -> bool:
    return bool(get_secret(provider_name))
