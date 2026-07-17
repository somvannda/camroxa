"""Multi-account token index on one machine."""

from __future__ import annotations

import json
from pathlib import Path

from shared.services.account_token_store import (
    ACCOUNTS_INDEX_KEY,
    ACTIVE_ACCOUNT_ID_KEY,
    list_saved_accounts,
    load_saved_tokens,
    remember_account,
    remove_saved_account,
)
from shared.services.secure_storage import SecureStorage


class _MemoryStorage(SecureStorage):
    def __init__(self) -> None:
        super().__init__(store_path=Path("memory-only") / "account-store.json")
        self._data = {}

    def _load(self) -> None:
        return

    def _save(self) -> None:
        return


def test_remember_and_switch_saved_accounts() -> None:
    storage = _MemoryStorage()
    remember_account(
        storage,
        user_id="user-a",
        email="a@example.com",
        display_name="Account A",
        tokens_json='{"accessToken":"a","refreshToken":"ra","tokenType":"bearer","expiresAt":1}',
    )
    remember_account(
        storage,
        user_id="user-b",
        email="b@example.com",
        display_name="Account B",
        tokens_json='{"accessToken":"b","refreshToken":"rb","tokenType":"bearer","expiresAt":2}',
    )

    accounts = list_saved_accounts(storage)
    assert [item.user_id for item in accounts] == ["user-b", "user-a"]
    assert storage.get(ACTIVE_ACCOUNT_ID_KEY) == "user-b"
    assert load_saved_tokens(storage, "user-a") is not None

    remove_saved_account(storage, "user-b")
    accounts = list_saved_accounts(storage)
    assert [item.user_id for item in accounts] == ["user-a"]
    assert storage.get(ACTIVE_ACCOUNT_ID_KEY) is None

    raw = storage.get(ACCOUNTS_INDEX_KEY)
    assert raw is not None
    parsed = json.loads(raw)
    assert len(parsed) == 1
