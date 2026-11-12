"""Get MIDI reuses the Studio clip-operation bridge with the MIDI internal path."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService


@pytest.mark.asyncio
async def test_request_studio_midi_uses_the_midi_operation() -> None:
    service = WebMusicService(AsyncMock(), AsyncMock(), redis=None)
    service._request_studio_clip_operation = AsyncMock(return_value={"id": "op"})
    project_id = uuid4()

    result = await service.request_studio_midi(
        uuid4(),
        uuid4(),
        variant="alt",
        project_id=project_id,
    )

    assert result == {"id": "op"}
    service._request_studio_clip_operation.assert_awaited_once()
    args, kwargs = service._request_studio_clip_operation.await_args
    assert kwargs["operation_type"] == "midi"
    assert kwargs["mode"] == "midi"
    assert kwargs["variant"] == "alt"
    assert kwargs["project_id"] == project_id
    assert kwargs["internal_path"] == "/internal/studio/midi"
    assert kwargs["internal_body"] == {}
