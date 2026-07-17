from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.exceptions import ValidationError
from platform_api.services.key_encryption import KeyEncryption


logger = logging.getLogger(__name__)


class AsyncPGConnection(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> str: ...


class AsyncPGPool(Protocol):
    async def acquire(self) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> str: ...


SignupMode = str


@dataclass(frozen=True, slots=True)
class InvitationCodeAdminItem:
    id: str
    code: str | None
    code_hint: str
    label: str | None
    max_uses: int
    current_uses: int
    remaining_uses: int | None
    is_active: bool
    expires_at: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class InvitationCodeCreateResult:
    id: str
    code: str
    code_hint: str
    label: str | None
    max_uses: int
    expires_at: str | None
    is_active: bool
    created_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _normalize_signup_mode(value: Any) -> SignupMode:
    candidate = str(value or "").strip().lower()
    if candidate == "open":
        return "open"
    return "invite_only"


def _hash_code(code: str) -> str:
    normalized = code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _generate_code(length: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class InvitationCodeService:
    def __init__(
        self,
        pool: AsyncPGPool,
        encryption: KeyEncryption | None = None,
    ) -> None:
        self._pool = pool
        self._encryption = encryption

    def _decrypt_code(self, encrypted_code: Any) -> str | None:
        raw = bytes(encrypted_code or b"")
        if not raw or self._encryption is None:
            return None
        try:
            return self._encryption.decrypt(raw)
        except Exception:
            logger.warning("Unable to decrypt stored invitation code.", exc_info=True)
            return None

    async def get_signup_mode(self) -> SignupMode:
        raw = await self._pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'signup_mode'"
        )
        return _normalize_signup_mode(raw)

    async def set_signup_mode(self, mode: SignupMode) -> SignupMode:
        normalized = _normalize_signup_mode(mode)
        await self._pool.execute(
            """
            INSERT INTO system_settings (key, value_type, value, updated_at)
            VALUES ('signup_mode', 'string', $1, NOW())
            ON CONFLICT (key) DO UPDATE SET value = $1, value_type = 'string', updated_at = NOW()
            """,
            normalized,
        )
        return normalized

    async def validate_invitation_code(self, code: str) -> dict[str, Any]:
        code_hash = _hash_code(code)
        row = await self._pool.fetchrow(
            """
            SELECT id, code_hint, label, max_uses, current_uses, is_active, expires_at, created_at
            FROM invitation_codes
            WHERE code_hash = $1
            """,
            code_hash,
        )
        if row is None:
            raise ValidationError(message="Invalid invitation code.")

        if not bool(row["is_active"]):
            raise ValidationError(message="Invitation code is disabled.")

        expires_at = row.get("expires_at")
        if expires_at is not None:
            now = _utc_now()
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now:
                    raise ValidationError(message="Invitation code has expired.")

        max_uses = int(row.get("max_uses") or 1)
        current_uses = int(row.get("current_uses") or 0)
        if current_uses >= max_uses:
            raise ValidationError(message="Invitation code has reached its usage limit.")

        return {
            "id": str(row["id"]),
            "code_hint": str(row.get("code_hint") or ""),
            "label": row.get("label"),
            "max_uses": max_uses,
            "current_uses": current_uses,
            "expires_at": _to_iso(expires_at) if isinstance(expires_at, datetime) else None,
            "created_at": _to_iso(row.get("created_at")) or "",
        }

    async def consume_invitation_code(
        self,
        *,
        conn: AsyncPGConnection,
        code: str,
        user_id: UUID,
    ) -> str:
        code_hash = _hash_code(code)
        row = await conn.fetchrow(
            """
            SELECT id, max_uses, current_uses, is_active, expires_at
            FROM invitation_codes
            WHERE code_hash = $1
            FOR UPDATE
            """,
            code_hash,
        )
        if row is None:
            raise ValidationError(message="Invalid invitation code.")
        if not bool(row["is_active"]):
            raise ValidationError(message="Invitation code is disabled.")

        expires_at = row.get("expires_at")
        if expires_at is not None and isinstance(expires_at, datetime):
            now = _utc_now()
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                raise ValidationError(message="Invitation code has expired.")

        max_uses = int(row.get("max_uses") or 1)
        current_uses = int(row.get("current_uses") or 0)
        if current_uses >= max_uses:
            raise ValidationError(message="Invitation code has reached its usage limit.")

        code_id = str(row["id"])
        await conn.execute(
            "UPDATE invitation_codes SET current_uses = current_uses + 1 WHERE id = $1",
            code_id,
        )
        await conn.execute(
            """
            INSERT INTO invitation_code_redemptions (id, invitation_code_id, user_id, redeemed_at)
            VALUES ($1, $2, $3, NOW())
            """,
            str(uuid4()),
            code_id,
            user_id,
        )
        return code_id

    async def list_admin_codes(self) -> list[InvitationCodeAdminItem]:
        rows = await self._pool.fetch(
            """
            SELECT id, encrypted_code, code_hint, label, max_uses, current_uses, is_active, expires_at, created_at
            FROM invitation_codes
            ORDER BY created_at DESC
            """
        )
        items: list[InvitationCodeAdminItem] = []
        for row in rows:
            max_uses = int(row.get("max_uses") or 1)
            current_uses = int(row.get("current_uses") or 0)
            remaining = max(max_uses - current_uses, 0)
            items.append(
                InvitationCodeAdminItem(
                    id=str(row["id"]),
                    code=self._decrypt_code(row.get("encrypted_code")),
                    code_hint=str(row.get("code_hint") or ""),
                    label=row.get("label"),
                    max_uses=max_uses,
                    current_uses=current_uses,
                    remaining_uses=remaining,
                    is_active=bool(row.get("is_active")),
                    expires_at=_to_iso(row.get("expires_at")) if isinstance(row.get("expires_at"), datetime) else None,
                    created_at=_to_iso(row.get("created_at")) or "",
                )
            )
        return items

    async def create_admin_code(
        self,
        *,
        label: str | None = None,
        max_uses: int = 1,
        expires_at: datetime | None = None,
        is_active: bool = True,
    ) -> InvitationCodeCreateResult:
        normalized_label = label.strip() if isinstance(label, str) and label.strip() else None
        max_uses = max(1, min(int(max_uses or 1), 100000))

        for _ in range(6):
            code = _generate_code()
            code_hash = _hash_code(code)
            code_hint = code[-4:]
            encrypted_code = (
                self._encryption.encrypt(code) if self._encryption is not None else None
            )
            code_id = str(uuid4())
            created_at = _utc_now()
            try:
                await self._pool.execute(
                    """
                    INSERT INTO invitation_codes
                      (id, code_hash, encrypted_code, code_hint, label, max_uses, current_uses, is_active, expires_at, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, 0, $7, $8, $9)
                    """,
                    code_id,
                    code_hash,
                    encrypted_code,
                    code_hint,
                    normalized_label,
                    max_uses,
                    is_active,
                    expires_at,
                    created_at,
                )
                return InvitationCodeCreateResult(
                    id=code_id,
                    code=code,
                    code_hint=code_hint,
                    label=normalized_label,
                    max_uses=max_uses,
                    expires_at=_to_iso(expires_at),
                    is_active=is_active,
                    created_at=_to_iso(created_at) or "",
                )
            except Exception:
                continue
        raise ValidationError(message="Unable to generate a unique invitation code. Please retry.")

    async def update_admin_code(
        self,
        *,
        code_id: str,
        label: str | None = None,
        max_uses: int | None = None,
        expires_at: datetime | None = None,
        is_active: bool | None = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []
        idx = 1

        if label is not None:
            idx += 1
            updates.append(f"label = ${idx}")
            params.append(label.strip() if label.strip() else None)

        if max_uses is not None:
            idx += 1
            updates.append(f"max_uses = ${idx}")
            params.append(max(1, min(int(max_uses or 1), 100000)))

        if is_active is not None:
            idx += 1
            updates.append(f"is_active = ${idx}")
            params.append(bool(is_active))

        if expires_at is not None:
            idx += 1
            updates.append(f"expires_at = ${idx}")
            params.append(expires_at)

        if not updates:
            return

        await self._pool.execute(
            f"UPDATE invitation_codes SET {', '.join(updates)} WHERE id = $1",
            code_id,
            *params,
        )

    async def delete_admin_code(self, code_id: str) -> None:
        await self._pool.execute("DELETE FROM invitation_codes WHERE id = $1", code_id)
