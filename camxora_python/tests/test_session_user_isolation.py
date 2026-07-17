"""Session isolation when switching accounts."""

from __future__ import annotations

from shared.models.auth import ProfileResponse, UserMeResponse
from shared.services.session_service import SessionService


def test_session_clear_wipes_workspace_cache() -> None:
    session = SessionService()
    session.workspace_cache.apply_warmup(
        me=UserMeResponse(
            id="u1",
            email="user@example.com",
            email_confirmed=True,
            display_name="User",
            credit_balance=10,
        ),
        profiles=[ProfileResponse(id="p1", user_id="u1", name="A")],
        settings_raw={"ffmpegPath": "/bin/ffmpeg"},
    )
    session.clear()
    assert session.get_tokens() is None
    assert not session.workspace_cache.has_core()
