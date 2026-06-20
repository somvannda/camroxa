"""Unit tests for GenerationService.

Tests song draft generation (LLM), Suno submission, and image generation
using mock clients and repositories.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    ValidationError,
)
from platform_api.models.domain import SunoTask
from platform_api.models.enums import TaskStatus
from platform_api.ports.generation_port import (
    DraftRequest,
    ImageRequest,
    SongDraft,
    SunoRequest,
)
from platform_api.services.generation_service import (
    GenerationService,
    _check_avoid_list,
    _normalize_text,
    _parse_resolution,
    compute_suno_request_hash,
    validate_lyrics_structure,
)


# ---------------------------------------------------------------------------
# Mock / Fake Collaborators
# ---------------------------------------------------------------------------


class FakeCreditService:
    """Fake credit service that tracks deductions and refunds."""

    def __init__(self, *, balance: int = 1000, should_fail: bool = False) -> None:
        self.balance = balance
        self.should_fail = should_fail
        self.deductions: list[tuple[str, int, str, str]] = []
        self.refunds: list[tuple[str, int, str, str]] = []

    async def deduct(self, user_id: str, amount: int, reason: str, ref_id: str) -> bool:
        if self.should_fail or self.balance < amount:
            return False
        self.balance -= amount
        self.deductions.append((user_id, amount, reason, ref_id))
        return True

    async def refund(self, user_id: str, amount: int, reason: str, ref_id: str) -> None:
        self.balance += amount
        self.refunds.append((user_id, amount, reason, ref_id))


class FakePricingRepo:
    """Fake pricing repo that returns configured prices."""

    def __init__(self, prices: dict[tuple[str, str], int] | None = None) -> None:
        self._prices = prices or {
            ("deepseek", "draft"): 2,
            ("v5", "suno"): 14,
            ("v5_5", "suno"): 14,
            ("fal", "image"): 3,
            ("slai", "image"): 3,
        }

    async def get_price(self, model_identifier: str, operation_type: str) -> int | None:
        return self._prices.get((model_identifier, operation_type))


class FakeTaskRepo:
    """Fake task repo for Suno task dedup and persistence."""

    def __init__(self) -> None:
        self.tasks: list[SunoTask] = []

    async def find_by_hash(self, user_id: UUID, request_hash: str) -> SunoTask | None:
        for task in self.tasks:
            if task.user_id == user_id and task.request_hash == request_hash:
                return task
        return None

    async def create(self, task: SunoTask) -> SunoTask:
        self.tasks.append(task)
        return task


class FakeLlmClient:
    """Fake LLM client that returns configured responses."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = responses or []
        self._call_count = 0

    async def generate_song_draft(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> dict[str, Any]:
        if self._call_count >= len(self._responses):
            raise ExternalServiceError("LLM unavailable", is_retryable=True)
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp


class FakeSunoClient:
    """Fake Suno client that returns a task ID."""

    def __init__(self, task_id: str = "suno-task-123", should_fail: bool = False) -> None:
        self._task_id = task_id
        self._should_fail = should_fail

    async def submit_task(
        self, *, model: str, title: str, lyrics: str, style: str,
        instrumental: bool, callback_url: str | None
    ) -> dict[str, Any]:
        if self._should_fail:
            raise ExternalServiceError("Suno unreachable", is_retryable=True)
        return {"taskId": self._task_id}


class FakeFalClient:
    """Fake Fal AI client."""

    def __init__(self, image_b64: str | None = None, should_fail: bool = False) -> None:
        self._image_b64 = image_b64 or base64.b64encode(b"fake-png-data").decode()
        self._should_fail = should_fail

    async def generate_image(
        self, *, prompt: str, model_id: str, width: int, height: int,
        num_images: int, extra_params: dict[str, Any] | None
    ) -> dict[str, Any]:
        if self._should_fail:
            raise ExternalServiceError("Fal AI error", is_retryable=True)
        return {"images": [{"base64": self._image_b64}]}


class FakeSlaiClient:
    """Fake SLAI client."""

    def __init__(self, image_b64: str | None = None, should_fail: bool = False) -> None:
        self._image_b64 = image_b64 or base64.b64encode(b"fake-png-data").decode()
        self._should_fail = should_fail

    async def generate_image(
        self, *, prompt: str, width: int, height: int, style_strength: float,
        reference_image_base64: str | None, extra_params: dict[str, Any] | None
    ) -> dict[str, Any]:
        if self._should_fail:
            raise ExternalServiceError("SLAI error", is_retryable=True)
        return {"image": self._image_b64}


# ---------------------------------------------------------------------------
# Helper to build a valid LLM response
# ---------------------------------------------------------------------------


def make_llm_response(title: str, album: str, lyrics: str) -> dict[str, Any]:
    """Create a properly structured LLM chat completion response."""
    content = json.dumps({"title": title, "album": album, "lyrics": lyrics})
    return {
        "choices": [{"message": {"content": content}}]
    }


def make_valid_lyrics(headers: list[str], content_per_section: int = 5) -> str:
    """Generate valid lyrics with headers and enough content lines."""
    parts: list[str] = []
    for header in headers:
        parts.append(header)
        for i in range(content_per_section):
            parts.append(f"Line {i + 1} of section {header}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def credit_service() -> FakeCreditService:
    return FakeCreditService(balance=1000)


@pytest.fixture
def pricing_repo() -> FakePricingRepo:
    return FakePricingRepo()


@pytest.fixture
def task_repo() -> FakeTaskRepo:
    return FakeTaskRepo()


# ---------------------------------------------------------------------------
# Tests: Pure Helpers
# ---------------------------------------------------------------------------


class TestValidateLyricsStructure:
    """Tests for validate_lyrics_structure."""

    def test_valid_lyrics_with_headers(self):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        assert validate_lyrics_structure(lyrics, headers) is True

    def test_content_before_first_header_fails(self):
        lyrics = "Some content before header\n[Verse]\nLine 1\n" * 20
        assert validate_lyrics_structure(lyrics, ["[Verse]"]) is False

    def test_wrong_header_order_fails(self):
        lyrics = "[Chorus]\nLine 1\nLine 2\nLine 3\nLine 4\n" * 5
        lyrics += "[Verse]\nLine 1\nLine 2\nLine 3\nLine 4\n" * 5
        assert validate_lyrics_structure(lyrics, ["[Verse]", "[Chorus]"]) is False

    def test_insufficient_content_lines_fails(self):
        # 4 headers × 4 = 16 required, only provide 3 per section = 12
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = "\n".join(
            f"{h}\n" + "\n".join(f"Line {j}" for j in range(3))
            for h in headers
        )
        assert validate_lyrics_structure(lyrics, headers) is False

    def test_no_headers_needs_32_content_lines(self):
        lyrics = "\n".join(f"Line {i}" for i in range(31))
        assert validate_lyrics_structure(lyrics, []) is False

        lyrics = "\n".join(f"Line {i}" for i in range(32))
        assert validate_lyrics_structure(lyrics, []) is True

    def test_empty_lyrics_fails(self):
        assert validate_lyrics_structure("", ["[Verse]"]) is False
        assert validate_lyrics_structure("", []) is False


class TestSunoRequestHash:
    """Tests for compute_suno_request_hash."""

    def test_deterministic(self):
        h1 = compute_suno_request_hash("V5", "Title", "Lyrics", "Pop", False)
        h2 = compute_suno_request_hash("V5", "Title", "Lyrics", "Pop", False)
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = compute_suno_request_hash("V5", "Title A", "Lyrics", "Pop", False)
        h2 = compute_suno_request_hash("V5", "Title B", "Lyrics", "Pop", False)
        assert h1 != h2

    def test_whitespace_normalized(self):
        h1 = compute_suno_request_hash("V5", "  Title  ", "Lyrics", "Pop", False)
        h2 = compute_suno_request_hash("V5", "Title", "Lyrics", "Pop", False)
        assert h1 == h2

    def test_hash_is_sha256_hex(self):
        h = compute_suno_request_hash("V5", "Title", "Lyrics", "Pop", False)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestNormalizeText:
    """Tests for _normalize_text."""

    def test_lowercase_and_strip(self):
        assert _normalize_text("  Hello World  ") == "hello world"

    def test_removes_accents(self):
        assert _normalize_text("café") == "cafe"

    def test_collapses_whitespace(self):
        assert _normalize_text("hello   world") == "hello world"


class TestCheckAvoidList:
    """Tests for _check_avoid_list."""

    def test_match_found(self):
        assert _check_avoid_list("Hello", ["hello", "world"]) is True

    def test_no_match(self):
        assert _check_avoid_list("Unique Title", ["other", "titles"]) is False

    def test_accent_insensitive(self):
        assert _check_avoid_list("Café", ["cafe"]) is True


class TestParseResolution:
    """Tests for _parse_resolution."""

    def test_valid(self):
        assert _parse_resolution("1920x1080") == (1920, 1080)

    def test_invalid(self):
        assert _parse_resolution("invalid") is None
        assert _parse_resolution("1920") is None

    def test_with_spaces(self):
        assert _parse_resolution(" 512x512 ") == (512, 512)


# ---------------------------------------------------------------------------
# Tests: submit_draft
# ---------------------------------------------------------------------------


class TestSubmitDraft:
    """Tests for GenerationService.submit_draft."""

    @pytest.mark.asyncio
    async def test_successful_draft_generation(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        llm_responses = [make_llm_response("My Song", "My Album", lyrics)]
        llm_client = FakeLlmClient(responses=llm_responses)

        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=llm_client,
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )

        request = DraftRequest(
            language="en",
            creativity_level=50,
            description="A pop song",
            structure="\n".join(headers),
        )
        result = await service.submit_draft("user-123", request)

        assert result.title == "My Song"
        assert result.album == "My Album"
        assert len(credit_service.deductions) == 1
        assert len(credit_service.refunds) == 0

    @pytest.mark.asyncio
    async def test_insufficient_credits_raises(self, pricing_repo, task_repo):
        credit_service = FakeCreditService(balance=0)
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="[Verse]",
        )
        with pytest.raises(InsufficientCreditsError):
            await service.submit_draft("user-123", request)

    @pytest.mark.asyncio
    async def test_unparseable_response_retries(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        # First response is garbage, second is valid
        llm_responses = [
            {"choices": [{"message": {"content": "not json"}}]},
            make_llm_response("Good Title", "Good Album", lyrics),
        ]
        llm_client = FakeLlmClient(responses=llm_responses)

        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=llm_client,
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="\n".join(headers),
        )
        result = await service.submit_draft("user-123", request)
        assert result.title == "Good Title"

    @pytest.mark.asyncio
    async def test_all_attempts_exhausted_refunds(self, credit_service, pricing_repo, task_repo):
        # All responses are unparseable
        bad_responses = [
            {"choices": [{"message": {"content": "bad"}}]}
            for _ in range(8)
        ]
        llm_client = FakeLlmClient(responses=bad_responses)

        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=llm_client,
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="[Verse]",
        )
        with pytest.raises(ExternalServiceError):
            await service.submit_draft("user-123", request)

        # Credits should be refunded
        assert len(credit_service.refunds) == 1

    @pytest.mark.asyncio
    async def test_forced_title_bypasses_llm(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        llm_responses = [make_llm_response("LLM Title", "LLM Album", lyrics)]
        llm_client = FakeLlmClient(responses=llm_responses)

        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=llm_client,
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="\n".join(headers),
            forced_title="My Forced Title",
        )
        result = await service.submit_draft("user-123", request)
        assert result.title == "My Forced Title"
        assert result.album == "LLM Album"

    @pytest.mark.asyncio
    async def test_avoid_list_triggers_retry(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        # First generates avoided title, second generates unique title
        llm_responses = [
            make_llm_response("Avoided Title", "Good Album", lyrics),
            make_llm_response("Unique Title", "Good Album", lyrics),
        ]
        llm_client = FakeLlmClient(responses=llm_responses)

        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=llm_client,
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="\n".join(headers),
            avoid_titles=["Avoided Title"],
        )
        result = await service.submit_draft("user-123", request)
        assert result.title == "Unique Title"


# ---------------------------------------------------------------------------
# Tests: submit_suno
# ---------------------------------------------------------------------------


class TestSubmitSuno:
    """Tests for GenerationService.submit_suno."""

    @pytest.mark.asyncio
    async def test_successful_submission(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(task_id="ext-task-456"),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = SunoRequest(model="V5", title="Song", lyrics="La la la", style="Pop")
        user_id = str(uuid4())
        task_id = await service.submit_suno(user_id, request)

        assert task_id  # Non-empty string
        assert len(task_repo.tasks) == 1
        assert task_repo.tasks[0].external_task_id == "ext-task-456"
        assert len(credit_service.deductions) == 1

    @pytest.mark.asyncio
    async def test_duplicate_returns_existing_task(self, credit_service, pricing_repo, task_repo):
        user_id = "user-123"
        user_uuid = UUID("00000000-0000-0000-0000-000000000123")
        request = SunoRequest(model="V5", title="Song", lyrics="La la la", style="Pop")
        request_hash = compute_suno_request_hash("V5", "Song", "La la la", "Pop", False)

        # Pre-populate with an existing task
        existing = SunoTask(
            id=uuid4(),
            user_id=user_uuid,
            request_hash=request_hash,
            model="V5",
            title="Song",
            status=TaskStatus.PENDING,
        )
        task_repo.tasks.append(existing)

        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )

        # Need to use same UUID in user_id
        # Override the task_repo to match the user_id format
        task_repo.tasks[0].user_id = UUID(int=0)

        # Use a user_id that matches
        result = await service.submit_suno(
            "00000000-0000-0000-0000-000000000000", request
        )
        assert result == str(existing.id)
        # No new deductions since it's a duplicate
        assert len(credit_service.deductions) == 0

    @pytest.mark.asyncio
    async def test_suno_failure_refunds_credits(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(should_fail=True),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = SunoRequest(model="V5", title="Song", lyrics="La la la", style="Pop")
        user_id = str(uuid4())

        with pytest.raises(ExternalServiceError):
            await service.submit_suno(user_id, request)

        # Credits deducted then refunded
        assert len(credit_service.deductions) == 1
        assert len(credit_service.refunds) == 1


# ---------------------------------------------------------------------------
# Tests: submit_image
# ---------------------------------------------------------------------------


class TestSubmitImage:
    """Tests for GenerationService.submit_image."""

    @pytest.mark.asyncio
    async def test_successful_fal_image(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="A sunset landscape",
            provider="fal",
            resolution="1024x1024",
            style_strength=0.5,
        )
        result = await service.submit_image("user-123", request)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert len(credit_service.deductions) == 1

    @pytest.mark.asyncio
    async def test_successful_slai_image(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="A sunset landscape",
            provider="slai",
            resolution="1024x1024",
            style_strength=0.5,
        )
        result = await service.submit_image("user-123", request)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_invalid_resolution_too_small(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="Valid prompt", provider="fal",
            resolution="256x256", style_strength=0.5,
        )
        with pytest.raises(ValidationError):
            await service.submit_image("user-123", request)

    @pytest.mark.asyncio
    async def test_invalid_resolution_too_large(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="Valid prompt", provider="fal",
            resolution="4096x4096", style_strength=0.5,
        )
        with pytest.raises(ValidationError):
            await service.submit_image("user-123", request)

    @pytest.mark.asyncio
    async def test_invalid_style_strength(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="Valid prompt", provider="fal",
            resolution="1024x1024", style_strength=1.5,
        )
        with pytest.raises(ValidationError):
            await service.submit_image("user-123", request)

    @pytest.mark.asyncio
    async def test_prompt_too_long(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="x" * 2001, provider="fal",
            resolution="1024x1024", style_strength=0.5,
        )
        with pytest.raises(ValidationError):
            await service.submit_image("user-123", request)

    @pytest.mark.asyncio
    async def test_base_image_too_large(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        large_image = b"x" * (10 * 1024 * 1024 + 1)
        request = ImageRequest(
            prompt="Valid prompt", provider="fal",
            resolution="1024x1024", style_strength=0.5,
            base_image=large_image,
        )
        with pytest.raises(ValidationError):
            await service.submit_image("user-123", request)

    @pytest.mark.asyncio
    async def test_provider_failure_refunds(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(should_fail=True),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="A sunset", provider="fal",
            resolution="1024x1024", style_strength=0.5,
        )
        with pytest.raises(ExternalServiceError):
            await service.submit_image("user-123", request)

        # Credits deducted then refunded
        assert len(credit_service.deductions) == 1
        assert len(credit_service.refunds) == 1

    @pytest.mark.asyncio
    async def test_empty_prompt_rejected(self, credit_service, pricing_repo, task_repo):
        service = GenerationService(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(),
            fal_client=FakeFalClient(),
            slai_client=FakeSlaiClient(),
        )
        request = ImageRequest(
            prompt="", provider="fal",
            resolution="1024x1024", style_strength=0.5,
        )
        with pytest.raises(ValidationError):
            await service.submit_image("user-123", request)
