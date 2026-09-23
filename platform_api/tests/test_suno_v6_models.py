"""Suno V6 model enablement: registry, request validation, and pricing keys."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from platform_api.ai.registry import (
    DEFAULT_SUNO_MUSIC_MODEL,
    SUNO_MODEL_PATTERN,
    resolve_suno_model_id,
)
from platform_api.routers.web_music import WebMusicGenerateRequest
from platform_api.services.pricing_keys import normalize_suno_pricing_sub_model

V6_MODELS = ("V6", "V6_MINI", "V6_WILD")
LEGACY_MODELS = ("V5", "V5_5")


def test_default_model_is_v6() -> None:
    assert DEFAULT_SUNO_MUSIC_MODEL == "V6"


@pytest.mark.parametrize("model", V6_MODELS + LEGACY_MODELS)
def test_model_pattern_accepts_supported_models(model: str) -> None:
    assert re.fullmatch(SUNO_MODEL_PATTERN, model)


@pytest.mark.parametrize("model", ["V4", "V4_5", "v6", "V7", "", "V6MINI"])
def test_model_pattern_rejects_unknown_models(model: str) -> None:
    assert re.fullmatch(SUNO_MODEL_PATTERN, model) is None


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("v6", "V6"),
        ("V6", "V6"),
        ("v6 mini", "V6_MINI"),
        ("V6_MINI", "V6_MINI"),
        ("v6wild", "V6_WILD"),
        ("v5", "V5"),
        ("v5.5", "V5_5"),
        (None, "V6"),
        ("garbage", "V6"),
    ],
)
def test_resolve_suno_model_id(version: str | None, expected: str) -> None:
    assert resolve_suno_model_id(version) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("V6", "V6"),
        ("v6", "V6"),
        ("v6.0", "V6"),
        ("V6_MINI", "V6_MINI"),
        ("v6 mini", "V6_MINI"),
        ("V6_WILD", "V6_WILD"),
        ("v6wild", "V6_WILD"),
        ("V5_5", "V5_5"),
        ("V5", "V5"),
    ],
)
def test_normalize_suno_pricing_sub_model_v6(raw: str, expected: str) -> None:
    assert normalize_suno_pricing_sub_model(raw) == expected


def test_web_music_request_defaults_to_v6() -> None:
    request = WebMusicGenerateRequest(mode="advanced", lyrics="la la")
    assert request.model == "V6"


@pytest.mark.parametrize("model", V6_MODELS)
def test_web_music_request_accepts_v6_models(model: str) -> None:
    request = WebMusicGenerateRequest(mode="advanced", lyrics="la la", model=model)
    assert request.model == model


def test_web_music_request_rejects_unknown_model() -> None:
    with pytest.raises(ValidationError):
        WebMusicGenerateRequest(mode="advanced", lyrics="la la", model="V4")
