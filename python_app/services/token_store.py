"""DPAPI-encrypted token persistence for Platform API JWT tokens.

Stores access and refresh tokens as a single encrypted JSON blob at
``%LOCALAPPDATA%/MusicGenerator/auth_tokens.dat``.  Uses atomic file writes
(write to ``.tmp`` then rename) to prevent corruption on crash or power loss.

Implements the ``TokenStorePort`` protocol defined in the design document.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from python_app.services.dpapi import dpapi_decrypt_from_base64, dpapi_encrypt_to_base64

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "MusicGenerator"
_TOKEN_FILENAME = "auth_tokens.dat"


@dataclass(frozen=True)
class StoredTokens:
    """Immutable token pair loaded from disk."""

    access_token: str
    refresh_token: str


class TokenStorePort(Protocol):
    """Protocol for token persistence."""

    def load(self) -> StoredTokens | None:
        """Load tokens from disk. Returns None if no valid tokens exist."""
        ...

    def save(self, access_token: str, refresh_token: str) -> None:
        """Encrypt and persist tokens to disk."""
        ...

    def clear(self) -> None:
        """Remove stored tokens from disk."""
        ...

    def has_tokens(self) -> bool:
        """Check if token file exists (without decrypting)."""
        ...


class TokenStore:
    """DPAPI-encrypted token storage on the local filesystem.

    Parameters
    ----------
    store_dir:
        Directory where the token file is written.
        Defaults to ``%LOCALAPPDATA%/MusicGenerator``.
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        self._store_dir = store_dir or _DEFAULT_STORE_DIR
        self._token_path = self._store_dir / _TOKEN_FILENAME
        self._tmp_path = self._store_dir / f"{_TOKEN_FILENAME}.tmp"

    @property
    def token_path(self) -> Path:
        """Full path to the token file (useful for testing)."""
        return self._token_path

    def load(self) -> StoredTokens | None:
        """Load and decrypt tokens from disk.

        Returns ``None`` if the file is missing, empty, or corrupt
        (no crash — errors are logged at warning level).
        """
        if not self._token_path.is_file():
            return None

        try:
            encrypted_b64 = self._token_path.read_text(encoding="utf-8").strip()
            if not encrypted_b64:
                return None

            json_str = dpapi_decrypt_from_base64(encrypted_b64)
            data = json.loads(json_str)

            access_token = data.get("access_token", "")
            refresh_token = data.get("refresh_token", "")

            if not access_token or not refresh_token:
                logger.warning("Token file missing required fields, treating as empty")
                return None

            return StoredTokens(access_token=access_token, refresh_token=refresh_token)

        except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Failed to load tokens from %s: %s", self._token_path, exc)
            return None

    def save(self, access_token: str, refresh_token: str) -> None:
        """Encrypt and persist tokens to disk using atomic write.

        Writes to a ``.tmp`` file first, then renames to the final path
        to prevent corruption if the process is interrupted.
        """
        payload = json.dumps(
            {"access_token": access_token, "refresh_token": refresh_token},
            separators=(",", ":"),
        )

        encrypted_b64 = dpapi_encrypt_to_base64(payload)

        # Ensure the directory exists
        self._store_dir.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to tmp file, then rename
        self._tmp_path.write_text(encrypted_b64, encoding="utf-8")
        self._tmp_path.replace(self._token_path)

    def clear(self) -> None:
        """Remove the token file from disk (if it exists)."""
        try:
            self._token_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove token file: %s", exc)

        # Also clean up any leftover tmp file
        try:
            self._tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    def has_tokens(self) -> bool:
        """Check if the token file exists on disk (without decrypting)."""
        return self._token_path.is_file()
