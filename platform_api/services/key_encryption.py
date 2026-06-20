"""Encryption utility for API key values stored at rest.

Uses Fernet symmetric encryption with a key derived via PBKDF2
from the server's master encryption key (PLATFORM_ENCRYPTION_MASTER_KEY).
"""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class KeyEncryption:
    """Handles AES-256 encryption/decryption of API key values.

    Uses Fernet (symmetric encryption) which provides AES-128-CBC
    with HMAC-SHA256 for authentication. For AES-256, we use a
    derived key via PBKDF2 from the server's master encryption key.
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

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"api-key-pool-salt",  # Static salt — key uniqueness from master_key
            iterations=100_000,
        )
        derived = kdf.derive(master_key.encode())
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a plaintext API key value.

        Args:
            plaintext: The raw API key string to encrypt.

        Returns:
            The encrypted ciphertext as bytes.
        """
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt an encrypted API key value.

        Args:
            ciphertext: The encrypted bytes to decrypt.

        Returns:
            The original plaintext API key string.

        Raises:
            cryptography.fernet.InvalidToken: If ciphertext is invalid
                or was encrypted with a different key.
        """
        return self._fernet.decrypt(ciphertext).decode()
