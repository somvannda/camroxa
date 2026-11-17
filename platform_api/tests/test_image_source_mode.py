"""Tests for image kind source mode normalization (P0 prompt_only)."""

from __future__ import annotations

from platform_api.models.enums import ImageKind
from platform_api.services.image_source_mode import (
    SOURCE_MODE_CATEGORY,
    SOURCE_MODE_PERSONAL_REFERENCE,
    SOURCE_MODE_PROMPT_ONLY,
    empty_prompt_error_message,
    is_personal_reference_source,
    is_prompt_only_source,
    normalize_image_kind_source_mode,
    personal_reference_not_ready_message,
)


def test_defaults_to_category_without_keys() -> None:
    assert normalize_image_kind_source_mode({}, ImageKind.BACKGROUND) == SOURCE_MODE_CATEGORY
    assert normalize_image_kind_source_mode({}, ImageKind.THUMBNAIL) == SOURCE_MODE_CATEGORY


def test_legacy_prompt_maps_background_only() -> None:
    settings = {"backgroundSourceMode": "prompt"}
    assert normalize_image_kind_source_mode(settings, ImageKind.BACKGROUND) == SOURCE_MODE_PROMPT_ONLY
    assert normalize_image_kind_source_mode(settings, ImageKind.THUMBNAIL) == SOURCE_MODE_CATEGORY


def test_dual_keys_override_legacy() -> None:
    settings = {
        "backgroundSourceMode": "prompt",
        "imageBackgroundSourceMode": "category",
        "imageThumbnailSourceMode": "prompt_only",
    }
    assert normalize_image_kind_source_mode(settings, ImageKind.BACKGROUND) == SOURCE_MODE_CATEGORY
    assert normalize_image_kind_source_mode(settings, ImageKind.THUMBNAIL) == SOURCE_MODE_PROMPT_ONLY
    assert is_prompt_only_source(settings, ImageKind.THUMBNAIL) is True


def test_samples_alias_maps_to_category() -> None:
    settings = {"imageBackgroundSourceMode": "samples"}
    assert normalize_image_kind_source_mode(settings, ImageKind.BACKGROUND) == SOURCE_MODE_CATEGORY


def test_personal_reference_mode() -> None:
    settings = {
        "imageBackgroundSourceMode": "personal_reference",
        "imageThumbnailSourceMode": "user_reference",
    }
    assert (
        normalize_image_kind_source_mode(settings, ImageKind.BACKGROUND)
        == SOURCE_MODE_PERSONAL_REFERENCE
    )
    assert (
        normalize_image_kind_source_mode(settings, ImageKind.THUMBNAIL)
        == SOURCE_MODE_PERSONAL_REFERENCE
    )
    assert is_personal_reference_source(settings, ImageKind.BACKGROUND) is True
    assert "not available yet" in personal_reference_not_ready_message(ImageKind.BACKGROUND)


def test_empty_prompt_messages_are_kind_specific() -> None:
    assert "Background:" in empty_prompt_error_message(ImageKind.BACKGROUND)
    assert "Thumbnail:" in empty_prompt_error_message(ImageKind.THUMBNAIL)


def test_prompt_library_only_forces_admin_source() -> None:
    from platform_api.services.image_source_mode import (
        PROMPT_SOURCE_ADMIN_LIBRARY,
        normalize_prompt_source,
        prompt_library_only,
    )

    settings = {
        "imagePromptLibraryOnly": "true",
        "imageBackgroundPromptSource": "custom",
        "imageThumbnailPromptSource": "custom",
    }

    assert prompt_library_only(settings)
    assert normalize_prompt_source(settings, ImageKind.BACKGROUND) == (
        PROMPT_SOURCE_ADMIN_LIBRARY
    )
    assert normalize_prompt_source(settings, ImageKind.THUMBNAIL) == (
        PROMPT_SOURCE_ADMIN_LIBRARY
    )
    assert normalize_prompt_source({}, ImageKind.BACKGROUND) == "custom"
