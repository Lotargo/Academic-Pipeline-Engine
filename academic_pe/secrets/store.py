from __future__ import annotations

import os
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from academic_pe.persistence.models import AuditEvent, Credential, CredentialStatus
from academic_pe.secrets.crypto import KeyWrapper, decrypt_payload, encrypt_payload


class WorkerPurpose(str, Enum):
    GENERATION = "generation"
    OCR = "ocr"
    API = "api"
    ADMIN = "admin"


class CredentialAccessDenied(PermissionError):
    pass


class CredentialStore(Protocol):
    def create(self, workspace_id: UUID, user_id: UUID, provider: str,
               label: str, secret: str) -> Credential: ...
    def replace(self, credential_id: UUID, workspace_id: UUID, secret: str) -> Credential: ...
    def delete(self, credential_id: UUID, workspace_id: UUID, user_id: UUID) -> None: ...
    def use(self, credential_id: UUID, workspace_id: UUID, purpose: WorkerPurpose) -> str: ...
    def rewrap(self, credential_id: UUID, workspace_id: UUID, new_wrapper: KeyWrapper) -> None: ...


class SqlAlchemyCredentialStore:
    def __init__(self, session: Session, wrapper: KeyWrapper):
        self.session = session
        self.wrapper = wrapper

    @staticmethod
    def _aad(credential_id: UUID, workspace_id: UUID, provider: str) -> bytes:
        return f"ape:credential:v1:{credential_id}:{workspace_id}:{provider}".encode()

    def _get(self, credential_id: UUID, workspace_id: UUID) -> Credential:
        credential = self.session.get(Credential, credential_id)
        if credential is None or credential.workspace_id != workspace_id:
            raise KeyError("credential not found")
        return credential

    def create(self, workspace_id: UUID, user_id: UUID, provider: str,
               label: str, secret: str) -> Credential:
        credential_id = uuid4()
        aad = self._aad(credential_id, workspace_id, provider)
        ciphertext, nonce, wrapped = encrypt_payload(secret.encode(), aad, self.wrapper)
        credential = Credential(id=credential_id, workspace_id=workspace_id,
            created_by_user_id=user_id, provider=provider, label=label,
            encrypted_payload=ciphertext, wrapped_data_key=wrapped, payload_nonce=nonce,
            encryption_key_id=self.wrapper.key_id, encryption_version=1)
        self.session.add(credential)
        self.session.add(AuditEvent(event_type="credential.created", actor_user_id=user_id,
            metadata_json={"credential_id": str(credential.id), "workspace_id": str(workspace_id), "provider": provider}))
        self.session.commit()
        return credential

    def replace(self, credential_id: UUID, workspace_id: UUID, secret: str) -> Credential:
        credential = self._get(credential_id, workspace_id)
        if credential.status == CredentialStatus.DELETED:
            raise KeyError("credential not found")
        aad = self._aad(credential.id, credential.workspace_id, credential.provider)
        ciphertext, nonce, wrapped = encrypt_payload(secret.encode(), aad, self.wrapper)
        credential.encrypted_payload, credential.payload_nonce = ciphertext, nonce
        credential.wrapped_data_key, credential.encryption_key_id = wrapped, self.wrapper.key_id
        credential.encryption_version += 1
        self.session.add(AuditEvent(event_type="credential.replaced", actor_user_id=credential.created_by_user_id,
            metadata_json={"credential_id": str(credential.id), "workspace_id": str(workspace_id)}))
        self.session.commit()
        return credential

    def delete(self, credential_id: UUID, workspace_id: UUID, user_id: UUID) -> None:
        credential = self._get(credential_id, workspace_id)
        credential.status = CredentialStatus.DELETED
        credential.encrypted_payload = os.urandom(max(32, len(credential.encrypted_payload)))
        credential.wrapped_data_key = os.urandom(max(32, len(credential.wrapped_data_key)))
        credential.payload_nonce = os.urandom(12)
        self.session.add(AuditEvent(event_type="credential.deleted", actor_user_id=user_id,
            metadata_json={"credential_id": str(credential.id), "workspace_id": str(workspace_id)}))
        self.session.commit()

    def use(self, credential_id: UUID, workspace_id: UUID, purpose: WorkerPurpose) -> str:
        if purpose not in {WorkerPurpose.GENERATION, WorkerPurpose.OCR}:
            raise CredentialAccessDenied("credential decrypt is restricted to provider workers")
        credential = self._get(credential_id, workspace_id)
        if credential.status != CredentialStatus.ACTIVE:
            raise KeyError("credential not found")
        if credential.encryption_key_id != self.wrapper.key_id:
            raise ValueError("credential requires matching KMS key adapter")
        aad = self._aad(credential.id, credential.workspace_id, credential.provider)
        plaintext = decrypt_payload(credential.encrypted_payload, credential.payload_nonce,
                                    credential.wrapped_data_key, aad, self.wrapper).decode()
        self.session.add(AuditEvent(event_type="credential.used",
            metadata_json={"credential_id": str(credential.id), "workspace_id": str(workspace_id), "purpose": purpose.value}))
        self.session.commit()
        return plaintext

    def rewrap(self, credential_id: UUID, workspace_id: UUID, new_wrapper: KeyWrapper) -> None:
        credential = self._get(credential_id, workspace_id)
        aad = self._aad(credential.id, credential.workspace_id, credential.provider)
        data_key = self.wrapper.unwrap(credential.wrapped_data_key, aad)
        credential.wrapped_data_key = new_wrapper.wrap(data_key, aad)
        credential.encryption_key_id = new_wrapper.key_id
        self.session.add(AuditEvent(event_type="credential.rewrapped",
            metadata_json={"credential_id": str(credential.id), "workspace_id": str(workspace_id), "key_id": new_wrapper.key_id}))
        self.session.commit()
        self.wrapper = new_wrapper
