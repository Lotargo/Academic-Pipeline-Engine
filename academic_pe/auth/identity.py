"""External identity verification and idempotent APE account provisioning.

The service profile trusts a token only after an identity adapter has verified
it.  The adapter returns the immutable subject issued by Supabase; email is
display metadata and is never used to locate an existing account.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email_validator import EmailNotValidError, validate_email
import json
import time
from typing import Any, Protocol
from urllib.request import Request, urlopen
from uuid import UUID, uuid5

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from academic_pe.persistence.models import (
    ActorRole,
    ExternalIdentity,
    Membership,
    MembershipRole,
    Organization,
    OrganizationKind,
    User,
)


class IdentityVerificationError(ValueError):
    """A bearer token did not prove a valid external identity."""


class IdentityProvisioningError(RuntimeError):
    """A valid identity cannot safely be associated with an APE account."""


@dataclass(frozen=True, slots=True)
class ExternalIdentityClaims:
    """Normalized, verified claims used at the APE identity boundary."""

    issuer: str
    provider: str
    provider_subject: str
    email: str


class ExternalIdentityVerifier(Protocol):
    def verify(self, bearer_token: str) -> ExternalIdentityClaims: ...


@dataclass(frozen=True, slots=True)
class SupabaseIdentitySettings:
    issuer: str
    jwks_url: str
    audience: str = "authenticated"
    allowed_providers: frozenset[str] = frozenset({"google", "yandex"})
    jwks_ttl: timedelta = timedelta(minutes=10)

    @classmethod
    def from_env(cls, values: Mapping[str, str]) -> "SupabaseIdentitySettings":
        base_url = values.get("APE_SUPABASE_URL", "").rstrip("/")
        if not base_url:
            raise RuntimeError("APE_SUPABASE_URL is required for the Supabase identity adapter")
        issuer = values.get("APE_SUPABASE_JWT_ISSUER", f"{base_url}/auth/v1")
        jwks_url = values.get("APE_SUPABASE_JWKS_URL", f"{issuer.rstrip('/')}/.well-known/jwks.json")
        audience = values.get("APE_SUPABASE_JWT_AUDIENCE", "authenticated")
        providers = frozenset(
            item.strip().lower()
            for item in values.get("APE_SUPABASE_ALLOWED_PROVIDERS", "google,yandex").split(",")
            if item.strip()
        )
        if not providers:
            raise RuntimeError("APE_SUPABASE_ALLOWED_PROVIDERS must not be empty")
        return cls(issuer=issuer, jwks_url=jwks_url, audience=audience, allowed_providers=providers)


JwksFetcher = Callable[[str], Mapping[str, Any]]


def fetch_jwks(url: str) -> Mapping[str, Any]:
    """Fetch a small JWKS document without logging URLs, headers, or tokens."""

    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - URL is trusted configuration.
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network details vary by runtime.
        raise IdentityVerificationError("identity signing keys are unavailable") from exc
    if not isinstance(payload, Mapping) or not isinstance(payload.get("keys"), list):
        raise IdentityVerificationError("identity signing keys are invalid")
    return payload


@dataclass(slots=True)
class SupabaseJwtVerifier:
    """Validate asymmetric Supabase access JWTs with bounded JWKS refreshes."""

    settings: SupabaseIdentitySettings
    jwks_fetcher: JwksFetcher = fetch_jwks
    clock: Callable[[], float] = time.monotonic
    _keys: dict[str, jwt.PyJWK] = field(default_factory=dict, init=False)
    _refresh_after: float = field(default=0.0, init=False)

    _ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA")

    def verify(self, bearer_token: str) -> ExternalIdentityClaims:
        try:
            header = jwt.get_unverified_header(bearer_token)
            kid = header.get("kid")
            algorithm = header.get("alg")
        except jwt.PyJWTError as exc:
            raise IdentityVerificationError("invalid identity token") from exc
        if not isinstance(kid, str) or not kid or algorithm not in self._ALGORITHMS:
            raise IdentityVerificationError("invalid identity token")

        key = self._key_for(kid)
        if key is None:
            self._refresh(force=True)
            key = self._keys.get(kid)
        if key is None:
            raise IdentityVerificationError("identity signing key is unknown")

        try:
            claims = jwt.decode(
                bearer_token,
                key.key,
                algorithms=[algorithm],
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise IdentityVerificationError("invalid identity token") from exc
        return self._claims_from_verified_jwt(claims)

    def _key_for(self, kid: str) -> jwt.PyJWK | None:
        if self.clock() >= self._refresh_after:
            self._refresh()
        return self._keys.get(kid)

    def _refresh(self, *, force: bool = False) -> None:
        if not force and self.clock() < self._refresh_after:
            return
        document = self.jwks_fetcher(self.settings.jwks_url)
        try:
            keys = {
                item["kid"]: jwt.PyJWK.from_dict(dict(item))
                for item in document["keys"]
                if isinstance(item, Mapping) and isinstance(item.get("kid"), str)
            }
        except (KeyError, TypeError, jwt.PyJWTError) as exc:
            raise IdentityVerificationError("identity signing keys are invalid") from exc
        if not keys:
            raise IdentityVerificationError("identity signing keys are invalid")
        self._keys = keys
        self._refresh_after = self.clock() + self.settings.jwks_ttl.total_seconds()

    def _claims_from_verified_jwt(self, claims: Mapping[str, Any]) -> ExternalIdentityClaims:
        if claims.get("role") != "authenticated":
            raise IdentityVerificationError("invalid identity token")
        raw_subject = claims.get("sub")
        try:
            subject = str(UUID(str(raw_subject)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise IdentityVerificationError("invalid identity subject") from exc

        metadata = claims.get("app_metadata")
        provider = metadata.get("provider") if isinstance(metadata, Mapping) else None
        if not isinstance(provider, str) or provider.lower() not in self.settings.allowed_providers:
            raise IdentityVerificationError("unsupported identity provider")
        raw_email = claims.get("email")
        if not isinstance(raw_email, str):
            raise IdentityVerificationError("identity email is missing")
        try:
            email = validate_email(raw_email, check_deliverability=False).normalized
        except EmailNotValidError as exc:
            raise IdentityVerificationError("identity email is invalid") from exc
        return ExternalIdentityClaims(
            issuer=self.settings.issuer,
            provider=provider.lower(),
            provider_subject=subject,
            email=email,
        )


@dataclass(frozen=True, slots=True)
class MockExternalIdentityVerifier:
    """Deterministic development-only verifier, visibly separate from OAuth."""

    issuer: str = "mock://academic-pipeline-engine"
    allowed_providers: frozenset[str] = frozenset({"google", "yandex"})

    def verify(self, bearer_token: str) -> ExternalIdentityClaims:
        prefix, separator, payload = bearer_token.partition(":")
        if prefix != "mock" or not separator:
            raise IdentityVerificationError("invalid mock identity token")

        provider, email_separator, raw_email = payload.partition(":")
        if provider.lower() == "email" and email_separator:
            try:
                email = validate_email(raw_email, check_deliverability=False).normalized
            except EmailNotValidError as exc:
                raise IdentityVerificationError("invalid mock identity token") from exc
            subject = str(uuid5(UUID("af4fe50a-86c9-4574-afc6-b8bc0950bc2c"), f"email:{email}"))
            return ExternalIdentityClaims(
                issuer=self.issuer,
                provider="email",
                provider_subject=subject,
                email=email,
            )

        if email_separator or provider.lower() not in self.allowed_providers:
            raise IdentityVerificationError("invalid mock identity token")
        normalized_provider = provider.lower()
        subject = str(uuid5(UUID("af4fe50a-86c9-4574-afc6-b8bc0950bc2c"), normalized_provider))
        return ExternalIdentityClaims(
            issuer=self.issuer,
            provider=normalized_provider,
            provider_subject=subject,
            email=f"mock-{normalized_provider}@example.invalid",
        )


def provision_external_identity(session: Session, identity: ExternalIdentityClaims) -> User:
    """Resolve or create a user, personal workspace, and external identity atomically.

    A pre-existing email never grants ownership of a new external identity.  A
    user who needs to connect a provider to a legacy account must do so through
    a future authenticated linking flow.
    """

    existing = session.scalar(select(ExternalIdentity).where(
        ExternalIdentity.issuer == identity.issuer,
        ExternalIdentity.provider_subject == identity.provider_subject,
    ))
    if existing is not None:
        user = session.get(User, existing.user_id)
        if user is None:
            raise IdentityProvisioningError("external identity has no user")
        return user

    try:
        user = User(
            email=identity.email.lower(),
            password_hash="external-identity-only",
            actor_role=ActorRole.USER,
        )
        session.add(user)
        session.flush()
        organization = Organization(
            owner_user_id=user.id,
            kind=OrganizationKind.PERSONAL,
            name="Personal",
        )
        session.add(organization)
        session.flush()
        from academic_pe.persistence.models import Workspace
        workspace = Workspace(organization_id=organization.id, name="Personal")
        session.add(workspace)
        session.flush()
        session.add(Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            membership_role=MembershipRole.OWNER,
        ))
        session.add(ExternalIdentity(
            user_id=user.id,
            issuer=identity.issuer,
            provider=identity.provider,
            provider_subject=identity.provider_subject,
        ))
        session.commit()
        return user
    except IntegrityError as exc:
        session.rollback()
        existing = session.scalar(select(ExternalIdentity).where(
            ExternalIdentity.issuer == identity.issuer,
            ExternalIdentity.provider_subject == identity.provider_subject,
        ))
        if existing is not None:
            user = session.get(User, existing.user_id)
            if user is not None:
                return user
        raise IdentityProvisioningError("identity cannot be linked to this account") from exc
