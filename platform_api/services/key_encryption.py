"""Encryption utility for API key values stored at rest.

Uses Fernet symmetric encryption with a key derived via PBKDF2
from the server's master encryption key (PLATFORM_ENCRYPTION_MASTER_KEY).

Phase 3 (M9): new ciphertexts use a per-record random salt embedded in the
blob. Legacy static-salt blobs remain decryptable for migration safety.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_LEGACY_SALT = b"api-key-pool-salt"
_SALT_LEN = 16
_VERSION_PER_ROW = 2


class KeyEncryption:
    """Handles AES encryption/decryption of API key values.

    Uses Fernet (symmetric encryption) which provides AES-128-CBC
    with HMAC-SHA256 for authentication. Key material is derived via
    PBKDF2 from the server's master encryption key plus a salt.
    """

    def __init__(self, master_key: str) -> None:
        """Initialize encryption with the given master key.

        Args:
            master_key: The server's master encryption key string.
                        Must be non-empty.

        Raises:
            ValueError: If master_key is empty.
        """
        if not master_key:
            raise ValueError("Master encryption key must not be empty")
        self._master_key = master_key.encode()
        # Keep a legacy Fernet for decrypting pre-Phase-3 rows.
        self._legacy_fernet = self._fernet_for_salt(_LEGACY_SALT)

    def _fernet_for_salt(self, salt: bytes) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        derived = kdf.derive(self._master_key)
        return Fernet(base64.urlsafe_b64encode(derived))

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a plaintext API key value with a per-record salt.

        Blob format: ``bytes([2]) + salt(16) + fernet_ciphertext``.
        """
        salt = os.urandom(_SALT_LEN)
        fernet = self._fernet_for_salt(salt)
        ciphertext = fernet.encrypt(plaintext.encode())
        return bytes([_VERSION_PER_ROW]) + salt + ciphertext

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt an encrypted API key value (v2 per-row salt or legacy).

        Raises:
            cryptography.fernet.InvalidToken: If ciphertext is invalid
                or was encrypted with a different key.
        """
        if not ciphertext:
            raise InvalidToken("Empty ciphertext")

        if ciphertext[0] == _VERSION_PER_ROW and len(ciphertext) > 1 + _SALT_LEN:
            salt = ciphertext[1 : 1 + _SALT_LEN]
            token = ciphertext[1 + _SALT_LEN :]
            return self._fernet_for_salt(salt).decrypt(token).decode()

        # Legacy static-salt Fernet blob (no version prefix).
        return self._legacy_fernet.decrypt(ciphertext).decode()
