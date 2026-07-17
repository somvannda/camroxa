from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from platform_api.services import invitation_code_service as invitation_module
from platform_api.services.invitation_code_service import InvitationCodeService
from platform_api.services.key_encryption import KeyEncryption


class FakeRecord(dict):
    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class FakePool:
    def __init__(self, rows: list[FakeRecord] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        self.executed.append((query, args))
        return self.rows

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query, args))
        return "INSERT 0 1"


@pytest.mark.asyncio
async def test_list_admin_codes_returns_decrypted_code_for_new_records() -> None:
    encryption = KeyEncryption("test-master-key")
    pool = FakePool(
        rows=[
            FakeRecord(
                id="invite-1",
                encrypted_code=encryption.encrypt("ABCDEF234567"),
                code_hint="4567",
                label="Creator cohort",
                max_uses=3,
                current_uses=1,
                is_active=True,
                expires_at=None,
                created_at=datetime(2026, 7, 13, tzinfo=timezone.utc),
            )
        ]
    )

    service = InvitationCodeService(pool=pool, encryption=encryption)
    items = await service.list_admin_codes()

    assert len(items) == 1
    assert items[0].code == "ABCDEF234567"
    assert items[0].code_hint == "4567"


@pytest.mark.asyncio
async def test_list_admin_codes_keeps_legacy_records_without_plaintext() -> None:
    pool = FakePool(
        rows=[
            FakeRecord(
                id="invite-legacy",
                encrypted_code=None,
                code_hint="9XYZ",
                label=None,
                max_uses=1,
                current_uses=0,
                is_active=True,
                expires_at=None,
                created_at=datetime(2026, 7, 13, tzinfo=timezone.utc),
            )
        ]
    )

    service = InvitationCodeService(pool=pool, encryption=None)
    items = await service.list_admin_codes()

    assert len(items) == 1
    assert items[0].code is None
    assert items[0].code_hint == "9XYZ"


@pytest.mark.asyncio
async def test_create_admin_code_persists_encrypted_code_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encryption = KeyEncryption("test-master-key")
    pool = FakePool()
    service = InvitationCodeService(pool=pool, encryption=encryption)

    monkeypatch.setattr(invitation_module, "_generate_code", lambda length=12: "ABCDEF234567")

    result = await service.create_admin_code(label="QA", max_uses=2, is_active=True)

    assert result.code == "ABCDEF234567"
    assert len(pool.executed) == 1
    insert_query, insert_args = pool.executed[0]
    assert "INSERT INTO invitation_codes" in insert_query
    assert encryption.decrypt(insert_args[2]) == "ABCDEF234567"
