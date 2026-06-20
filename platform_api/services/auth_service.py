"""Authentication service implementing JWT token management.

Handles login, token refresh, logout, and password hashing for the Platform API.
Implements the AuthServicePort protocol from ports/auth_port.py.

Requirements: 1.1, 1.3, 1.4, 1.5
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

import bcrypt
import jwt

from platform_api.config import Settings
from platform_api.exceptions import AuthenticationError
from platform_api.models.domain import User
from platform_api.ports.auth_port import TokenPair, TokenPayload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repository Protocol (dependency for looking up users)
# ---------------------------------------------------------------------------


class UserRepository(Protocol):
    """Minimal protocol for user lookup required by the auth service."""

    async def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email, or None if not found."""
        ...


class RefreshTokenRepository(Protocol):
    """Protocol for refresh token persistence (refresh_tokens table)."""

    async def store(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        """Store a new refresh token hash for the user."""
        ...

    async def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Return the refresh token record matching the hash, or None.

        Expected keys: user_id, token_hash, expires_at, revoked_at.
        """
        ...

    async def revoke(self, token_hash: str) -> None:
        """Mark a single refresh token as revoked (set revoked_at)."""
        ...

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Mark ALL refresh tokens for a user as revoked."""
        ...


# ---------------------------------------------------------------------------
# Password hashing constants (bcrypt, work factor 12)
# ---------------------------------------------------------------------------

_BCRYPT_ROUNDS = 12


# ---------------------------------------------------------------------------
# Auth Service
# ---------------------------------------------------------------------------


class AuthService:
    """Authentication service with JWT token management.

    Implements AuthServicePort: authenticate, refresh_token, validate_token,
    and revoke_tokens.

    Constructor Parameters:
        config: Application settings (jwt_secret, algorithm, token expiry).
        user_repo: Repository for user lookups by email.
        refresh_token_repo: Repository for refresh token CRUD.
    """

    def __init__(
        self,
        config: Settings,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
    ) -> None:
        self._config = config
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo

    # ------------------------------------------------------------------
    # Public API (AuthServicePort)
    # ------------------------------------------------------------------

    async def authenticate(self, email: str, password: str) -> TokenPair:
        """Authenticate a user with email/password and return a token pair.

        Validates credentials against the stored password hash. On success,
        issues an access token (30 min) and refresh token (7 days).

        Raises:
            AuthenticationError: If the user does not exist or the password
                is incorrect.
        """
        user = await self._user_repo.get_by_email(email)
        if user is None:
            raise AuthenticationError("Invalid credentials.")

        if not self.verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid credentials.")

        return await self._issue_token_pair(user)

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        """Issue a new token pair using a valid refresh token.

        Validates the refresh token's signature and checks the stored hash
        in the database. The old refresh token is revoked (rotated).

        Raises:
            AuthenticationError: If the token is invalid, expired, or revoked.
        """
        # Decode and validate JWT signature/expiry
        payload = self._decode_token(refresh_token, expected_type="refresh")

        # Look up the hashed token in the database
        token_hash = self._hash_token(refresh_token)
        stored = await self._refresh_token_repo.get_by_hash(token_hash)

        if stored is None:
            raise AuthenticationError("Refresh token not found.")

        if stored.get("revoked_at") is not None:
            raise AuthenticationError("Refresh token has been revoked.")

        expires_at = stored.get("expires_at")
        if expires_at is not None:
            # Ensure timezone-aware comparison
            now = datetime.now(timezone.utc)
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    raise AuthenticationError("Refresh token has expired.")

        # Revoke the old refresh token (rotation)
        await self._refresh_token_repo.revoke(token_hash)

        # Look up user to build new token pair
        user = await self._user_repo.get_by_email(payload.email)
        if user is None:
            raise AuthenticationError("User no longer exists.")

        return await self._issue_token_pair(user)

    async def validate_token(self, token: str) -> TokenPayload:
        """Validate an access token and return its decoded payload.

        Raises:
            AuthenticationError: If the token is invalid or expired.
        """
        return self._decode_token(token, expected_type="access")

    async def revoke_tokens(self, user_id: str) -> None:
        """Revoke all active refresh tokens for a user.

        Used on logout, account suspension, or password change.
        """
        await self._refresh_token_repo.revoke_all_for_user(UUID(user_id))
        logger.info("Revoked all refresh tokens for user %s", user_id)

    # ------------------------------------------------------------------
    # Password hashing utilities
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(plain_password: str) -> str:
        """Hash a plaintext password using bcrypt with work factor 12."""
        password_bytes = plain_password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a bcrypt hash."""
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _issue_token_pair(self, user: User) -> TokenPair:
        """Create and persist a new access + refresh token pair for a user."""
        now = datetime.now(timezone.utc)

        # Access token
        access_exp = now + timedelta(minutes=self._config.access_token_expire_minutes)
        access_payload: dict[str, Any] = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "exp": access_exp,
            "iat": now,
            "type": "access",
        }
        access_token = jwt.encode(
            access_payload,
            self._config.jwt_secret,
            algorithm=self._config.jwt_algorithm,
        )

        # Refresh token
        refresh_exp = now + timedelta(days=self._config.refresh_token_expire_days)
        refresh_payload: dict[str, Any] = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "exp": refresh_exp,
            "iat": now,
            "type": "refresh",
            "jti": secrets.token_hex(16),  # unique identifier for rotation tracking
        }
        refresh_token = jwt.encode(
            refresh_payload,
            self._config.jwt_secret,
            algorithm=self._config.jwt_algorithm,
        )

        # Store refresh token hash in DB
        token_hash = self._hash_token(refresh_token)
        await self._refresh_token_repo.store(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_exp,
        )

        expires_in = int(self._config.access_token_expire_minutes * 60)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    def _decode_token(self, token: str, expected_type: str) -> TokenPayload:
        """Decode and validate a JWT token.

        Args:
            token: The raw JWT string.
            expected_type: Either "access" or "refresh".

        Returns:
            TokenPayload with decoded claims.

        Raises:
            AuthenticationError: On any decode failure or type mismatch.
        """
        try:
            payload = jwt.decode(
                token,
                self._config.jwt_secret,
                algorithms=[self._config.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired.")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token.")

        # Verify token type
        token_type = payload.get("type")
        if token_type != expected_type:
            raise AuthenticationError(
                f"Invalid token type: expected {expected_type}, got {token_type}."
            )

        return TokenPayload(
            user_id=payload["user_id"],
            email=payload["email"],
            role=payload["role"],
            exp=payload["exp"],
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        """Compute a SHA-256 hash of a token for secure storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
