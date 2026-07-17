"""Tests for shared LLM response parsing."""

from __future__ import annotations

from platform_api.ai.parsing.response_parser import parse_json_object, parse_string_list
from platform_api.ai.purposes.channel_text import (
    parse_description_text,
    parse_keywords,
    parse_tags,
    parse_title_album_lyrics,
)
from platform_api.ai.registry import (
    resolve_fal_api_model_id,
    resolve_text_model_id,
    resolve_text_request_timeout,
)
from platform_api.ai.purposes.draft_routing import build_draft_routing
from platform_api.ai.models import TextRouting


def test_parse_json_object_strips_markdown_fence() -> None:
    content = '```json\n{"title":"T","album":"A","lyrics":"[Verse]\\nline"}\n```'
    parsed = parse_json_object(content)
    assert parsed is not None
    assert parsed["title"] == "T"


def test_parse_title_album_lyrics() -> None:
    parsed = parse_title_album_lyrics(
        '{"title":"Song","album":"Album","lyrics":"[Verse]\\nHello"}'
    )
    assert parsed == {
        "title": "Song",
        "album": "Album",
        "lyrics": "[Verse]\nHello",
    }


def test_parse_string_list_from_array() -> None:
    assert parse_string_list('["Alpha", "Beta"]') == ["Alpha", "Beta"]


def test_parse_keywords_and_tags() -> None:
    assert parse_keywords('{"keywords":["edm","workout music"]}') == ["edm", "workout music"]
    assert parse_tags('{"tags":["gym mix"]}') == ["gym mix"]


def test_parse_keywords_filters_broken_fragments() -> None:
    raw = (
        '{"keywords":["Bass Drive","EDM workout music","gym motivatio","high e","ergy workout playlist",'
        '"fit","ess beats","electro","ic da","ce music for exercise"]}'
    )
    keywords = parse_keywords(raw)
    assert "fit" not in keywords
    assert "ess beats" not in keywords
    assert "ic da" not in keywords
    assert "high e" not in keywords
    assert "Bass Drive" in keywords
    assert "EDM workout music" in keywords
    assert all("," not in item for item in keywords)
    assert all(len(item.split()) <= 3 for item in keywords)


def test_parse_tags_respects_youtube_length_budget() -> None:
    from platform_api.ai.purposes.channel_text import format_youtube_comma_field, normalize_youtube_tags

    tags = normalize_youtube_tags([f"workout music tag number {index}" for index in range(30)])
    joined = format_youtube_comma_field(tags, max_chars=500)
    assert len(joined) <= 500


def test_build_draft_routing_split_detection() -> None:
    lyric = type("R", (), {"provider": "slai", "sub_model": "xiaomi/mimo-v2.5-pro"})()
    title = type("R", (), {"provider": "openai", "sub_model": "gpt-4o-mini"})()
    album = type("R", (), {"provider": "slai", "sub_model": "xiaomi/mimo-v2.5-pro"})()
    routing = build_draft_routing(lyric, title, album)
    assert routing.use_split is True

    same = build_draft_routing(lyric, lyric, lyric)
    assert same.use_split is False
    assert same.title == TextRouting(provider="slai", sub_model="xiaomi/mimo-v2.5-pro")


def test_resolve_fal_api_model_id() -> None:
    assert resolve_fal_api_model_id("flux-pro") == "fal-ai/flux-pro/v1.1"
    assert resolve_fal_api_model_id("mimo-v2.5-pro") == "fal-ai/flux/schnell"


def test_resolve_text_model_alias() -> None:
    assert resolve_text_model_id("slai", "mimo-v2.5-pro") == "xiaomi/mimo-v2.5-pro"


def test_resolve_text_request_timeout_for_mimo() -> None:
    assert resolve_text_request_timeout("slai", "mimo-v2.5-pro", fallback=60.0) == 180.0
    assert resolve_text_request_timeout("deepseek", "deepseek-chat", fallback=60.0, draft=True) == 120.0


def test_parse_description_text_fallback() -> None:
    assert parse_description_text('{"description":"Hello channel"}') == "Hello channel"
    assert parse_description_text("Plain description text") == "Plain description text"
