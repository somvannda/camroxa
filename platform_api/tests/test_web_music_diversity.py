"""Batch diversity helpers: shared prompts must not produce identical songs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.services.content_pool_service import ClaimedPoolItem
from platform_api.services.web_music_service import (
    _WEB_LYRICS_PROMPT_MAX,
    _sanitize_song_plan,
    WebMusicService,
    build_web_simple_lyrics_prompt,
    ensure_lyrics_opening,
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


@pytest.mark.asyncio
async def test_simple_generation_uses_theme_and_pool_seeds(
    mute_blocklist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One shared description + a per-song theme must not yield one song twice."""
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.generate_suno_lyrics = AsyncMock(
        return_value=("[Verse]\ncity lights", "Same Title As Yesterday")
    )
    service = WebMusicService(MagicMock(), generation)
    service._is_paid_queue_user = AsyncMock(return_value=True)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._reserve_daily_slot = AsyncMock(
        return_value={"limit": 1000, "used": 0, "remaining": 100, "is_pro": True}
    )
    service._enqueue_web_generate = AsyncMock(return_value=task_id)
    service._link_generation_debit_reference = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=uuid4())
    service._with_queue_fields = AsyncMock(side_effect=lambda _uid, quota: quota)
    service._recent_web_titles = AsyncMock(return_value=["Midnight Pulse"])

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

    payload = await service.generate(
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

    lyrics_prompt = generation.generate_suno_lyrics.await_args.args[0]
    assert "rooftop sunrise" in lyrics_prompt
    assert len(lyrics_prompt) <= _WEB_LYRICS_PROMPT_MAX
    # The pool title wins over the generator's repeated title.
    assert payload["title"] == "Teal Horizon"
    assert "Midnight Pulse" in lyrics_prompt  # avoid list reached the prompt
    enqueued = service._enqueue_web_generate.await_args.kwargs
    assert "Streetlights hum" in enqueued["lyrics"]
    assert finalize.await_count == 2
