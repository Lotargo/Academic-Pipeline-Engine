from __future__ import annotations

from urllib.parse import urlparse

from .models import ModelMetadata, ProviderDefinition


def custom_openai_provider(provider_id: str, base_url: str,
                           models: tuple[ModelMetadata, ...], *, priority: int = 100) -> ProviderDefinition:
    """Create metadata for a custom OpenAI-compatible endpoint without storing its key."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("base_url must be an absolute HTTP(S) URL without embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain query or fragment")
    return ProviderDefinition(id=provider_id, display_name=provider_id, models=models,
                              openai_compatible=True, base_url=base_url.rstrip("/"), priority=priority)
