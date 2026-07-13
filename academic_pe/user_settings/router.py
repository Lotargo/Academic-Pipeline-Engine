"""HTTP boundary for personal and workspace-member settings.

The client never supplies a user or workspace identifier. Those boundaries are
derived from the verified principal and active membership on every request.
"""

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from academic_pe.persistence.models import (
    Credential,
    CredentialStatus,
    Membership,
    MembershipStatus,
    TenantStatus,
    UserPreference,
    Workspace,
    WorkspaceMemberSettings,
)
from academic_pe.secrets.crypto import LocalAesKeyWrapper
from academic_pe.secrets.store import SqlAlchemyCredentialStore


Language = Literal["ru", "en"]
Theme = Literal["light", "dark", "system"]
CredentialPolicy = Literal["platform_first", "user_only"]


class EditorDefaults(BaseModel):
    academic_mode: bool = False
    web_search_enabled: bool = False
    author: str | None = Field(default=None, max_length=200)
    artifact_override: str | None = Field(default=None, max_length=100)


class PersonalSettingsUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    language: Language | None = None
    theme: Theme | None = None
    editor_defaults: EditorDefaults | None = None


class ProviderSelectionUpdate(BaseModel):
    provider_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    credential_policy: CredentialPolicy


class CredentialCreate(BaseModel):
    provider_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    secret: str = Field(min_length=1, max_length=10_000)


class CredentialReplace(BaseModel):
    secret: str = Field(min_length=1, max_length=10_000)


_CATALOG = {
    "openai": {"display_name": "OpenAI", "models": ("gpt-5.4", "gpt-5.4-mini")},
    "anthropic": {"display_name": "Anthropic", "models": ("Claude Opus 4.8", "Claude Sonnet 4.6", "Claude Haiku 4.5")},
    "google": {"display_name": "Google", "models": ("gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-3.1-flash-lite")},
}


def _platform_provider_ids() -> set[str]:
    return {
        item.strip().lower()
        for item in os.getenv("APE_PLATFORM_PROVIDER_IDS", "").split(",")
        if item.strip()
    }


def _providers() -> list[dict[str, object]]:
    platform_ids = _platform_provider_ids()
    return [
        {
            "id": provider_id,
            "display_name": definition["display_name"],
            "models": [{"id": model, "capabilities": ["text_generation"]} for model in definition["models"]],
            "availability": "available" if provider_id in platform_ids else "unavailable",
            "supports_byok": True,
        }
        for provider_id, definition in _CATALOG.items()
    ]


def _credential_wrapper() -> LocalAesKeyWrapper | None:
    """Return the service-dev wrapper without inventing a production KMS adapter."""

    if os.getenv("APE_CREDENTIAL_WRAPPER") != "local-aes":
        return None
    raw = os.getenv("APE_CREDENTIAL_MASTER_KEY")
    if not raw:
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        key = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, binascii.Error, UnicodeEncodeError) as exc:
        raise RuntimeError("APE_CREDENTIAL_MASTER_KEY must be URL-safe base64 for exactly 32 bytes") from exc
    if len(key) != 32:
        raise RuntimeError("APE_CREDENTIAL_MASTER_KEY must decode to exactly 32 bytes")
    return LocalAesKeyWrapper(key, os.getenv("APE_CREDENTIAL_KEY_ID", "service-dev/local-aes-v1"))


def _metadata(credential: Credential) -> dict[str, str]:
    return {
        "id": str(credential.id),
        "provider_id": credential.provider,
        "label": credential.label,
        "status": credential.status.value,
        # The UI deliberately renders a fixed mask; never derive a mask from a secret.
        "masked_value": "••••••••",
        "validation": "unknown",
        "created_at": credential.created_at.isoformat(),
        "updated_at": credential.updated_at.isoformat(),
    }


def create_user_settings_router(
    session_factory: Callable[[], Session], principal_dependency: Callable[..., Any]
) -> APIRouter:
    router = APIRouter(tags=["personal-settings"])

    def session_dep():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def active_workspace(current: Any, session: Session) -> tuple[Membership, Workspace]:
        row = session.execute(
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(
                Membership.user_id == current.user_id,
                Membership.status == MembershipStatus.ACTIVE,
                Workspace.status == TenantStatus.ACTIVE,
            )
            .order_by(Workspace.created_at)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="workspace not found")
        return row

    def member_settings(
        session: Session, workspace_id: UUID, user_id: UUID, *, create: bool
    ) -> WorkspaceMemberSettings | None:
        record = session.scalar(
            select(WorkspaceMemberSettings).where(
                WorkspaceMemberSettings.workspace_id == workspace_id,
                WorkspaceMemberSettings.user_id == user_id,
            )
        )
        if record is None and create:
            record = WorkspaceMemberSettings(workspace_id=workspace_id, user_id=user_id)
            session.add(record)
            session.flush()
        return record

    def user_preferences(session: Session, user_id: UUID, *, create: bool) -> UserPreference | None:
        record = session.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
        if record is None and create:
            record = UserPreference(user_id=user_id)
            session.add(record)
            session.flush()
        return record

    def personal_snapshot(current: Any, session: Session) -> dict[str, object]:
        membership, workspace = active_workspace(current, session)
        preferences = user_preferences(session, current.user_id, create=False)
        workspace_settings = member_settings(session, workspace.id, current.user_id, create=False)
        try:
            defaults = EditorDefaults.model_validate(
                workspace_settings.editor_defaults_json if workspace_settings else {}
            )
        except ValueError:
            defaults = EditorDefaults()
        return {
            "profile": {
                "display_name": preferences.display_name if preferences else None,
                "language": preferences.language if preferences else "ru",
                "theme": preferences.theme if preferences else "system",
            },
            "editor_defaults": defaults.model_dump(mode="json"),
            "workspace": {
                "id": str(workspace.id),
                "name": workspace.name,
                "role": membership.membership_role.value,
            },
        }

    @router.get("/api/settings/me")
    def get_personal_settings(
        current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)
    ):
        return personal_snapshot(current, session)

    @router.put("/api/settings/me")
    def update_personal_settings(
        body: PersonalSettingsUpdate,
        current: Any = Depends(principal_dependency),
        session: Session = Depends(session_dep),
    ):
        _, workspace = active_workspace(current, session)
        preferences = user_preferences(session, current.user_id, create=True)
        assert preferences is not None
        if "display_name" in body.model_fields_set:
            preferences.display_name = body.display_name.strip() if body.display_name and body.display_name.strip() else None
        if body.language is not None:
            preferences.language = body.language
        if body.theme is not None:
            preferences.theme = body.theme
        if body.editor_defaults is not None:
            settings = member_settings(session, workspace.id, current.user_id, create=True)
            assert settings is not None
            settings.editor_defaults_json = body.editor_defaults.model_dump(
                mode="json", exclude_none=True
            )
        session.commit()
        return personal_snapshot(current, session)

    @router.get("/api/provider-settings")
    def get_provider_settings(
        current: Any = Depends(principal_dependency), session: Session = Depends(session_dep)
    ):
        _, workspace = active_workspace(current, session)
        settings = member_settings(session, workspace.id, current.user_id, create=False)
        selection = None
        if settings and settings.provider_id and settings.model_id and settings.credential_policy:
            selection = {
                "provider_id": settings.provider_id,
                "model_id": settings.model_id,
                "credential_policy": settings.credential_policy,
            }
        credentials = session.scalars(
            select(Credential)
            .where(
                Credential.workspace_id == workspace.id,
                Credential.created_by_user_id == current.user_id,
            )
            .order_by(Credential.created_at.desc())
        ).all()
        return {
            "providers": _providers(),
            "credentials": [_metadata(item) for item in credentials],
            "selection": selection,
        }

    @router.put("/api/provider-settings")
    def update_provider_settings(
        body: ProviderSelectionUpdate,
        current: Any = Depends(principal_dependency),
        session: Session = Depends(session_dep),
    ):
        provider_id = body.provider_id.strip().lower()
        definition = _CATALOG.get(provider_id)
        if definition is None or body.model_id not in definition["models"]:
            raise HTTPException(status_code=422, detail="unsupported provider or model")
        _, workspace = active_workspace(current, session)
        if body.credential_policy == "user_only":
            credential = session.scalar(
                select(Credential.id).where(
                    Credential.workspace_id == workspace.id,
                    Credential.created_by_user_id == current.user_id,
                    Credential.provider == provider_id,
                    Credential.status == CredentialStatus.ACTIVE,
                )
            )
            if credential is None:
                raise HTTPException(status_code=422, detail="an active personal credential is required")
        settings = member_settings(session, workspace.id, current.user_id, create=True)
        assert settings is not None
        settings.provider_id = provider_id
        settings.model_id = body.model_id
        settings.credential_policy = body.credential_policy
        session.commit()
        return {
            "provider_id": settings.provider_id,
            "model_id": settings.model_id,
            "credential_policy": settings.credential_policy,
        }

    @router.post("/api/credentials", status_code=201)
    def create_credential(
        body: CredentialCreate,
        current: Any = Depends(principal_dependency),
        session: Session = Depends(session_dep),
    ):
        provider_id = body.provider_id.strip().lower()
        if provider_id not in _CATALOG:
            raise HTTPException(status_code=422, detail="unsupported provider")
        wrapper = _credential_wrapper()
        if wrapper is None:
            raise HTTPException(status_code=503, detail="personal credential storage is not configured")
        _, workspace = active_workspace(current, session)
        credential = SqlAlchemyCredentialStore(session, wrapper).create(
            workspace.id, current.user_id, provider_id, body.label.strip(), body.secret
        )
        return _metadata(credential)

    def own_credential(credential_id: UUID, current: Any, session: Session) -> Credential:
        _, workspace = active_workspace(current, session)
        credential = session.scalar(
            select(Credential).where(
                Credential.id == credential_id,
                Credential.workspace_id == workspace.id,
                Credential.created_by_user_id == current.user_id,
            )
        )
        if credential is None:
            raise HTTPException(status_code=404, detail="credential not found")
        return credential

    @router.patch("/api/credentials/{credential_id}")
    def replace_credential(
        credential_id: UUID,
        body: CredentialReplace,
        current: Any = Depends(principal_dependency),
        session: Session = Depends(session_dep),
    ):
        credential = own_credential(credential_id, current, session)
        wrapper = _credential_wrapper()
        if wrapper is None:
            raise HTTPException(status_code=503, detail="personal credential storage is not configured")
        credential = SqlAlchemyCredentialStore(session, wrapper).replace(
            credential.id, credential.workspace_id, body.secret
        )
        return _metadata(credential)

    @router.delete("/api/credentials/{credential_id}", status_code=204)
    def delete_credential(
        credential_id: UUID,
        current: Any = Depends(principal_dependency),
        session: Session = Depends(session_dep),
    ):
        credential = own_credential(credential_id, current, session)
        wrapper = _credential_wrapper()
        if wrapper is None:
            raise HTTPException(status_code=503, detail="personal credential storage is not configured")
        SqlAlchemyCredentialStore(session, wrapper).delete(
            credential.id, credential.workspace_id, current.user_id
        )
        return Response(status_code=204)

    return router
