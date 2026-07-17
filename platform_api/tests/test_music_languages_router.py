"""Music language router tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from platform_api.middleware.auth import AuthContext
from platform_api.routers import admin_music_languages, music_languages


class FakeMusicLanguageDb:
    def __init__(self) -> None:
        now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        self.rows = {
            "en": {
                "code": "en",
                "label": "English",
                "enabled": True,
                "sort_order": 0,
                "created_at": now,
                "updated_at": now,
            },
            "km": {
                "code": "km",
                "label": "Khmer",
                "enabled": False,
                "sort_order": 1,
                "created_at": now,
                "updated_at": now,
            },
        }

    async def fetch(self, query: str, *args):
        if "WHERE enabled = TRUE" in query:
            return [row for row in self.rows.values() if row["enabled"]]
        return list(self.rows.values())

    async def fetchrow(self, query: str, *args):
        if query.startswith("SELECT code, label, enabled, sort_order FROM music_languages"):
            return self.rows.get(str(args[0]))
        if query.startswith("SELECT enabled FROM music_languages"):
            row = self.rows.get(str(args[0]))
            return {"enabled": row["enabled"]} if row else None
        if query.startswith("INSERT INTO music_languages"):
            code, label, enabled, sort_order = args
            now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
            row = {
                "code": code,
                "label": label,
                "enabled": enabled,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }
            self.rows[str(code)] = row
            return row
        if "UPDATE music_languages" in query:
            code = str(args[0])
            row = self.rows.get(code)
            if row is None:
                return None
            if args[1] is not None:
                row["label"] = args[1]
            if args[2] is not None:
                row["enabled"] = args[2]
            if args[3] is not None:
                row["sort_order"] = args[3]
            row["updated_at"] = datetime(2026, 7, 10, 12, 30, tzinfo=timezone.utc)
            return row
        return None

    async def fetchval(self, query: str, *args):
        if "enabled = TRUE AND code <>" in query:
            exclude = str(args[0])
            return sum(1 for row in self.rows.values() if row["enabled"] and row["code"] != exclude)
        if "enabled = TRUE" in query:
            return sum(1 for row in self.rows.values() if row["enabled"])
        return 0

    async def execute(self, query: str, *args):
        if query.startswith("DELETE FROM music_languages"):
            code = str(args[0])
            if code in self.rows:
                del self.rows[code]
                return "DELETE 1"
            return "DELETE 0"
        return "OK"


@pytest.mark.asyncio
async def test_public_music_languages_returns_enabled_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_languages, "get_db_pool", lambda: FakeMusicLanguageDb())

    result = await music_languages.list_enabled_music_languages(
        AuthContext(user_id="00000000-0000-0000-0000-000000000001", email="boss@example.com", role="user")
    )

    assert len(result.items) == 1
    assert result.items[0].code == "en"
    assert result.items[0].label == "English"


@pytest.mark.asyncio
async def test_admin_can_enable_language(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = FakeMusicLanguageDb()
    monkeypatch.setattr(admin_music_languages, "get_db_pool", lambda: fake_db)
    monkeypatch.setattr(music_languages, "get_db_pool", lambda: fake_db)
    ctx = AuthContext(user_id="00000000-0000-0000-0000-000000000001", email="boss@example.com", role="admin")

    updated = await admin_music_languages.update_music_language(
        "km",
        admin_music_languages.UpdateMusicLanguageRequest(enabled=True),
        ctx,
    )
    assert updated.enabled is True

    public = await music_languages.list_enabled_music_languages(
        AuthContext(user_id="00000000-0000-0000-0000-000000000001", email="user@example.com", role="user")
    )
    assert {item.code for item in public.items} == {"en", "km"}
