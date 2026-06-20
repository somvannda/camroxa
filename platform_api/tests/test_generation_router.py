"""Tests for the generation and callbacks routers.

Tests cover:
- POST /generation/draft (song draft generation)
- POST /generation/suno (Suno submission)
- GET /generation/suno/{taskId} (task status)
- POST /generation/image (image generation)
- POST /callbacks/suno (Suno callback processing)
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    NotFoundError,
)
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.enums import TaskStatus
from platform_api.ports.generation_port import SongDraft
from platform_api.routers.callbacks import _get_notification_port, _get_suno_task_repo
from platform_api.routers.generation import _get_generation_service, _get_task_lookup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")


@pytest.fixture
def mock_generation_service() -> AsyncMock:
    """Create a mock GenerationService."""
    service = AsyncMock()
    service.submit_draft = AsyncMock(
        return_value=SongDraft(title="Test Song", album="Test Album", lyrics="[Verse]\nLyrics here")
    )
    service.submit_suno = AsyncMock(return_value=str(uuid4()))
    service.submit_image = AsyncMock(return_value=b"\x89PNG\r\n\x1a\nfakedata")
    return service


@pytest.fixture
def mock_task_lookup() -> AsyncMock:
    """Create a mock TaskLookupPort."""
    lookup = AsyncMock()
    lookup.get_task_by_id = AsyncMock(return_value=None)
    return lookup


@pytest.fixture
def mock_suno_task_repo() -> AsyncMock:
    """Create a mock SunoTaskRepository for callbacks."""
    repo = AsyncMock()
    repo.find_by_external_id = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_notification() -> AsyncMock:
    """Create a mock NotificationPort."""
    notif = AsyncMock()
    notif.push = AsyncMock(return_value=None)
    notif.queue = AsyncMock(return_value=None)
    return notif


@pytest.fixture
def app(
    mock_generation_service: AsyncMock,
    mock_task_lookup: AsyncMock,
    mock_suno_task_repo: AsyncMock,
    mock_notification: AsyncMock,
):
    """Create a test app with all dependencies overridden."""
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    application.dependency_overrides[_get_generation_service] = lambda: mock_generation_service
    application.dependency_overrides[_get_task_lookup] = lambda: mock_task_lookup
    application.dependency_overrides[_get_suno_task_repo] = lambda: mock_suno_task_repo
    application.dependency_overrides[_get_notification_port] = lambda: mock_notification
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /generation/draft
# ---------------------------------------------------------------------------


class TestGenerateDraft:
    """Tests for POST /api/v1/generation/draft."""

    async def test_success(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """Valid request returns 200 with draft."""
        response = await client.post(
            "/api/v1/generation/draft",
            json={
                "language": "en",
                "creativity_level": 75,
                "description": "Upbeat pop song about summer",
                "structure": "[Verse]\n[Chorus]\n[Verse]\n[Chorus]",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Song"
        assert data["album"] == "Test Album"
        assert "lyrics" in data
        mock_generation_service.submit_draft.assert_awaited_once()

    async def test_with_avoid_lists(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """Request with avoid lists is accepted."""
        response = await client.post(
            "/api/v1/generation/draft",
            json={
                "description": "Rock ballad",
                "structure": "[Verse]\n[Chorus]",
                "avoid_titles": ["Existing Song"],
                "avoid_albums": ["Existing Album"],
                "forced_title": "My Forced Title",
            },
        )
        assert response.status_code == 200

    async def test_missing_description(self, client: AsyncClient) -> None:
        """Missing required 'description' returns 422."""
        response = await client.post(
            "/api/v1/generation/draft",
            json={"structure": "[Verse]"},
        )
        assert response.status_code == 422

    async def test_insufficient_credits(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """InsufficientCreditsError from service returns 402."""
        mock_generation_service.submit_draft.side_effect = InsufficientCreditsError(
            details={"required": 10}
        )
        response = await client.post(
            "/api/v1/generation/draft",
            json={"description": "Test", "structure": ""},
        )
        assert response.status_code == 402


# ---------------------------------------------------------------------------
# POST /generation/suno
# ---------------------------------------------------------------------------


class TestSubmitSuno:
    """Tests for POST /api/v1/generation/suno."""

    async def test_success(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """Valid request returns 202 with task_id."""
        task_id = str(uuid4())
        mock_generation_service.submit_suno.return_value = task_id

        response = await client.post(
            "/api/v1/generation/suno",
            json={
                "model": "V5",
                "title": "Test Song",
                "lyrics": "La la la",
                "style": "pop",
                "instrumental": False,
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == task_id
        mock_generation_service.submit_suno.assert_awaited_once()

    async def test_invalid_model(self, client: AsyncClient) -> None:
        """Invalid model returns 422."""
        response = await client.post(
            "/api/v1/generation/suno",
            json={
                "model": "V3",
                "title": "Song",
                "lyrics": "Lyrics",
                "style": "rock",
            },
        )
        assert response.status_code == 422

    async def test_external_service_error(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """ExternalServiceError returns 502."""
        mock_generation_service.submit_suno.side_effect = ExternalServiceError(
            "Suno API timeout", is_retryable=True
        )
        response = await client.post(
            "/api/v1/generation/suno",
            json={
                "model": "V5_5",
                "title": "Song",
                "lyrics": "Lyrics",
                "style": "pop",
            },
        )
        assert response.status_code == 502

    async def test_missing_title(self, client: AsyncClient) -> None:
        """Missing title returns 422."""
        response = await client.post(
            "/api/v1/generation/suno",
            json={
                "model": "V5",
                "lyrics": "Some lyrics",
                "style": "rock",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /generation/suno/{task_id}
# ---------------------------------------------------------------------------


class TestGetSunoTaskStatus:
    """Tests for GET /api/v1/generation/suno/{task_id}."""

    async def test_success_pending(
        self, client: AsyncClient, mock_task_lookup: AsyncMock
    ) -> None:
        """Returns task status when found."""
        task_id = uuid4()
        mock_task_lookup.get_task_by_id.return_value = {
            "id": task_id,
            "status": TaskStatus.PENDING.value,
            "audio_url_ok": None,
            "audio_url_alt": None,
            "downloaded_ok": False,
            "downloaded_alt": False,
        }

        response = await client.get(f"/api/v1/generation/suno/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(task_id)
        assert data["status"] == "pending"
        assert data["audio_url_ok"] is None

    async def test_success_completed(
        self, client: AsyncClient, mock_task_lookup: AsyncMock
    ) -> None:
        """Returns audio URLs when task is complete."""
        task_id = uuid4()
        mock_task_lookup.get_task_by_id.return_value = {
            "id": task_id,
            "status": TaskStatus.SUCCESS.value,
            "audio_url_ok": "https://cdn.suno.ai/ok-track.mp3",
            "audio_url_alt": "https://cdn.suno.ai/alt-track.mp3",
            "downloaded_ok": True,
            "downloaded_alt": False,
        }

        response = await client.get(f"/api/v1/generation/suno/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["audio_url_ok"] == "https://cdn.suno.ai/ok-track.mp3"
        assert data["audio_url_alt"] == "https://cdn.suno.ai/alt-track.mp3"
        assert data["downloaded_ok"] is True

    async def test_not_found(
        self, client: AsyncClient, mock_task_lookup: AsyncMock
    ) -> None:
        """Non-existent task returns 404."""
        mock_task_lookup.get_task_by_id.return_value = None
        task_id = uuid4()

        response = await client.get(f"/api/v1/generation/suno/{task_id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /generation/image
# ---------------------------------------------------------------------------


class TestGenerateImage:
    """Tests for POST /api/v1/generation/image."""

    async def test_success(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """Valid request returns 200 with base64 image."""
        response = await client.post(
            "/api/v1/generation/image",
            json={
                "prompt": "A beautiful sunset over the ocean",
                "provider": "fal",
                "resolution": "1920x1080",
                "style_strength": 0.7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_base64" in data
        # Should be valid base64
        decoded = base64.b64decode(data["image_base64"])
        assert len(decoded) > 0
        mock_generation_service.submit_image.assert_awaited_once()

    async def test_with_base_image(
        self, client: AsyncClient, mock_generation_service: AsyncMock
    ) -> None:
        """Request with base_image is accepted."""
        fake_image = base64.b64encode(b"fake png data").decode()
        response = await client.post(
            "/api/v1/generation/image",
            json={
                "prompt": "Enhance this image",
                "provider": "slai",
                "resolution": "1024x1024",
                "base_image": fake_image,
            },
        )
        assert response.status_code == 200

    async def test_invalid_provider(self, client: AsyncClient) -> None:
        """Invalid provider returns 422."""
        response = await client.post(
            "/api/v1/generation/image",
            json={
                "prompt": "Test prompt",
                "provider": "invalid",
                "resolution": "1920x1080",
            },
        )
        assert response.status_code == 422

    async def test_invalid_resolution_format(self, client: AsyncClient) -> None:
        """Invalid resolution format returns 422."""
        response = await client.post(
            "/api/v1/generation/image",
            json={
                "prompt": "Test prompt",
                "provider": "fal",
                "resolution": "invalid",
            },
        )
        assert response.status_code == 422

    async def test_prompt_too_long(self, client: AsyncClient) -> None:
        """Prompt exceeding 2000 chars returns 422."""
        response = await client.post(
            "/api/v1/generation/image",
            json={
                "prompt": "A" * 2001,
                "provider": "fal",
                "resolution": "1920x1080",
            },
        )
        assert response.status_code == 422

    async def test_style_strength_out_of_range(self, client: AsyncClient) -> None:
        """style_strength > 1.0 returns 422."""
        response = await client.post(
            "/api/v1/generation/image",
            json={
                "prompt": "Test",
                "provider": "fal",
                "resolution": "1920x1080",
                "style_strength": 1.5,
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /callbacks/suno
# ---------------------------------------------------------------------------


class TestSunoCallback:
    """Tests for POST /api/v1/callbacks/suno."""

    async def test_success_with_recognized_task(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
        mock_notification: AsyncMock,
    ) -> None:
        """Valid callback with recognized task updates status and pushes notification."""
        task_id = uuid4()
        user_id = str(uuid4())
        mock_suno_task_repo.find_by_external_id.return_value = {
            "id": task_id,
            "user_id": user_id,
            "status": TaskStatus.PENDING.value,
        }

        response = await client.post(
            "/api/v1/callbacks/suno",
            json={
                "task_id": "ext-task-123",
                "status": "SUCCESS",
                "audio_url_ok": "https://cdn.suno.ai/ok.mp3",
                "audio_url_alt": "https://cdn.suno.ai/alt.mp3",
            },
        )
        assert response.status_code == 200
        mock_suno_task_repo.find_by_external_id.assert_awaited_once_with("ext-task-123")
        mock_suno_task_repo.update_status.assert_awaited_once_with(
            task_id,
            status=TaskStatus.SUCCESS,
            audio_url_ok="https://cdn.suno.ai/ok.mp3",
            audio_url_alt="https://cdn.suno.ai/alt.mp3",
        )
        mock_notification.push.assert_awaited_once()

    async def test_unrecognized_task_id(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
        mock_notification: AsyncMock,
    ) -> None:
        """Unrecognized task_id is discarded with 200 (Req 11.8)."""
        mock_suno_task_repo.find_by_external_id.return_value = None

        response = await client.post(
            "/api/v1/callbacks/suno",
            json={"task_id": "unknown-task", "status": "SUCCESS"},
        )
        assert response.status_code == 200
        mock_suno_task_repo.update_status.assert_not_awaited()
        mock_notification.push.assert_not_awaited()

    async def test_malformed_payload(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
    ) -> None:
        """Malformed payload is discarded with 200 (Req 11.8)."""
        response = await client.post(
            "/api/v1/callbacks/suno",
            content=b"not valid json{{{",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        mock_suno_task_repo.find_by_external_id.assert_not_awaited()

    async def test_no_task_id_in_payload(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
    ) -> None:
        """Payload without task_id is discarded (Req 11.8)."""
        response = await client.post(
            "/api/v1/callbacks/suno",
            json={"status": "SUCCESS", "audio_url": "https://example.com/audio.mp3"},
        )
        assert response.status_code == 200
        mock_suno_task_repo.find_by_external_id.assert_not_awaited()

    async def test_failed_status(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
        mock_notification: AsyncMock,
    ) -> None:
        """FAILED status is properly stored."""
        task_id = uuid4()
        user_id = str(uuid4())
        mock_suno_task_repo.find_by_external_id.return_value = {
            "id": task_id,
            "user_id": user_id,
            "status": TaskStatus.PENDING.value,
        }

        response = await client.post(
            "/api/v1/callbacks/suno",
            json={"task_id": "ext-task-456", "status": "FAILED"},
        )
        assert response.status_code == 200
        mock_suno_task_repo.update_status.assert_awaited_once_with(
            task_id,
            status=TaskStatus.FAILED,
            audio_url_ok=None,
            audio_url_alt=None,
        )

    async def test_nested_data_payload(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
        mock_notification: AsyncMock,
    ) -> None:
        """Handles nested data field format from Suno."""
        task_id = uuid4()
        user_id = str(uuid4())
        mock_suno_task_repo.find_by_external_id.return_value = {
            "id": task_id,
            "user_id": user_id,
            "status": TaskStatus.PENDING.value,
        }

        response = await client.post(
            "/api/v1/callbacks/suno",
            json={
                "data": {
                    "task_id": "ext-nested-789",
                    "status": "COMPLETE",
                    "audio_url_ok": "https://cdn.suno.ai/nested-ok.mp3",
                    "audio_url_alt": "https://cdn.suno.ai/nested-alt.mp3",
                }
            },
        )
        assert response.status_code == 200
        mock_suno_task_repo.find_by_external_id.assert_awaited_once_with("ext-nested-789")
        mock_suno_task_repo.update_status.assert_awaited_once()
