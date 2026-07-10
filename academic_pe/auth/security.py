from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret: str
    issuer: str = "academic-pe"
    access_ttl: timedelta = timedelta(minutes=15)
    refresh_ttl: timedelta = timedelta(days=30)

    def __post_init__(self) -> None:
        if len(self.jwt_secret) < 32:
            raise ValueError("jwt_secret must contain at least 32 characters")


_passwords = PasswordHash.recommended()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return _passwords.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return _passwords.verify(password, encoded)
    except Exception:
        # Legacy users carry a reset marker rather than a password hash.
        return False


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: UUID, role: str, token_version: int, settings: AuthSettings) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "role": role, "ver": token_version, "typ": "access",
              "iss": settings.issuer, "iat": now, "exp": now + settings.access_ttl}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: AuthSettings) -> dict[str, Any]:
    claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.issuer)
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return claims
