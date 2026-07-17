from __future__ import annotations

import pytest

from platform_api.services.streaming_slug import slugify


def test_slugify_basic() -> None:
    assert slugify("My Album: Vol. 2") == "my-album-vol-2"
    assert slugify("   ") == "item"


def test_slugify_truncates() -> None:
    assert len(slugify("a" * 200)) <= 120
