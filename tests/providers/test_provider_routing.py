from uuid import uuid4

import pytest

from academic_pe.providers import (
    Capability, CredentialCandidate, CredentialSource, InMemoryProviderRegistry,
    ModelMetadata, ProviderDefinition, ProviderHealth, ProviderRouter, RouteRequest,
)
from academic_pe.providers.openai_compatible import custom_openai_provider
from academic_pe.providers.router import ProviderRoutingError


TEXT = frozenset({Capability.TEXT_GENERATION})


def definition(name: str, priority: int = 100) -> ProviderDefinition:
    return ProviderDefinition(name, (ModelMetadata(f"{name}-model", TEXT),), priority=priority)


def test_user_byok_is_selected_before_platform_credential():
    registry = InMemoryProviderRegistry(); registry.register(definition("openai"))
    user, platform = uuid4(), uuid4()
    router = ProviderRouter(registry, lambda request, provider: [
        CredentialCandidate(provider, CredentialSource.PLATFORM, platform),
        CredentialCandidate(provider, CredentialSource.USER, user),
    ])
    result = router.route(RouteRequest(Capability.TEXT_GENERATION, uuid4()))
    assert (result.credential_source, result.credential_id) == (CredentialSource.USER, user)


def test_platform_route_can_be_selected_when_byok_is_disabled():
    registry = InMemoryProviderRegistry(); registry.register(definition("openai"))
    platform = uuid4()
    router = ProviderRouter(registry, lambda request, provider: [
        CredentialCandidate(provider, CredentialSource.USER, uuid4()),
        CredentialCandidate(provider, CredentialSource.PLATFORM, platform),
    ])
    result = router.route(RouteRequest(Capability.TEXT_GENERATION, uuid4(), allow_user=False))
    assert result.credential_id == platform


def test_open_circuit_falls_back_deterministically():
    registry = InMemoryProviderRegistry()
    registry.register(definition("primary", 1)); registry.register(definition("backup", 2))
    router = ProviderRouter(registry,
        lambda request, provider: [CredentialCandidate(provider, CredentialSource.PLATFORM, uuid4())],
        lambda provider: ProviderHealth.OPEN if provider == "primary" else ProviderHealth.HEALTHY)
    assert router.route(RouteRequest(Capability.TEXT_GENERATION, uuid4())).provider_id == "backup"


def test_custom_openai_compatible_provider_contract():
    registry = InMemoryProviderRegistry()
    registry.register(custom_openai_provider("lab", "https://llm.example/v1/", (ModelMetadata("lab-1", TEXT),)))
    credential = uuid4()
    result = ProviderRouter(registry, lambda request, provider: [
        CredentialCandidate(provider, CredentialSource.USER, credential)
    ]).route(RouteRequest(Capability.TEXT_GENERATION, uuid4(), preferred_providers=("lab",)))
    assert result.base_url == "https://llm.example/v1"
    assert result.model_id == "lab-1"


def test_missing_capability_or_credentials_has_no_route():
    registry = InMemoryProviderRegistry(); registry.register(definition("openai"))
    with pytest.raises(ProviderRoutingError):
        ProviderRouter(registry, lambda request, provider: []).route(
            RouteRequest(Capability.VISION, uuid4()))


@pytest.mark.parametrize("url", ["relative/v1", "ftp://example/v1", "https://key@example/v1", "https://example/v1?q=x"])
def test_custom_endpoint_rejects_unsafe_shapes(url):
    with pytest.raises(ValueError):
        custom_openai_provider("bad", url, (ModelMetadata("m", TEXT),))
