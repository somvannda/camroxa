"""Encryption for creator identity documents (KYC) at rest.

Documents live in the same object store as public media, so the bytes are
encrypted before they leave the process. A leaked object, a misconfigured
bucket policy, or a signed URL to the raw object all yield ciphertext.

The key is derived from the server master key using a salt that is unique to
this purpose, so a document ciphertext can never be replayed as an API key or
the other way around.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_PURPOSE_SALT = b"creator-kyc-documents-v1"
_SALT_LEN = 16
_VERSION = 1


class DocumentCipher:
    """Fernet over raw bytes, with a per-document random salt."""

    def __init__(self, master_key: str) -> None:
        if not master_key:
            raise ValueError("Master encryption key must not be empty")
        self._master_key = master_key.encode()

    def _fernet_for_salt(self, salt: bytes) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            # The purpose salt keeps this key domain separate from API keys and
            # media, even though both derive from the same master key.
            salt=_PURPOSE_SALT + salt,
            iterations=100_000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(self._master_key)))

    def encrypt(self, data: bytes) -> bytes:
        """Blob format: ``bytes([1]) + salt(16) + fernet_ciphertext``."""
        if not data:
            raise ValueError("Refusing to encrypt an empty document")
        salt = os.urandom(_SALT_LEN)
        token = self._fernet_for_salt(salt).encrypt(data)
        return bytes([_VERSION]) + salt + token

    def decrypt(self, blob: bytes) -> bytes:
        if not blob:
            raise InvalidToken("Empty ciphertext")
        if blob[0] != _VERSION or len(blob) <= 1 + _SALT_LEN:
            raise InvalidToken("Unsupported document ciphertext version")
        salt = blob[1 : 1 + _SALT_LEN]
        return self._fernet_for_salt(salt).decrypt(blob[1 + _SALT_LEN :])

    @staticmethod
    def is_encrypted(blob: bytes) -> bool:
        return bool(blob) and blob[0] == _VERSION and len(blob) > 1 + _SALT_LEN


def document_cipher_from_settings() -> DocumentCipher:
    """Build the cipher from PLATFORM_ENCRYPTION_MASTER_KEY."""
    from platform_api.config import get_settings

    settings = get_settings()
    master = getattr(settings, "encryption_master_key", None)
    if not master:
        raise ValueError("PLATFORM_ENCRYPTION_MASTER_KEY is not configured")
    return DocumentCipher(str(master))
