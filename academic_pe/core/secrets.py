import json
import os
from typing import Optional, Dict

SECRETS_PATH = "config/secrets.json"

def get_secret(provider_name: str) -> Optional[str]:
    """
    Retrieve the API key for a given provider.
    First tries config/secrets.json, then falls back to environment variables.
    """
    # 1. Try config/secrets.json
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                secrets = json.load(f)
                if isinstance(secrets, dict) and secrets.get(provider_name):
                    return secrets[provider_name]
        except Exception:
            pass

    # 2. Environment variable fallback
    if provider_name == "openai":
        return os.getenv("OPENAI_API_KEY")
    elif provider_name == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY")
    elif provider_name == "google":
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    elif provider_name == "custom_openai":
        return os.getenv("CUSTOM_API_KEY")
    elif provider_name == "lm_studio":
        return os.getenv("LM_STUDIO_API_KEY") or "lm-studio"
    elif provider_name == "zen":
        return os.getenv("ZEN_API_KEY")
    return None

def save_secret(provider_name: str, key: str) -> None:
    """
    Save the API key for a provider to config/secrets.json.
    """
    secrets: Dict[str, str] = {}
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                secrets = json.load(f)
                if not isinstance(secrets, dict):
                    secrets = {}
        except Exception:
            secrets = {}

    secrets[provider_name] = key
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        json.dump(secrets, f, indent=2)

def is_secret_configured(provider_name: str) -> bool:
    """
    Check if a secret is configured (either in JSON or env).
    """
    return bool(get_secret(provider_name))
