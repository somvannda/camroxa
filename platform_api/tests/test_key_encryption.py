"""Phase 3: per-row key salt encryption (M9)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import pytest

from platform_api.services.key_encryption import KeyEncryption


def _legacy_encrypt(master_key: str, plaintext: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"api-key-pool-salt",
        iterations=100_000,
    )
    derived = kdf.derive(master_key.encode())
    fernet = Fernet(base64.urlsafe_b64encode(derived))
    return fernet.encrypt(plaintext.encode())


def test_encrypt_uses_per_row_salt_and_roundtrips() -> None:
    enc = KeyEncryption("test-master-key-phase3")
    a = enc.encrypt("sk-live-one")
    b = enc.encrypt("sk-live-one")
    assert a != b  # different salts
    assert a[0] == 2
    assert enc.decrypt(a) == "sk-live-one"
    assert enc.decrypt(b) == "sk-live-one"


def test_decrypt_legacy_static_salt_blob() -> None:
    master = "legacy-master-key"
    enc = KeyEncryption(master)
    legacy = _legacy_encrypt(master, "sk-old-key")
    assert enc.decrypt(legacy) == "sk-old-key"


def test_wrong_master_key_fails() -> None:
    enc = KeyEncryption("master-a")
    blob = enc.encrypt("secret")
    with pytest.raises(InvalidToken):
        KeyEncryption("master-b").decrypt(blob)
