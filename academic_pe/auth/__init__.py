from academic_pe.auth.router import create_auth_router
from academic_pe.auth.identity import (
    ExternalIdentityClaims,
    IdentityProvisioningError,
    IdentityVerificationError,
    MockExternalIdentityVerifier,
    SupabaseIdentitySettings,
    SupabaseJwtVerifier,
)
from academic_pe.auth.security import AuthSettings

__all__ = [
    "AuthSettings",
    "ExternalIdentityClaims",
    "IdentityProvisioningError",
    "IdentityVerificationError",
    "MockExternalIdentityVerifier",
    "SupabaseIdentitySettings",
    "SupabaseJwtVerifier",
    "create_auth_router",
]
