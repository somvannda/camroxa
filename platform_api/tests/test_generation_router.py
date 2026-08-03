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
from uuid import UUID, uuid4

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
from platform_api.routers.callbacks import (
    _get_batch_service as _get_callback_batch_service,
    _get_image_job_service,
    _get_notification_port,
    _get_suno_task_repo,
)
from platform_api.routers.generation import (
    _get_batch_service,
    _get_enforcement_service,
    _get_generation_service,
    _get_job_queue_repo,
    _get_task_lookup,
    _get_ai_routing_service,
    _get_prompt_service,
    _get_profile_service,
)
from platform_api.services.job_types import JOB_RETRY_SONG_SUNO


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")


@pytest.fixture
def mock_enforcement_service() -> AsyncMock:
    """Create a mock UsageEnforcementService.

    By default, check_and_deduct / deduct_for_operation succeed.
    """
    from types import SimpleNamespace

    service = AsyncMock()
    service.check_and_deduct = AsyncMock(return_value=10)
    service.deduct_for_operation = AsyncMock(return_value=0)
    service.refund_failed_operation = AsyncMock()
    service.resolve_max_credits = AsyncMock(return_value=5)
    service.preflight_quotas_and_balance = AsyncMock()
    service.reserve_and_hold_before_provider = AsyncMock(
        return_value=SimpleNamespace(held_units=0, plan_covered=True)
    )
    service.finalize_held_operation = AsyncMock(return_value=0)
    return service


@pytest.fixture
def mock_generation_service() -> AsyncMock:
    """Create a mock GenerationService."""
    from types import SimpleNamespace

    service = AsyncMock()
    service.submit_draft = AsyncMock(
        return_value=SongDraft(title="Test Song", album="Test Album", lyrics="[Verse]\nLyrics here")
    )
    service.polish_lyrics_text = AsyncMock(return_value="[Verse]\nPolished lyrics here")
    service.submit_suno = AsyncMock(return_value=str(uuid4()))
    service.submit_image = AsyncMock(return_value=b"\x89PNG\r\n\x1a\nfakedata")
    service.submit_image_outcome = AsyncMock(
        return_value=SimpleNamespace(
            image_bytes=b"\x89PNG\r\n\x1a\nfakedata",
            provider="fal",
            sub_model="flux-pro",
        )
    )
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
def mock_callback_batch_service() -> AsyncMock:
    service = AsyncMock()
    service.handle_suno_task_update = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_image_job_service() -> AsyncMock:
    svc = AsyncMock()
    svc.run_pending_jobs = AsyncMock(return_value=0)
    return svc


@pytest.fixture
def mock_ai_routing_service() -> AsyncMock:
    """Create a mock AIRoutingService.

    Returns a RoutingResult with default fal provider for image operations.
    """
    from platform_api.services.ai_routing_service import RoutingResult

    service = AsyncMock()
    routing = RoutingResult(
        provider="fal",
        sub_model="flux-pro",
        service_type="image_generation",
    )
    service.resolve = AsyncMock(return_value=routing)
    service.resolve_image_chain = AsyncMock(return_value=[routing])
    text_routing = RoutingResult(
        provider="deepseek",
        sub_model="deepseek-chat",
        service_type="text_generation",
    )
    service.resolve_text_chain = AsyncMock(return_value=[text_routing])
    return service


@pytest.fixture
def mock_prompt_service() -> AsyncMock:
    service = AsyncMock()
    description = type("Description", (), {"content": "Full hidden admin description"})()
    structure = type("Structure", (), {"content": "[Verse]\n[Chorus]\n[Bridge]"})()
    mood = type("Mood", (), {"content": "Warm nostalgia with soft ache"})()
    service.get_description_for_access = AsyncMock(return_value=description)
    service.get_structure_for_access = AsyncMock(return_value=structure)
    service.get_mood_for_access = AsyncMock(return_value=mood)
    return service


@pytest.fixture
def mock_profile_service() -> AsyncMock:
    service = AsyncMock()
    service.require_owned_profile = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_batch_service() -> AsyncMock:
    service = AsyncMock()
    service.validate_song_suno_retry = AsyncMock(return_value=None)
    service.retry_song_suno = AsyncMock(return_value=None)
    service.latest_suno_failure_hint = AsyncMock(return_value=None)
    service.lyric_rewrite_context_for_user_song = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_job_queue() -> AsyncMock:
    queue = AsyncMock()
    queue.enqueue = AsyncMock(return_value=None)
    return queue


@pytest.fixture
def app(
    mock_generation_service: AsyncMock,
    mock_enforcement_service: AsyncMock,
    mock_task_lookup: AsyncMock,
    mock_suno_task_repo: AsyncMock,
    mock_notification: AsyncMock,
    mock_callback_batch_service: AsyncMock,
    mock_image_job_service: AsyncMock,
    mock_ai_routing_service: AsyncMock,
    mock_prompt_service: AsyncMock,
    mock_profile_service: AsyncMock,
    mock_batch_service: AsyncMock,
    mock_job_queue: AsyncMock,
):
    """Create a test app with all dependencies overridden."""
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    application.dependency_overrides[_get_generation_service] = lambda: mock_generation_service
    application.dependency_overrides[_get_enforcement_service] = lambda: mock_enforcement_service
    application.dependency_overrides[_get_ai_routing_service] = lambda: mock_ai_routing_service
    application.dependency_overrides[_get_prompt_service] = lambda: mock_prompt_service
    application.dependency_overrides[_get_profile_service] = lambda: mock_profile_service
    application.dependency_overrides[_get_batch_service] = lambda: mock_batch_service
    application.dependency_overrides[_get_job_queue_repo] = lambda: mock_job_queue
    application.dependency_overrides[_get_task_lookup] = lambda: mock_task_lookup
    application.dependency_overrides[_get_suno_task_repo] = lambda: mock_suno_task_repo
    application.dependency_overrides[_get_notification_port] = lambda: mock_notification
    application.dependency_overrides[_get_callback_batch_service] = lambda: mock_callback_batch_service
    application.dependency_overrides[_get_image_job_service] = lambda: mock_image_job_service
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

    async def test_split_bills_lyric_title_album(
        self,
        client: AsyncClient,
        mock_enforcement_service: AsyncMock,
        mock_generation_service: AsyncMock,
    ) -> None:
        """Direct draft path bills each LLM slot like batch (H5)."""
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
        assert mock_enforcement_service.deduct_for_operation.await_count == 3
        ops = [
            call.args[2]
            for call in mock_enforcement_service.deduct_for_operation.await_args_list
        ]
        assert ops == ["lyric", "title", "album"]
        mock_generation_service.submit_draft.assert_awaited_once()

    async def test_forced_title_skips_title_slot(
        self,
        client: AsyncClient,
        mock_enforcement_service: AsyncMock,
    ) -> None:
        response = await client.post(
            "/api/v1/generation/draft",
            json={
                "description": "Rock ballad",
                "structure": "[Verse]\n[Chorus]",
                "forced_title": "My Forced Title",
            },
        )
        assert response.status_code == 200
        ops = [
            call.args[2]
            for call in mock_enforcement_service.deduct_for_operation.await_args_list
        ]
        assert ops == ["lyric", "album"]

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

    async def test_resolves_hidden_prompt_content_from_ids(
        self,
        client: AsyncClient,
        mock_generation_service: AsyncMock,
        mock_prompt_service: AsyncMock,
    ) -> None:
        response = await client.post(
            "/api/v1/generation/draft",
            json={
                "description_id": str(uuid4()),
                "structure_id": str(uuid4()),
            },
        )
        assert response.status_code == 200

        _, draft_request = mock_generation_service.submit_draft.await_args.args[:2]
        assert draft_request.description == "Full hidden admin description"
        assert draft_request.structure == "[Verse]\n[Chorus]\n[Bridge]"
        mock_prompt_service.get_description_for_access.assert_awaited_once()
        mock_prompt_service.get_structure_for_access.assert_awaited_once()

    async def test_missing_description(self, client: AsyncClient) -> None:
        """Missing description source returns 422."""
        response = await client.post(
            "/api/v1/generation/draft",
            json={"structure": "[Verse]"},
        )
        assert response.status_code == 422

    async def test_missing_structure(self, client: AsyncClient) -> None:
        """Missing structure source returns 422."""
        response = await client.post(
            "/api/v1/generation/draft",
            json={"description": "Test song"},
        )
        assert response.status_code == 422

    async def test_invalid_structure_without_headers(self, client: AsyncClient) -> None:
        """Structure without bracket headers returns 422."""
        response = await client.post(
            "/api/v1/generation/draft",
            json={"description": "Test song", "structure": "Verse / Chorus / Bridge"},
        )
        assert response.status_code == 422

    async def test_insufficient_credits(
        self, client: AsyncClient, mock_enforcement_service: AsyncMock
    ) -> None:
        """InsufficientCreditsError from enforcement returns 402."""
        mock_enforcement_service.deduct_for_operation.side_effect = (
            InsufficientCreditsError(details={"required": 10})
        )
        response = await client.post(
            "/api/v1/generation/draft",
            json={"description": "Test", "structure": "[Verse]\n[Chorus]\n[Bridge]\n[Outro]"},
        )
        assert response.status_code == 402


# ---------------------------------------------------------------------------
# POST /generation/polish-lyrics
# ---------------------------------------------------------------------------


class TestPolishLyrics:
    """Tests for POST /api/v1/generation/polish-lyrics."""

    async def test_success(
        self,
        client: AsyncClient,
        mock_generation_service: AsyncMock,
        mock_enforcement_service: AsyncMock,
    ) -> None:
        response = await client.post(
            "/api/v1/generation/polish-lyrics",
            json={"lyrics": "[Verse]\nLine one", "strength": 60},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["lyrics"] == "[Verse]\nPolished lyrics here"
        assert data["suno_queued"] is False
        mock_enforcement_service.check_and_deduct.assert_awaited_once()
        call = mock_enforcement_service.check_and_deduct.await_args
        assert call.kwargs["operation_type"] == "lyric"
        mock_generation_service.polish_lyrics_text.assert_awaited_once()

    async def test_refunds_on_llm_failure(
        self,
        client: AsyncClient,
        mock_generation_service: AsyncMock,
        mock_enforcement_service: AsyncMock,
    ) -> None:
        mock_generation_service.polish_lyrics_text.side_effect = ExternalServiceError(
            "Polish returned empty lyrics.",
            is_retryable=True,
        )
        response = await client.post(
            "/api/v1/generation/polish-lyrics",
            json={"lyrics": "[Verse]\nLine one", "strength": 40},
        )
        assert response.status_code in {502, 503}
        mock_enforcement_service.refund_failed_operation.assert_awaited_once()
        refund_call = mock_enforcement_service.refund_failed_operation.await_args
        assert refund_call.kwargs["reason"] == "polish_failed"

    async def test_uses_chat_llm_chain_not_suno(
        self,
        client: AsyncClient,
        mock_generation_service: AsyncMock,
        mock_ai_routing_service: AsyncMock,
    ) -> None:
        from platform_api.services.ai_routing_service import RoutingResult

        mock_ai_routing_service.resolve_text_chain = AsyncMock(
            return_value=[
                RoutingResult(
                    provider="suno",
                    sub_model="lyrics",
                    service_type="music_generation",
                ),
                RoutingResult(
                    provider="deepseek",
                    sub_model="deepseek-chat",
                    service_type="text_generation",
                ),
            ]
        )
        response = await client.post(
            "/api/v1/generation/polish-lyrics",
            json={"lyrics": "[Verse]\nLine one", "strength": 60},
        )
        assert response.status_code == 200
        mock_generation_service.polish_lyrics_text.assert_awaited_once()
        call = mock_generation_service.polish_lyrics_text.await_args
        assert call.args[3] == "deepseek"
        assert call.kwargs["provider_chain"] == [
            ("deepseek", "deepseek-chat"),
        ]

    async def test_queues_suno_when_history_context_provided(
        self,
        client: AsyncClient,
        mock_generation_service: AsyncMock,
        mock_batch_service: AsyncMock,
        mock_job_queue: AsyncMock,
    ) -> None:
        batch_id = str(uuid4())
        song_id = str(uuid4())
        response = await client.post(
            "/api/v1/generation/polish-lyrics",
            json={
                "lyrics": "[Verse]\nLine one",
                "strength": 60,
                "batch_id": batch_id,
                "song_id": song_id,
                "title": "Retry Title",
                "album": "Retry Album",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["suno_queued"] is True
        mock_batch_service.validate_song_suno_retry.assert_awaited_once()
        validate_call = mock_batch_service.validate_song_suno_retry.await_args
        assert validate_call.kwargs["batch_id"] == UUID(batch_id)
        assert validate_call.kwargs["song_id"] == UUID(song_id)
        assert validate_call.kwargs["lyrics_override"] == "[Verse]\nPolished lyrics here"
        assert validate_call.kwargs["title_override"] == "Retry Title"
        mock_job_queue.enqueue.assert_awaited_once()
        enqueue_kwargs = mock_job_queue.enqueue.await_args.kwargs
        assert enqueue_kwargs["job_type"] == JOB_RETRY_SONG_SUNO
        assert enqueue_kwargs["payload"]["lyrics"] == "[Verse]\nPolished lyrics here"


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
        mock_generation_service.submit_image_outcome.assert_awaited_once()

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
        mock_callback_batch_service: AsyncMock,
    ) -> None:
        """Valid callback with recognized task updates status and pushes notification."""
        task_id = uuid4()
        user_id = str(uuid4())
        mock_suno_task_repo.find_by_external_id.return_value = {
            "id": task_id,
            "user_id": user_id,
            "song_id": str(uuid4()),
            "batch_id": str(uuid4()),
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
        mock_callback_batch_service.handle_suno_task_update.assert_awaited_once()

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
        mock_callback_batch_service: AsyncMock,
    ) -> None:
        """FAILED status is properly stored."""
        task_id = uuid4()
        user_id = str(uuid4())
        mock_suno_task_repo.find_by_external_id.return_value = {
            "id": task_id,
            "user_id": user_id,
            "song_id": str(uuid4()),
            "batch_id": str(uuid4()),
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
        mock_callback_batch_service.handle_suno_task_update.assert_awaited_once()

    async def test_nested_data_payload(
        self,
        client: AsyncClient,
        mock_suno_task_repo: AsyncMock,
        mock_notification: AsyncMock,
        mock_callback_batch_service: AsyncMock,
    ) -> None:
        """Handles nested data field format from Suno."""
        task_id = uuid4()
        user_id = str(uuid4())
        mock_suno_task_repo.find_by_external_id.return_value = {
            "id": task_id,
            "user_id": user_id,
            "song_id": str(uuid4()),
            "batch_id": str(uuid4()),
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
        mock_callback_batch_service.handle_suno_task_update.assert_awaited_once()
