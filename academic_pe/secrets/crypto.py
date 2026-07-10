from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class KeyWrapper(Protocol):
    @property
    def key_id(self) -> str: ...
    def wrap(self, data_key: bytes, context: bytes) -> bytes: ...
    def unwrap(self, wrapped_key: bytes, context: bytes) -> bytes: ...


@dataclass(frozen=True)
class LocalAesKeyWrapper:
    """Development/test adapter. Production adapters delegate wrap/unwrap to KMS."""
    master_key: bytes
    key_id: str

    def __post_init__(self) -> None:
        if len(self.master_key) != 32:
            raise ValueError("AES-256 master key must be exactly 32 bytes")

    def wrap(self, data_key: bytes, context: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + AESGCM(self.master_key).encrypt(nonce, data_key, context)

    def unwrap(self, wrapped_key: bytes, context: bytes) -> bytes:
        return AESGCM(self.master_key).decrypt(wrapped_key[:12], wrapped_key[12:], context)


def encrypt_payload(plaintext: bytes, aad: bytes, wrapper: KeyWrapper) -> tuple[bytes, bytes, bytes]:
    data_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, aad)
    return ciphertext, nonce, wrapper.wrap(data_key, aad)


def decrypt_payload(ciphertext: bytes, nonce: bytes, wrapped_key: bytes,
                    aad: bytes, wrapper: KeyWrapper) -> bytes:
    data_key = wrapper.unwrap(wrapped_key, aad)
    return AESGCM(data_key).decrypt(nonce, ciphertext, aad)
