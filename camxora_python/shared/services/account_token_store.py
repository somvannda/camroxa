"""Persisted auth tokens for multiple accounts on one machine."""

from __future__ import annotations

import json
from dataclasses import dataclass

from shared.services.secure_storage import SecureStorage

ACCOUNTS_INDEX_KEY = "camxora.auth.accounts"
ACTIVE_ACCOUNT_ID_KEY = "camxora.auth.activeAccountId"


def _token_key(user_id: str) -> str:
    return f"camxora.auth.tokens.{user_id}"


@dataclass(frozen=True, slots=True)
class SavedAccount:
    user_id: str
    email: str
    display_name: str


def _parse_accounts(raw: str | None) -> list[SavedAccount]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    accounts: list[SavedAccount] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("userId") or item.get("user_id") or "").strip()
        if not user_id:
            continue
        accounts.append(
            SavedAccount(
                user_id=user_id,
                email=str(item.get("email") or "").strip(),
                display_name=str(item.get("displayName") or item.get("display_name") or "").strip(),
            )
        )
    return accounts


def list_saved_accounts(storage: SecureStorage) -> list[SavedAccount]:
    return _parse_accounts(storage.get(ACCOUNTS_INDEX_KEY))


def remember_account(
    storage: SecureStorage,
    *,
    user_id: str,
    email: str,
    display_name: str,
    tokens_json: str,
) -> None:
    normalized_id = str(user_id).strip()
    if not normalized_id:
        return
    storage.set(_token_key(normalized_id), tokens_json)
    storage.set(ACTIVE_ACCOUNT_ID_KEY, normalized_id)
    accounts = [item for item in list_saved_accounts(storage) if item.user_id != normalized_id]
    accounts.insert(
        0,
        SavedAccount(
            user_id=normalized_id,
            email=str(email or "").strip(),
            display_name=str(display_name or "").strip() or str(email or "").strip(),
        ),
    )
    payload = [
        {
            "userId": item.user_id,
            "email": item.email,
            "displayName": item.display_name,
        }
        for item in accounts[:8]
    ]
    storage.set(ACCOUNTS_INDEX_KEY, json.dumps(payload, separators=(",", ":")))


def load_saved_tokens(storage: SecureStorage, user_id: str) -> str | None:
    return storage.get(_token_key(str(user_id).strip()))


def remove_saved_account(storage: SecureStorage, user_id: str) -> None:
    normalized_id = str(user_id).strip()
    storage.remove(_token_key(normalized_id))
    accounts = [item for item in list_saved_accounts(storage) if item.user_id != normalized_id]
    payload = [
        {
            "userId": item.user_id,
            "email": item.email,
            "displayName": item.display_name,
        }
        for item in accounts
    ]
    if payload:
        storage.set(ACCOUNTS_INDEX_KEY, json.dumps(payload, separators=(",", ":")))
    else:
        storage.remove(ACCOUNTS_INDEX_KEY)
    if storage.get(ACTIVE_ACCOUNT_ID_KEY) == normalized_id:
        storage.remove(ACTIVE_ACCOUNT_ID_KEY)
