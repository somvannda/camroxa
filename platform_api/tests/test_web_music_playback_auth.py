"""Tests for login-required web music playback."""

from __future__ import annotations

import pytest

from platform_api.exceptions import ForbiddenError
from platform_api.services.web_music_service import WebMusicService


@pytest.mark.asyncio
async def test_stream_by_play_token_requires_login() -> None:
    service = WebMusicService.__new__(WebMusicService)
    service._redis = object()
    with pytest.raises(ForbiddenError, match="Sign in to play music"):
        await service.stream_by_play_token("token", session_user_id=None)
