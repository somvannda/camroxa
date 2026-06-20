"""Authentication service protocol interface.

Defines the contract for authentication operations including login,
token refresh, validation, and revocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Access + refresh token pair returned on authentication."""

    access_token: str
    refresh_token: str
    expires_in: int  # access token lifetime in seconds


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded JWT payload with essential claims."""

    user_id: str
    email: str
    role: str
    exp: int  # expiration timestamp (Unix epoch)


class AuthServicePort(Protocol):
    """Port for authentication and token management.

    Implementations handle credential verification, JWT issuance/validation,
    and token revocation.
    """

    async def authenticate(self, email: str, password: str) -> TokenPair:
        """Authenticate a user with email/password and return a token pair.

        Raises AuthenticationError on invalid credentials.
        Raises AccountLockedError if the account is locked due to repeated failures.
        """
        ...

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        """Issue a new token pair using a valid refresh token.

        Rotates the refresh token (old one becomes invalid).
        Raises AuthenticationError if the refresh token is expired or revoked.
        """
        ...

    async def validate_token(self, token: str) -> TokenPayload:
        """Validate an access token and return its decoded payload.

        Raises AuthenticationError if the token is invalid or expired.
        """
        ...

    async def revoke_tokens(self, user_id: str) -> None:
        """Revoke all active tokens for a user.

        Used on logout, account suspension, or password change.
        """
        ...
