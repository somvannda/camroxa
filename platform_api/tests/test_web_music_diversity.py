"""Batch diversity helpers: shared prompts must not produce identical songs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.services.content_pool_service import ClaimedPoolItem
from platform_api.exceptions import ExternalServiceError
from platform_api.services.web_music_service import (
    _WEB_LYRICS_PROMPT_MAX,
    _sanitize_song_plan,
    WebMusicService,
    build_web_simple_lyrics_prompt,
    ensure_lyrics_opening,
    lyrics_failure_user_message,
)


class TestSimpleLyricsPrompt:
    def test_keeps_prompt_under_suno_limit(self) -> None:
        prompt = "moody synthwave " * 80
        text = build_web_simple_lyrics_prompt(
            prompt=prompt,
            theme="a late-night drive through a flooded city",
            forced_opening="Streetlights hum like static",
            structure_hint="Chorus, Verse, Chorus, Bridge, Chorus",
            avoid_titles=["Midnight Pulse", "Neon Heartline"],
        )
        assert len(text) <= _WEB_LYRICS_PROMPT_MAX
        # The distinguishing parts survive the truncation.
        assert "flooded city" in text
        assert "Streetlights hum" in text
        assert "Midnight Pulse" in text

    def test_same_prompt_different_theme_differs(self) -> None:
        prompt = "warm analog synth pop, 118 BPM, female vocal"
        first = build_web_simple_lyrics_prompt(
            prompt=prompt,
            theme="a bus ride after a breakup",
            forced_opening="Rain on the window",
        )
        second = build_web_simple_lyrics_prompt(
            prompt=prompt,
            theme="a rooftop party at sunrise",
            forced_opening="The city hums awake",
        )
        assert first != second

    def test_prompt_only_still_builds_text(self) -> None:
        assert build_web_simple_lyrics_prompt(prompt="dreamy lofi") != ""


class TestEnsuredOpening:
    def test_inserted_within_first_lines(self) -> None:
        lyrics = "[Verse]\nCity lights"
        out = ensure_lyrics_opening(lyrics, "Streetlights hum")
        assert "Streetlights hum" in out.splitlines()[:2]

    def test_keeps_existing_duplicate(self) -> None:
        lyrics = "[Verse]\nStreetlights hum like static\nCity lights"
        assert ensure_lyrics_opening(lyrics, "Streetlights hum like static") == lyrics

    def test_inserts_after_section_header(self) -> None:
        out = ensure_lyrics_opening("[Verse]\nCity lights", "Streetlights hum")
        assert out.splitlines()[0] == "[Verse]"
        assert out.splitlines()[1] == "Streetlights hum"


class TestSongPlanSanitize:
    def test_returns_exact_count_with_unique_titles(self) -> None:
        raw = """
        [
          {"title": "Midnight Pulse", "theme": "neon streets", "structure": "Chorus, Verse"},
          {"title": "Midnight Pulse", "theme": "rain at dusk", "structure": "Verse, Chorus"},
          {"title": "Neon Heartline", "theme": "an empty arcade", "structure": "Chorus, Verse"}
        ]
        """
        ideas = _sanitize_song_plan(raw, prompt="synth pop", count=3)
        assert len(ideas) == 3
        titles = [idea["title"].lower() for idea in ideas]
        assert len(set(titles)) == 3
        assert all(idea["theme"] for idea in ideas)

    def test_falls_back_when_llm_returns_garbage(self) -> None:
        ideas = _sanitize_song_plan("not json at all", prompt="sunset disco", count=4)
        assert len(ideas) == 4
        assert len({idea["title"] for idea in ideas}) == 4
        assert all(idea["title"] for idea in ideas)

    def test_avoids_recent_listener_titles(self) -> None:
        raw = '[{"title": "Midnight Pulse", "theme": "a"}, {"title": "Fresh Start", "theme": "b"}]'
        ideas = _sanitize_song_plan(
            raw,
            prompt="disco",
            count=2,
            avoid_titles=["Midnight Pulse"],
        )
        assert ideas[0]["title"].lower() != "midnight pulse"
        assert ideas[1]["title"] == "Fresh Start"


@pytest.fixture
def mute_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    service.get_runtime_config = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: service,
    )


def _pool_seeds(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Claim a pool title/opening line instead of whatever the LLM returns."""

    async def fake_claim(**kwargs):
        text = "Teal Horizon" if kwargs["kind"] == "titles" else "Streetlights hum"
        return ClaimedPoolItem(
            kind=kwargs["kind"],
            item_id=1,
            text=text,
            secondary_text=None,
            reservation_token=kwargs["reservation_token"],
        )

    finalize = AsyncMock()
    monkeypatch.setattr(
        "platform_api.services.web_music_service.claim_pool_item", fake_claim
    )
    monkeypatch.setattr(
        "platform_api.services.web_music_service.finalize_pool_item", finalize
    )
    return finalize


def _queued_row(task_id) -> dict[str, object]:
    return {
        "id": task_id,
        "title": "Untitled",
        "lyrics": "",
        "style": "Contemporary pop",
        "model": "V6_MINI",
        "instrumental": False,
        "external_task_id": None,
        "negative_tags": None,
        "vocal_gender": None,
        "style_weight": 0.5,
        "weirdness_constraint": 0.5,
        "audio_weight": 0.5,
        "reference_image_urls": [],
        "reference_video_urls": [],
        "persona_id": None,
        "status": "pending",
    }


@pytest.mark.asyncio
async def test_simple_generation_queues_without_waiting_for_lyrics(
    mute_blocklist: None,
) -> None:
    """Suno's lyrics task must not run inside the POST.

    It polls for up to two minutes, which put the edge proxy's 100s response
    limit (HTTP 524) in the middle of every batch: the first song landed and
    the rest died.
    """
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock()
    service = WebMusicService(AsyncMock(), generation)
    service._is_paid_queue_user = AsyncMock(return_value=True)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._reserve_daily_slot = AsyncMock(
        return_value={"limit": 1000, "used": 0, "remaining": 100, "is_pro": True}
    )
    service._enqueue_web_generate = AsyncMock(return_value=task_id)
    service._link_generation_debit_reference = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=uuid4())
    service._with_queue_fields = AsyncMock(side_effect=lambda _uid, quota: quota)

    await service.generate(
        user_id,
        mode="simple",
        lyrics="",
        style="",
        title="",
        instrumental=False,
        model="V6_MINI",
        prompt="moody synthwave, warm bass, female vocal",
        theme="a rooftop sunrise after the party",
    )

    generation.generate_suno_lyrics.assert_not_awaited()
    enqueued = service._enqueue_web_generate.await_args.kwargs
    assert enqueued["lyrics"] == ""
    assert enqueued["lyrics_brief"] == {
        "prompt": "moody synthwave, warm bass, female vocal",
        "theme": "a rooftop sunrise after the party",
        "structure": "",
        "title": "",
    }


@pytest.mark.asyncio
async def test_worker_writes_simple_lyrics_before_submitting(
    mute_blocklist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One shared description + a per-song theme must not yield one song twice."""
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock(
        return_value=("[Verse]\ncity lights", "Same Title As Yesterday")
    )
    service = WebMusicService(AsyncMock(), generation)
    service._pool.fetchrow = AsyncMock(return_value=_queued_row(task_id))
    service._recent_web_titles = AsyncMock(return_value=["Midnight Pulse"])
    finalize = _pool_seeds(monkeypatch)

    await service.write_queued_lyrics(
        user_id,
        task_id,
        reservation_id="res-1",
        brief={
            "prompt": "moody synthwave, warm bass, female vocal",
            "theme": "a rooftop sunrise after the party",
            "structure": "",
            "title": "",
        },
    )

    lyrics_prompt = generation.generate_suno_lyrics.await_args.args[0]
    assert "rooftop sunrise" in lyrics_prompt
    assert "Midnight Pulse" in lyrics_prompt  # avoid list reached the prompt
    assert len(lyrics_prompt) <= _WEB_LYRICS_PROMPT_MAX

    writes = [
        call.args
        for call in service._pool.execute.await_args_list
        if "SET title = $3, lyrics = $4" in str(call.args[0])
    ]
    assert writes, "the written lyrics were never persisted"
    # The pool title wins over the generator's repeated title, and the pool
    # opening line opens the generated lyrics.
    assert writes[0][3] == "Teal Horizon"
    assert "Streetlights hum" in writes[0][4]
    assert finalize.await_count == 2


@pytest.mark.asyncio
async def test_lyrics_failure_refunds_the_queued_song(
    mute_blocklist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed lyrics task must refund, not leave the song charged forever."""
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock(side_effect=RuntimeError("suno lyrics down"))
    service = WebMusicService(AsyncMock(), generation)
    service._pool.fetchrow = AsyncMock(return_value=_queued_row(task_id))
    service._recent_web_titles = AsyncMock(return_value=[])
    service._release_daily_slot = AsyncMock()
    _pool_seeds(monkeypatch)

    with pytest.raises(RuntimeError, match="suno lyrics down"):
        await service.write_queued_lyrics(
            user_id,
            task_id,
            reservation_id="res-1",
            brief={"prompt": "dreamy lofi", "theme": "", "structure": "", "title": ""},
        )

    service._release_daily_slot.assert_awaited()
    assert service._release_daily_slot.await_args.kwargs["reference_id"] == "res-1"


@pytest.mark.asyncio
async def test_refunded_song_is_not_resurrected(
    mute_blocklist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retried job must not deliver a song an earlier attempt refunded."""
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock()
    generation.submit_suno_external_id = AsyncMock(return_value="ext-1")
    service = WebMusicService(AsyncMock(), generation)
    refunded = _queued_row(task_id)
    refunded["status"] = "failed"
    service._pool.fetchrow = AsyncMock(return_value=refunded)
    _pool_seeds(monkeypatch)

    await service.write_queued_lyrics(
        user_id,
        task_id,
        reservation_id="res-1",
        brief={"prompt": "dreamy lofi", "theme": "", "structure": "", "title": ""},
    )
    await service.fulfill_queued_generate(user_id, task_id, reservation_id="res-1")

    generation.generate_suno_lyrics.assert_not_awaited()
    generation.submit_suno_external_id.assert_not_awaited()


class TestLyricsRefusalMessage:
    """The listener must learn *why* Suno would not write the song."""

    def test_producer_tag_refusal_is_actionable(self) -> None:
        message = lyrics_failure_user_message(
            "Suno failed (GENERATE_LYRICS_FAILED): Your prompt contains producer tag "
            "lowlight - we don't reference specific artists on Suno, please change "
            "your prompt and try again."
        )
        assert "artist or producer reference" in message
        assert "Credits were refunded" in message
        assert "Suno failed (" not in message

    def test_provider_detail_is_kept(self) -> None:
        message = lyrics_failure_user_message("Suno lyrics timed out after 45s.")
        assert "Suno lyrics timed out after 45s." in message
        assert message.endswith("Credits were refunded.")

    def test_empty_reason_falls_back(self) -> None:
        assert lyrics_failure_user_message("") == (
            "This song could not be written. Credits were refunded."
        )


def _refusal() -> ExternalServiceError:
    return ExternalServiceError(
        "Suno failed (GENERATE_LYRICS_FAILED): Your prompt contains producer tag "
        "lowlight - we don't reference specific artists on Suno, please change your "
        "prompt and try again.",
        is_retryable=False,
    )


@pytest.mark.asyncio
async def test_rejected_pool_opening_is_dropped_and_retried(
    mute_blocklist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Suno's artist filter can read the pooled opening line as a producer tag.

    The line is decorative, so drop it and write the lyrics again instead of
    failing a song the listener already paid for (production saw 4 of 5 songs
    die on "low-light" being read as the producer tag "lowlight").
    """
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock(
        side_effect=[_refusal(), ("[Verse]\nclean night", "Clean Night")]
    )
    service = WebMusicService(AsyncMock(), generation)
    service._pool.fetchrow = AsyncMock(return_value=_queued_row(task_id))
    service._pool.execute = AsyncMock()
    service._recent_web_titles = AsyncMock(return_value=[])
    released = AsyncMock()
    monkeypatch.setattr(
        "platform_api.services.web_music_service.release_claimed_items", released
    )
    _pool_seeds(monkeypatch)

    await service.write_queued_lyrics(
        user_id,
        task_id,
        reservation_id="res-1",
        brief={"prompt": "moody synthwave", "theme": "", "structure": "", "title": ""},
    )

    assert generation.generate_suno_lyrics.await_count == 2
    first_prompt = generation.generate_suno_lyrics.await_args_list[0].args[0]
    second_prompt = generation.generate_suno_lyrics.await_args_list[1].args[0]
    assert "Streetlights hum" in first_prompt
    assert "Streetlights hum" not in second_prompt
    released.assert_awaited()  # the rejected seed goes back to the pool

    writes = [
        call.args
        for call in service._pool.execute.await_args_list
        if "SET title = $3, lyrics = $4" in str(call.args[0])
    ]
    assert writes, "the retried lyrics were never persisted"
    assert writes[0][4].startswith("[Verse]")


@pytest.mark.asyncio
async def test_refusal_reason_is_stored_on_the_song(
    mute_blocklist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal that survives the retry must be readable in the library."""
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock(side_effect=_refusal())
    service = WebMusicService(AsyncMock(), generation)
    service._pool.fetchrow = AsyncMock(return_value=_queued_row(task_id))
    service._pool.execute = AsyncMock()
    service._recent_web_titles = AsyncMock(return_value=[])
    service._release_daily_slot = AsyncMock()
    _pool_seeds(monkeypatch)

    with pytest.raises(ExternalServiceError):
        await service.write_queued_lyrics(
            user_id,
            task_id,
            reservation_id="res-1",
            brief={"prompt": "moody synthwave", "theme": "", "structure": "", "title": ""},
        )

    failed = [
        call.args
        for call in service._pool.execute.await_args_list
        if "SET status = $3, error_message = $4" in str(call.args[0])
    ]
    assert failed, "the refused song was never marked failed"
    assert "artist or producer reference" in failed[0][4]
    service._release_daily_slot.assert_awaited()
