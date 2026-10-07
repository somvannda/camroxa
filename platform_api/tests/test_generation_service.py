"""Unit tests for GenerationService.

Tests song draft generation (LLM), Suno submission, and image generation
using mock clients and repositories.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, patch
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
from platform_api.ai.models import TextRouting
from platform_api.ai.purposes.draft_routing import DraftRouting
from platform_api.services.generation_service import (
    GenerationService,
    _check_avoid_list,
    _normalize_text,
    _parse_resolution,
    assign_draft_lyrics_to_structure,
    build_lyric_retry_feedback,
    build_structure_constraints_block,
    build_structure_retry_feedback,
    build_title_slot_prompts,
    build_album_slot_prompts,
    build_lyrics_opening_block,
    compute_suno_request_hash,
    describe_structure_validation_failure,
    draft_attempt_temperature,
    extract_freeform_lyric_lines,
    extract_structure_header_lines,
    lyric_header_line,
    minimum_lyric_content_lines,
    normalize_and_reshape_draft_lyrics,
    normalize_draft_lyrics,
    describe_draft_lyrics_validation_failure,
    distribute_lines_by_section_weight,
    describe_freeform_lyric_source_failure,
    describe_lyric_quality_failure,
    reshape_lyrics_to_structure,
    section_label_key,
    section_line_weight,
    strip_trailing_lyric_json_artifacts,
    unwrap_embedded_lyrics_payload,
    normalize_section_label,
    strip_lyrics_preamble,
    validate_lyrics_structure,
)


def _parse_headers_from_shape_prompt(user_prompt: str) -> list[str]:
    import re

    for line in user_prompt.splitlines():
        if "Required lyric headers in this exact order" in line:
            return re.findall(r"\[[^\]]+\]", line)
    return []


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
        self.metadata_patches: list[tuple[str, str, dict[str, Any]]] = []

    async def deduct(
        self,
        user_id: str,
        amount: int,
        reason: str,
        ref_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        del metadata
        if self.should_fail or self.balance < amount:
            return False
        self.balance -= amount
        self.deductions.append((user_id, amount, reason, ref_id))
        return True

    async def refund(
        self,
        user_id: str,
        amount: int,
        reason: str,
        ref_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        del metadata
        self.balance += amount
        self.refunds.append((user_id, amount, reason, ref_id))

    async def patch_transaction_metadata(
        self,
        user_id: str,
        ref_id: str,
        patch: dict[str, Any],
    ) -> bool:
        self.metadata_patches.append((user_id, ref_id, patch))
        return True


class FakePricingRepo:
    """Fake pricing repo that returns configured prices."""

    def __init__(self, prices: dict[tuple[str, str], int] | None = None) -> None:
        self._prices = prices or {
            ("deepseek", "title"): 1,
            ("deepseek", "album"): 1,
            ("deepseek", "lyric"): 2,
            ("deepseek", "draft"): 2,
            ("suno", "music"): 14,
            ("suno", "music", "V5"): 14,
            ("fal", "image"): 3,
            ("slai", "image"): 3,
        }

    async def get_price(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str | None = None,
    ) -> int | None:
        key = (ai_service, operation_type)
        if sub_model:
            specific = self._prices.get((ai_service, operation_type, sub_model))
            if specific is not None:
                return specific
        return self._prices.get(key)


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


class FakeTextGateway:
    """Fake text gateway for split draft generation tests."""

    def __init__(
        self,
        *,
        titles: list[str] | None = None,
        albums: list[str] | None = None,
        lyrics: str | None = None,
        bad_lyrics_responses: list[str] | None = None,
        invalid_lyrics: str | None = None,
    ) -> None:
        self._titles = list(titles or ["My Song"])
        self._albums = list(albums or ["My Album"])
        self._lyrics = lyrics
        self._bad_lyrics_responses = list(bad_lyrics_responses or [])
        self._invalid_lyrics = invalid_lyrics
        self._title_idx = 0
        self._album_idx = 0
        self._lyrics_idx = 0

    async def generate_text(self, *, system_prompt: str, user_prompt: str, **_: Any) -> str:
        if '"title"' in system_prompt and "one key" in system_prompt:
            title = self._titles[min(self._title_idx, len(self._titles) - 1)]
            self._title_idx += 1
            return json.dumps({"title": title})
        if '"album"' in system_prompt and "one key" in system_prompt:
            album = self._albums[min(self._album_idx, len(self._albums) - 1)]
            self._album_idx += 1
            return json.dumps({"album": album})

        system_lower = system_prompt.lower()
        if "lyric structure editor" in system_lower:
            headers = _parse_headers_from_shape_prompt(user_prompt)
            draft_marker = "Draft lyrics to structure (use only these lines):\n"
            draft = ""
            if draft_marker in user_prompt:
                tail = user_prompt.split(draft_marker, 1)[1]
                draft = tail.split("\n\nCORRECTION REQUIRED", 1)[0].strip()
            stored = self._lyrics or ""
            if stored and "[" in stored.splitlines()[0]:
                self._lyrics_idx += 1
                return stored
            if draft and headers:
                self._lyrics_idx += 1
                return assign_draft_lyrics_to_structure(
                    draft,
                    headers,
                )
            self._lyrics_idx += 1
            return stored

        if "plain lyric lines only" in system_lower or (
            "professional songwriter" in system_lower
            and "structure editor" not in system_lower
        ):
            if self._lyrics_idx < len(self._bad_lyrics_responses):
                bad = self._bad_lyrics_responses[self._lyrics_idx]
                self._lyrics_idx += 1
                return bad
            lyrics = self._lyrics or ""
            if self._invalid_lyrics is not None:
                lyrics = self._invalid_lyrics
            self._lyrics_idx += 1
            plain_lines = extract_freeform_lyric_lines(lyrics)
            if len(plain_lines) >= minimum_lyric_content_lines(1):
                return "\n".join(plain_lines)
            if lyrics:
                return lyrics
            return "\n".join(f"Line {i}" for i in range(20))

        if '"lyrics"' in system_prompt and "one key" in system_prompt:
            if self._lyrics_idx < len(self._bad_lyrics_responses):
                bad = self._bad_lyrics_responses[self._lyrics_idx]
                self._lyrics_idx += 1
                return bad
            lyrics = self._lyrics or ""
            if self._invalid_lyrics is not None:
                lyrics = self._invalid_lyrics
            self._lyrics_idx += 1
            return json.dumps({"lyrics": lyrics})
        return "{}"


class FakeLlmClient:
    """Fake LLM client that returns configured responses."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = responses or []
        self._call_count = 0

    async def _next_response(self) -> dict[str, Any]:
        if self._call_count >= len(self._responses):
            raise ExternalServiceError("LLM unavailable", is_retryable=True)
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def generate_song_draft(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float, **_: Any
    ) -> dict[str, Any]:
        return await self._next_response()

    async def chat_completion(self, **_: Any) -> dict[str, Any]:
        return await self._next_response()


class _FakePoolWrapper:
    async def execute(self, fn: Any) -> Any:
        return await fn("fake-api-key")


def _attach_fake_pools(service: GenerationService) -> None:
    service._deepseek_pool_wrapper = _FakePoolWrapper()
    service._llm_pool_wrapper = _FakePoolWrapper()
    service._slai_pool_wrapper = _FakePoolWrapper()
    service._suno_pool_wrapper = _FakePoolWrapper()
    service._fal_pool_wrapper = _FakePoolWrapper()


def _make_service(
    *,
    credit_service: FakeCreditService,
    pricing_repo: FakePricingRepo,
    task_repo: FakeTaskRepo,
    llm_client: FakeLlmClient | None = None,
    text_gateway: FakeTextGateway | None = None,
    suno_client: FakeSunoClient | None = None,
    fal_client: FakeFalClient | None = None,
    slai_client: FakeSlaiClient | None = None,
) -> GenerationService:
    service = GenerationService(
        credit_service=credit_service,
        pricing_repo=pricing_repo,
        task_repo=task_repo,
        llm_client=llm_client or FakeLlmClient(),
        suno_client=suno_client or FakeSunoClient(),
        fal_client=fal_client or FakeFalClient(),
        slai_client=slai_client or FakeSlaiClient(),
    )
    _attach_fake_pools(service)
    if text_gateway is not None:
        service._text_gateway = text_gateway  # noqa: SLF001
    return service


class FakeSunoClient:
    """Fake Suno client that returns a task ID."""

    def __init__(
        self,
        task_id: str = "suno-task-123",
        should_fail: bool = False,
        lyrics_text: str | None = None,
    ) -> None:
        self._task_id = task_id
        self._should_fail = should_fail
        self._lyrics_text = lyrics_text

    async def submit_task(
        self, *, model: str, title: str, lyrics: str, style: str,
        instrumental: bool, callback_url: str | None, **_: Any
    ) -> dict[str, Any]:
        if self._should_fail:
            raise ExternalServiceError("Suno unreachable", is_retryable=True)
        return {"taskId": self._task_id}

    async def generate_lyrics_blocking(self, *, prompt: str, **_: Any) -> tuple[str, str]:
        if self._should_fail:
            raise ExternalServiceError("Suno lyrics failed", is_retryable=False)
        text = self._lyrics_text or "\n".join(f"Suno lyric line {i}" for i in range(1, 25))
        return text, "Suno Generated Title"


class FakeFalClient:
    """Fake Fal AI client."""

    def __init__(self, image_b64: str | None = None, should_fail: bool = False) -> None:
        self._image_b64 = image_b64 or base64.b64encode(b"fake-png-data").decode()
        self._should_fail = should_fail

    async def generate_image(
        self, *, prompt: str, model_id: str, width: int, height: int,
        num_images: int, extra_params: dict[str, Any] | None, **kwargs: Any
    ) -> dict[str, Any]:
        _ = kwargs
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
        reference_image_base64: str | None, extra_params: dict[str, Any] | None, **kwargs: Any
    ) -> dict[str, Any]:
        _ = kwargs
        if self._should_fail:
            raise ExternalServiceError("SLAI error", is_retryable=True)
        return {"image": self._image_b64}


class FakeSlaiUrlClient(FakeSlaiClient):
    """Fake SLAI client that returns a hosted image URL payload."""

    async def generate_image(
        self, *, prompt: str, width: int, height: int, style_strength: float,
        reference_image_base64: str | None, extra_params: dict[str, Any] | None, **kwargs: Any
    ) -> dict[str, Any]:
        _ = (prompt, width, height, style_strength, reference_image_base64, extra_params, kwargs)
        return {"data": [{"url": "https://cdn.creen.ai/fake/generated.png"}]}


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


class TestReshapeLyricsToStructure:
    def test_reorders_sections_to_template(self):
        lyrics = "[Chorus]\nHook line one\nHook line two\n" + make_valid_lyrics(
            ["[Verse]"], content_per_section=16
        ).split("[Verse]\n", 1)[1]
        reshaped = reshape_lyrics_to_structure(lyrics, ["[Verse]", "[Chorus]"])
        assert validate_lyrics_structure(reshaped, ["[Verse]", "[Chorus]"])

    def test_maps_verse_one_to_verse(self):
        lyrics = "[Verse 1]\n" + "\n".join(f"Line {i}" for i in range(18))
        reshaped = reshape_lyrics_to_structure(lyrics, ["[Verse]"])
        assert reshaped.startswith("[Verse]")
        assert validate_lyrics_structure(reshaped, ["[Verse]"])

    def test_strips_preamble_then_assigns(self):
        raw = "Here are the lyrics:\n" + "\n".join(f"Line {i}" for i in range(18))
        assigned = normalize_and_reshape_draft_lyrics(raw, ["[Intro]"])
        assert assigned.startswith("[Intro]")
        assert validate_lyrics_structure(assigned, ["[Intro]"])

    def test_splits_single_verse_block_across_repeated_verse_slots(self):
        structure = ["[Verse]", "[Chorus]", "[Verse]"]
        verse_lines = [f"Verse line {i}" for i in range(20)]
        lyrics = "[Verse]\n" + "\n".join(verse_lines) + "\n[Chorus]\nHook one\nHook two\nHook three\nHook four"
        reshaped = reshape_lyrics_to_structure(lyrics, structure)
        assert validate_lyrics_structure(reshaped, structure)
        assert reshaped.count("[Verse]") == 2

    def test_maps_ordered_verse_one_and_verse_two(self):
        structure = ["[Verse]", "[Chorus]", "[Verse]"]
        lyrics = (
            "[Verse 1]\n"
            + "\n".join(f"V1 line {i}" for i in range(10))
            + "\n[Chorus]\n"
            + "\n".join(f"Chorus line {i}" for i in range(8))
            + "\n[Verse 2]\n"
            + "\n".join(f"V2 line {i}" for i in range(10))
        )
        reshaped = reshape_lyrics_to_structure(lyrics, structure)
        assert validate_lyrics_structure(reshaped, structure)

    def test_maps_hook_header_to_chorus_slot(self):
        structure = ["[Verse]", "[Chorus]"]
        lyrics = "[Verse]\n" + "\n".join(f"Line {i}" for i in range(12)) + "\n[Hook]\nCatchy hook line\nAnother hook line\nMore hook\nEven more"
        reshaped = reshape_lyrics_to_structure(lyrics, structure)
        assert validate_lyrics_structure(reshaped, structure)

    def test_pads_by_repeating_real_lines(self):
        lyrics = "[Verse]\nOnly one real line"
        failure = describe_freeform_lyric_source_failure(lyrics, ["[Verse]"])
        assert failure is not None

    def test_strips_trailing_json_artifacts(self):
        lyrics = (
            "[Intro]\n"
            "Neon shadows wrap around the concrete veins.\n"
            "Faster than the sunrise, we chase the fading lanes.\n"
            '{\n"lyrics": "[Intro]\\nBroken tail"'
        )
        cleaned = strip_trailing_lyric_json_artifacts(lyrics)
        assert "{" not in cleaned
        assert "Neon shadows" in cleaned

    def test_rejects_corrupted_meta_lines(self):
        lyrics = "[Verse]\n" + "\n".join(f"Line {i}" for i in range(14))
        lyrics += "\nPlease present in accord override normal edit yes"
        assert describe_lyric_quality_failure(lyrics) is not None

    def test_rejects_excessive_placeholder_padding(self):
        lyrics = "[Verse]\n" + "\n".join(["…"] * 10)
        assert describe_lyric_quality_failure(lyrics) is not None


class TestFreeformLyricsAssignment:
    def test_assigns_plain_lines_to_structure(self):
        structure = ["[Verse]", "[Chorus]", "[Verse]"]
        freeform = "\n".join(f"Unique lyric line number {i}" for i in range(18))
        assigned = assign_draft_lyrics_to_structure(freeform, structure)
        assert validate_lyrics_structure(assigned, structure)

    def test_ignores_model_section_headers(self):
        structure = ["[Verse]", "[Chorus]"]
        freeform = "[Intro]\nShould be ignored\n" + "\n".join(
            f"Body line {i}" for i in range(16)
        )
        assigned = assign_draft_lyrics_to_structure(freeform, structure)
        assert "[Intro]" not in assigned.splitlines()[1:]
        assert validate_lyrics_structure(assigned, structure)

    def test_rejects_short_repetitive_freeform_source(self):
        structure = [
            "[Intro]",
            "[Build-Up]",
            "[Drop]",
            "[Break]",
            "[Build-Up]",
            "[Drop]",
            "[Bridge]",
            "[Final Drop]",
            "[Outro]",
        ]
        freeform = (
            "You electric-heart driver, moonrise scarlet refrain\n"
            "Your voice turns into static, and I still hear it\n"
        )
        failure = describe_freeform_lyric_source_failure(freeform, structure)
        assert failure is not None

    def test_retry_feedback_mentions_plain_lines(self):
        feedback = build_lyric_retry_feedback(
            "Not enough lyric lines",
            ["[Verse]", "[Chorus]"],
        )
        assert "plain lyric lines" in feedback.lower() or "distinct plain lyric" in feedback.lower()

    def test_weighted_split_gives_drops_more_lines_than_intro(self):
        structure = [
            "[Intro: dark pads]",
            "[Build-Up: risers]",
            "[Drop: 808]",
            "[Break: rain]",
            "[Drop: heavy]",
            "[Outro: fade]",
        ]
        freeform = "\n".join(f"Line {i}" for i in range(24))
        assigned = assign_draft_lyrics_to_structure(freeform, structure)
        assert validate_lyrics_structure(assigned, structure)
        intro_lines = _count_assigned_section_lines(assigned, "[Intro]")
        drop_lines = _count_assigned_section_lines(assigned, "[Drop]")
        break_lines = _count_assigned_section_lines(assigned, "[Break]")
        assert drop_lines > intro_lines
        assert drop_lines > break_lines

    def test_distribute_lines_by_section_weight_respects_weights(self):
        buckets = distribute_lines_by_section_weight(
            [f"line-{i}" for i in range(20)],
            [1.0, 1.5, 3.0, 1.0],
        )
        assert sum(len(bucket) for bucket in buckets) == 20
        assert len(buckets[2]) > len(buckets[0])


def _count_assigned_section_lines(assigned: str, header: str) -> int:
    lines = [line.strip() for line in assigned.splitlines() if line.strip()]
    current: str | None = None
    total = 0
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            current = line
            continue
        if current == header:
            total += 1
    return total


class TestTwoStepLyricPrompts:
    def test_lyric_shape_prompt_references_draft_only(self):
        from platform_api.services.generation_service import (
            build_lyric_shape_user_prompt,
            parse_plain_lyric_text,
        )

        draft = "\n".join(f"Draft line {i}" for i in range(18))
        prompt = build_lyric_shape_user_prompt(
            draft_lyrics=draft,
            structure_guide="[Verse]: gritty\n[Chorus]: hook",
            structure_headers=["[Verse]", "[Chorus]"],
            forced_opening="Opening one",
        )
        assert draft in prompt
        assert "use only these lines" in prompt.lower()
        assert "[Verse]" in prompt

    def test_lyric_rewrite_prompt_uses_mood_not_description(self):
        from platform_api.services.generation_service import (
            build_lyric_rewrite_system_prompt,
            build_lyric_rewrite_user_prompt,
            lyric_rewrite_temperature,
            prepare_lyrics_for_rewrite,
            describe_lyric_rewrite_quality_failure,
        )

        user_prompt = build_lyric_rewrite_user_prompt(
            lyrics="[Verse]\nHello night drive neon",
            mood="Soft ache and quiet hope",
            title="Paper Lanterns",
            structure="[Verse]\n[Chorus]",
            description="Aggressive EDM festival banger with chrome synths",
        )
        assert "Soft ache and quiet hope" in user_prompt
        assert "Paper Lanterns" in user_prompt
        assert "[Verse]\n[Chorus]" in user_prompt
        assert "Aggressive EDM" not in user_prompt
        assert "Song theme / description" not in user_prompt
        assert "chrome synths" not in user_prompt

        system_prompt = build_lyric_rewrite_system_prompt(strength=80)
        assert "word salad" in system_prompt.lower()
        assert lyric_rewrite_temperature(100) <= 0.9
        assert lyric_rewrite_temperature(0) >= 0.35

        poisoned = (
            "[Intro]\nWe chase the glowing signals before the light.\n"
            "If this is the rush, why does it cut so deep?\n\n"
            "[Drop]\nPhantom navigators count the hours with quiet care.\n\n"
            "[Bridge]\nMortal breath, softly held, glowing future late keypad stock, cry rolls "
            "number alert, fluid curtains, sunlight trends against the freak performing fire optic, "
            "keywords without striped consumption, arrive homeowner evenly.\n\n"
            "[Outro]\nsanitize value forbidden kitty JSONObject githubusercontent 汉字 العربية"
        )
        trimmed = prepare_lyrics_for_rewrite(poisoned)
        assert "glowing signals" in trimmed
        assert "keypad stock" not in trimmed
        assert "sanitize value" not in trimmed
        assert describe_lyric_rewrite_quality_failure(poisoned) is not None
        assert describe_lyric_rewrite_quality_failure(trimmed) is None

    def test_parse_plain_lyric_text_strips_json_wrapper(self):
        from platform_api.services.generation_service import parse_plain_lyric_text

        raw = '{"lyrics": "Line one\\nLine two"}'
        parsed = parse_plain_lyric_text(raw)
        assert "Line one" in parsed
        assert "Line two" in parsed


class TestAiStructureLyrics:
    """Tests for AI Structure mode lyric normalization and validation."""

    def test_normalize_wraps_plain_text_as_single_verse(self):
        from platform_api.services.generation_service import normalize_ai_structure_lyrics

        plain = "\n".join(f"Line {index}" for index in range(18))
        normalized = normalize_ai_structure_lyrics(plain)
        assert normalized.startswith("[Verse]\n")
        assert "Line 17" in normalized

    def test_validate_ai_structure_with_headers(self):
        from platform_api.services.generation_service import validate_ai_structure_lyrics

        lines = ["[Intro]", "Warm start"]
        lines += ["[Verse]"] + [f"Verse line {index}" for index in range(8)]
        lines += ["[Chorus]"] + [f"Hook line {index}" for index in range(8)]
        assert validate_ai_structure_lyrics("\n".join(lines)) is True

    def test_validate_ai_structure_rejects_short_plain_text(self):
        from platform_api.services.generation_service import (
            describe_ai_structure_validation_failure,
        )

        plain = "\n".join(f"Line {index}" for index in range(8))
        failure = describe_ai_structure_validation_failure(plain)
        assert failure is not None

    def test_analyze_ai_structure_response(self):
        from platform_api.services.generation_service import analyze_ai_structure_lyric_response

        raw = "Here are the lyrics:\n[Verse]\nOne\n[Chorus]\nTwo\n" + "\n".join(
            f"Line {index}" for index in range(16)
        )
        analysis = analyze_ai_structure_lyric_response(raw)
        assert analysis["has_headers"] is True
        assert analysis["header_count"] >= 2
        assert analysis["has_preamble"] is True


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

    def test_production_structure_accepts_short_lyric_headers(self):
        structure_headers = [
            "[Intro: dark atmospheric synth pads]",
            "[Build-Up: filtered cowbells]",
            "[Drop: distorted 808 bass]",
            "[Outro: fading atmospheric pads]",
        ]
        lyrics = make_valid_lyrics(
            ["[Intro]", "[Build-Up]", "[Drop]", "[Outro]"],
            content_per_section=5,
        )
        assert validate_lyrics_structure(lyrics, structure_headers) is True

    def test_production_structure_rejects_wrong_section_order(self):
        structure_headers = [
            "[Intro: pads]",
            "[Drop: bass]",
        ]
        lyrics = "[Drop]\nline one\nline two\nline three\nline four\nline five\nline six\nline seven\nline eight\n"
        lyrics += "[Intro]\nline one\nline two\nline three\nline four\nline five\nline six\nline seven\nline eight\n"
        assert validate_lyrics_structure(lyrics, structure_headers) is False

    def test_minimum_lines_scales_for_many_sections(self):
        assert minimum_lyric_content_lines(9) == 18
        assert minimum_lyric_content_lines(4) == 16


class TestDescribeStructureValidationFailure:
    def test_returns_none_for_valid_lyrics(self):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        assert describe_structure_validation_failure(lyrics, headers) is None

    def test_reports_missing_lines(self):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = "\n".join(
            f"{h}\n" + "\n".join(f"Line {j}" for j in range(3))
            for h in headers
        )
        reason = describe_structure_validation_failure(lyrics, headers)
        assert reason is not None
        assert "Not enough lyric lines" in reason

    def test_reports_wrong_first_line(self):
        reason = describe_structure_validation_failure(
            "Opening line\n[Verse]\n" + "\n".join(f"Line {i}" for i in range(20)),
            ["[Verse]"],
        )
        assert reason is not None
        assert "first line" in reason.lower()

    def test_retry_feedback_includes_headers(self):
        feedback = build_structure_retry_feedback(
            "Section header mismatch: section 1 expected [Intro], got [Verse].",
            ["[Intro: pads]", "[Drop: bass]"],
        )
        assert "CORRECTION REQUIRED" in feedback
        assert "[Intro]" in feedback
        assert "[Drop]" in feedback


class TestDraftAttemptTemperature:
    def test_lowers_temperature_on_retry(self):
        assert draft_attempt_temperature(1.2, 1) == 1.2
        assert draft_attempt_temperature(1.2, 2) == pytest.approx(0.84)
        assert draft_attempt_temperature(0.4, 3) == 0.35


class TestPoolRephrasePrompts:
    def test_title_prompt_uses_seed_and_avoid_list(self):
        system, user = build_title_slot_prompts(
            user_context="Description:\nEDM track",
            title_seed="Midnight Drive",
            avoid_titles=["Used Title"],
        )
        assert "Rephrase" in system
        assert 'Seed title: "Midnight Drive"' in user
        assert "Avoid these titles: Used Title" in user

    def test_album_prompt_uses_seed(self):
        system, user = build_album_slot_prompts(
            user_context="Description:\nEDM track",
            album_seed="Night Circuit",
        )
        assert "Rephrase" in system
        assert 'Seed album: "Night Circuit"' in user

    def test_lyrics_opening_block_requires_expansion(self):
        block = build_lyrics_opening_block("Line one\nLine two")
        assert "Required opening lines" in block
        assert "Line one" in block


class TestStructureConstraintsBlock:
    def test_includes_minimum_line_count(self):
        block = build_structure_constraints_block(["[Verse]", "[Chorus]"])
        assert "at least 16 non-header lyric lines" in block
        assert "[Verse]" in block
        assert "[Chorus]" in block


class TestNormalizeDraftLyrics:
    def test_strip_preamble_before_first_header(self):
        raw = "Here are the lyrics:\n[Intro]\nline one\nline two\n"
        assert strip_lyrics_preamble(raw).startswith("[Intro]")

    def test_normalize_accepts_preamble_prefixed_lyrics(self):
        headers = ["[Intro]", "[Verse]", "[Chorus]", "[Outro]"]
        raw = "Sure! Here you go:\n" + make_valid_lyrics(
            ["[Intro]", "[Verse]", "[Chorus]", "[Outro]"],
            content_per_section=5,
        )
        cleaned = normalize_draft_lyrics(raw, headers)
        assert validate_lyrics_structure(cleaned, headers) is True


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
        text_gateway = FakeTextGateway(
            titles=["My Song"],
            albums=["My Album"],
            lyrics=lyrics,
        )

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
        )

        request = DraftRequest(
            language="en",
            creativity_level=50,
            description="A pop song",
            structure="\n".join(headers),
        )
        result = await service.submit_draft(
            "user-123",
            request,
            provider="deepseek",
            model="deepseek-chat",
        )

        assert result.title == "My Song"
        assert result.album == "My Album"
        assert len(credit_service.deductions) == 1
        assert credit_service.deductions[0][1] == 4
        assert len(credit_service.refunds) == 0

    @pytest.mark.asyncio
    async def test_insufficient_credits_raises(self, pricing_repo, task_repo):
        credit_service = FakeCreditService(balance=0)
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="[Verse]",
        )
        with pytest.raises(InsufficientCreditsError):
            await service.submit_draft(
                "user-123",
                request,
                provider="deepseek",
                model="deepseek-chat",
            )

    @pytest.mark.asyncio
    async def test_unparseable_response_retries(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        text_gateway = FakeTextGateway(
            titles=["Good Title"],
            albums=["Good Album"],
            lyrics=lyrics,
            bad_lyrics_responses=["not json"],
        )

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="\n".join(headers),
        )
        result = await service.submit_draft(
            "user-123",
            request,
            provider="deepseek",
            model="deepseek-chat",
        )
        assert result.title == "Good Title"

    @pytest.mark.asyncio
    async def test_all_attempts_exhausted_refunds(self, credit_service, pricing_repo, task_repo):
        class LyricsFailingGateway(FakeTextGateway):
            async def generate_text(self, *, system_prompt: str, user_prompt: str, **_: Any) -> str:
                system_lower = system_prompt.lower()
                if "lyric structure editor" in system_lower or (
                    "plain lyric lines only" in system_lower
                    or (
                        "professional songwriter" in system_lower
                        and "structure editor" not in system_lower
                    )
                ):
                    raise ExternalServiceError("Lyric provider unavailable", is_retryable=False)
                return await super().generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

        text_gateway = LyricsFailingGateway(
            titles=["Good Title"],
            albums=["Good Album"],
        )

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="[Verse]",
        )
        with pytest.raises(ExternalServiceError):
            await service.submit_draft(
                "user-123",
                request,
                provider="deepseek",
                model="deepseek-chat",
            )

        assert len(credit_service.refunds) == 1

    @pytest.mark.asyncio
    async def test_reshapes_invalid_lyrics_without_extra_title_calls(
        self, credit_service, pricing_repo, task_repo
    ):
        text_gateway = FakeTextGateway(
            titles=["Stable Title"],
            albums=["Stable Album"],
            invalid_lyrics="[Wrong Header]\n" + "\n".join(f"line {i}" for i in range(20)),
        )
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
        )
        request = DraftRequest(
            language="en",
            creativity_level=50,
            description="A pop song",
            structure="[Verse]",
        )
        result = await service.submit_draft(
            "user-123",
            request,
            provider="deepseek",
            model="deepseek-chat",
        )
        assert result.title == "Stable Title"
        assert result.album == "Stable Album"
        assert text_gateway._title_idx == 1
        assert text_gateway._album_idx == 1
        assert text_gateway._lyrics_idx == 2

    @pytest.mark.asyncio
    async def test_forced_title_bypasses_llm(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        text_gateway = FakeTextGateway(
            titles=["LLM Title"],
            albums=["LLM Album"],
            lyrics=lyrics,
        )

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="\n".join(headers),
            forced_title="My Forced Title",
        )
        result = await service.submit_draft(
            "user-123",
            request,
            provider="deepseek",
            model="deepseek-chat",
        )
        assert result.title == "My Forced Title"
        assert result.album == "LLM Album"
        assert credit_service.deductions[0][1] == 3

    @pytest.mark.asyncio
    async def test_avoid_list_triggers_retry(self, credit_service, pricing_repo, task_repo):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        lyrics = make_valid_lyrics(headers, content_per_section=5)
        text_gateway = FakeTextGateway(
            titles=["Avoided Title", "Unique Title"],
            albums=["Good Album"],
            lyrics=lyrics,
        )

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
        )
        request = DraftRequest(
            language="en", creativity_level=50,
            description="A pop song", structure="\n".join(headers),
            avoid_titles=["Avoided Title"],
        )
        result = await service.submit_draft(
            "user-123",
            request,
            provider="deepseek",
            model="deepseek-chat",
        )
        assert result.title == "Unique Title"

    @pytest.mark.asyncio
    async def test_suno_lyric_routing_uses_suno_client(
        self, credit_service, pricing_repo, task_repo
    ):
        headers = ["[Verse]", "[Chorus]", "[Bridge]", "[Outro]"]
        suno_lyrics = make_valid_lyrics(headers, content_per_section=5)
        text_gateway = FakeTextGateway(
            titles=["My Song"],
            albums=["My Album"],
        )
        suno_client = FakeSunoClient(lyrics_text=suno_lyrics)
        pricing_repo._prices[("suno", "lyric")] = 3

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            text_gateway=text_gateway,
            suno_client=suno_client,
        )
        request = DraftRequest(
            language="en",
            creativity_level=50,
            description="Dark phonk trap",
            structure="\n".join(headers),
        )
        routing = DraftRouting(
            title=TextRouting(provider="deepseek", sub_model="deepseek-chat"),
            album=TextRouting(provider="deepseek", sub_model="deepseek-chat"),
            lyric=TextRouting(provider="suno", sub_model="lyrics"),
        )
        result = await service.submit_draft(
            "user-123",
            request,
            provider="deepseek",
            model="deepseek-chat",
            draft_routing=routing,
        )

        assert result.title == "My Song"
        assert result.album == "My Album"
        assert "[Verse]" in result.lyrics
        assert text_gateway._lyrics_idx == 0


# ---------------------------------------------------------------------------
# Tests: submit_suno
# ---------------------------------------------------------------------------


class TestSubmitSuno:
    """Tests for GenerationService.submit_suno."""

    @pytest.fixture(autouse=True)
    def _stub_suno_blocklist(self):
        from platform_api.services.suno_lyrics_sanitize import SunoRuntimeBlocklist

        blocklist = AsyncMock()
        blocklist.get_runtime_config = AsyncMock(return_value=SunoRuntimeBlocklist())
        with patch(
            "platform_api.dependencies.get_suno_blocklist_service",
            return_value=blocklist,
        ):
            yield

    @pytest.mark.asyncio
    async def test_successful_submission(self, credit_service, pricing_repo, task_repo):
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(task_id="ext-task-456"),
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
    async def test_failed_task_is_not_treated_as_duplicate(
        self, credit_service, pricing_repo, task_repo
    ):
        """A *failed* task must not be returned as a duplicate (issue #372).

        Re-running a song whose only task failed has to create a fresh task and
        charge normally, instead of returning the dead task (which used to leave
        the caller charged with no regeneration).
        """
        user_uuid = UUID("00000000-0000-0000-0000-000000000000")
        user_id = str(user_uuid)
        request = SunoRequest(model="V5", title="Song", lyrics="La la la", style="Pop")
        request_hash = compute_suno_request_hash("V5", "Song", "La la la", "Pop", False)

        existing = SunoTask(
            id=uuid4(),
            user_id=user_uuid,
            request_hash=request_hash,
            model="V5",
            title="Song",
            status=TaskStatus.FAILED,
        )
        task_repo.tasks.append(existing)

        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(task_id="ext-task-retry"),
        )

        result = await service.submit_suno(user_id, request)

        assert result != str(existing.id)  # not the dead task
        assert len(task_repo.tasks) == 2  # a fresh task was created
        assert len(credit_service.deductions) == 1  # the (legit) charge happened

    @pytest.mark.asyncio
    async def test_v5_5_uses_model_specific_pricing(self, credit_service, task_repo):
        pricing_repo = FakePricingRepo(
            prices={
                ("suno", "music", "V5_5"): 16,
            }
        )
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(task_id="ext-task-v55"),
        )
        request = SunoRequest(model="V5_5", title="Song", lyrics="La la la", style="Pop")
        user_id = str(uuid4())
        task_id = await service.submit_suno(user_id, request)

        assert task_id
        assert len(credit_service.deductions) == 1
        assert credit_service.deductions[0][1] == 16

    @pytest.mark.asyncio
    async def test_suno_failure_refunds_credits(self, credit_service, pricing_repo, task_repo):
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            suno_client=FakeSunoClient(should_fail=True),
        )
        request = SunoRequest(model="V5", title="Song", lyrics="La la la", style="Pop")
        user_id = str(uuid4())

        with pytest.raises(ExternalServiceError):
            await service.submit_suno(user_id, request)

        # Credits deducted then refunded
        assert len(credit_service.deductions) == 1
        assert len(credit_service.refunds) == 1

    @pytest.mark.asyncio
    async def test_web_music_blocklist_rejects_before_suno(
        self, credit_service, pricing_repo, task_repo
    ):
        from platform_api.services.suno_lyrics_sanitize import SunoRuntimeBlocklist

        suno = FakeSunoClient(task_id="should-not-run")
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            suno_client=suno,
        )
        runtime = SunoRuntimeBlocklist(
            replacements={"lowlight": "afterglow"},
            block_terms=frozenset({"lowlight"}),
        )
        blocklist = AsyncMock()
        blocklist.get_runtime_config = AsyncMock(return_value=runtime)
        request = SunoRequest(
            model="V5",
            title="Night Song",
            lyrics="Pressure in the bleeding lowlight",
            style="Pop",
        )
        with patch(
            "platform_api.dependencies.get_suno_blocklist_service",
            return_value=blocklist,
        ):
            with pytest.raises(ValidationError, match="Suno-blocked"):
                await service.submit_suno(
                    str(uuid4()),
                    request,
                    skip_pricing=True,
                    source="web_music",
                )
        assert task_repo.tasks == []
        assert credit_service.deductions == []


# ---------------------------------------------------------------------------
# Tests: submit_image
# ---------------------------------------------------------------------------


class TestSubmitImage:
    """Tests for GenerationService.submit_image."""

    @pytest.mark.asyncio
    async def test_successful_fal_image(self, credit_service, pricing_repo, task_repo):
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            fal_client=FakeFalClient(),
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
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
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
    async def test_successful_slai_image_url_payload(self, credit_service, pricing_repo, task_repo):
        service = _make_service(
            credit_service=credit_service,
            pricing_repo=pricing_repo,
            task_repo=task_repo,
            llm_client=FakeLlmClient(),
            slai_client=FakeSlaiUrlClient(),
        )
        service.extract_image_bytes_async = AsyncMock(return_value=b"fake-downloaded-png")
        request = ImageRequest(
            prompt="A bold gym music logo",
            provider="slai",
            resolution="1024x1024",
            style_strength=0.5,
        )

        result = await service.submit_image("user-123", request)

        assert result == b"fake-downloaded-png"
        service.extract_image_bytes_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_channel_cover_resolution_1920x1080_is_allowed(
        self, credit_service, pricing_repo, task_repo
    ):
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
            prompt="A cinematic channel banner",
            provider="fal",
            resolution="1920x1080",
            style_strength=0.5,
        )
        service._generate_fal_image = AsyncMock(return_value=b"fake-banner-bytes")
        result = await service.submit_image("user-123", request, skip_pricing=True)
        assert result == b"fake-banner-bytes"
        assert len(credit_service.deductions) == 0

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
            prompt="x" * 5001, provider="fal",
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


def test_parse_llm_json_content_strips_markdown_fence() -> None:
    content = '```json\n{"title":"T","album":"A","lyrics":"[Verse]\\nline"}\n```'
    parsed = GenerationService._parse_llm_json_content(content)
    assert parsed is not None
    assert parsed["title"] == "T"
    assert parsed["album"] == "A"


def test_parse_llm_response_accepts_fenced_json() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"title":"T","album":"A","lyrics":"[Verse]\\nline one"}\n```'
                }
            }
        ]
    }
    parsed = GenerationService._parse_llm_response(response)
    assert parsed == {"title": "T", "album": "A", "lyrics": "[Verse]\nline one"}
