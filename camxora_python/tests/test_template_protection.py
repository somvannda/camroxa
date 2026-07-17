"""Tests for marketplace template protection logic.

Validates read-only enforcement, Save As name validation, and copy preparation.
"""

from __future__ import annotations

import uuid

from features.marketplace.template_protection import (
    can_save_template,
    is_marketplace_template,
    prepare_save_as_copy,
    validate_save_as_name,
)


class TestIsMarketplaceTemplate:
    """is_marketplace_template checks if source == 'marketplace'."""

    def test_marketplace_source_returns_true(self) -> None:
        assert is_marketplace_template({"source": "marketplace"}) is True

    def test_user_source_returns_false(self) -> None:
        assert is_marketplace_template({"source": "user"}) is False

    def test_builtin_source_returns_false(self) -> None:
        assert is_marketplace_template({"source": "builtin"}) is False

    def test_empty_source_returns_false(self) -> None:
        assert is_marketplace_template({"source": ""}) is False

    def test_missing_source_returns_false(self) -> None:
        assert is_marketplace_template({}) is False

    def test_case_insensitive(self) -> None:
        assert is_marketplace_template({"source": "Marketplace"}) is True
        assert is_marketplace_template({"source": "MARKETPLACE"}) is True

    def test_whitespace_padded(self) -> None:
        assert is_marketplace_template({"source": " marketplace "}) is True


class TestCanSaveTemplate:
    """can_save_template returns False for marketplace, True for others."""

    def test_marketplace_cannot_save(self) -> None:
        assert can_save_template({"source": "marketplace"}) is False

    def test_user_can_save(self) -> None:
        assert can_save_template({"source": "user"}) is True

    def test_builtin_can_save(self) -> None:
        assert can_save_template({"source": "builtin"}) is True

    def test_empty_source_can_save(self) -> None:
        assert can_save_template({"source": ""}) is True

    def test_missing_source_can_save(self) -> None:
        assert can_save_template({}) is True


class TestValidateSaveAsName:
    """validate_save_as_name rejects empty, whitespace-only, and >100 char names."""

    def test_valid_name(self) -> None:
        valid, error = validate_save_as_name("My Template Copy")
        assert valid is True
        assert error == ""

    def test_empty_string_rejected(self) -> None:
        valid, error = validate_save_as_name("")
        assert valid is False
        assert "empty" in error.lower()

    def test_whitespace_only_rejected(self) -> None:
        valid, error = validate_save_as_name("   ")
        assert valid is False
        assert "whitespace" in error.lower()

    def test_tabs_only_rejected(self) -> None:
        valid, error = validate_save_as_name("\t\t")
        assert valid is False
        assert "whitespace" in error.lower()

    def test_newline_only_rejected(self) -> None:
        valid, error = validate_save_as_name("\n\n")
        assert valid is False
        assert "whitespace" in error.lower()

    def test_max_100_chars_valid(self) -> None:
        name = "x" * 100
        valid, error = validate_save_as_name(name)
        assert valid is True
        assert error == ""

    def test_101_chars_rejected(self) -> None:
        name = "x" * 101
        valid, error = validate_save_as_name(name)
        assert valid is False
        assert "100" in error

    def test_single_char_valid(self) -> None:
        valid, error = validate_save_as_name("A")
        assert valid is True
        assert error == ""

    def test_name_with_leading_trailing_spaces_valid(self) -> None:
        # Leading/trailing spaces are allowed as long as there are non-space chars
        valid, error = validate_save_as_name("  My Template  ")
        assert valid is True
        assert error == ""


class TestPrepareSaveAsCopy:
    """prepare_save_as_copy creates a new template dict with correct fields."""

    def test_generates_new_uid(self) -> None:
        original = {
            "uid": "original-uid-123",
            "name": "Original Template",
            "source": "marketplace",
            "template": {"style": "bars", "spectrumEnabled": True},
            "kind": "video",
            "marketplace_item_id": "mkt-item-1",
        }
        result = prepare_save_as_copy(original, "My Copy", "user-42")
        assert result["uid"] != "original-uid-123"
        # Validate it's a proper UUID
        uuid.UUID(result["uid"])

    def test_sets_source_to_user(self) -> None:
        original = {"source": "marketplace", "template": {}, "kind": "video"}
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["source"] == "user"

    def test_uses_provided_name(self) -> None:
        original = {"source": "marketplace", "template": {}, "kind": "video"}
        result = prepare_save_as_copy(original, "My New Name", "user-1")
        assert result["name"] == "My New Name"

    def test_copies_template_json(self) -> None:
        template_json = {"style": "ring", "spectrumEnabled": True, "audioSettings": {"inputGain": 1.0}}
        original = {"source": "marketplace", "template": template_json, "kind": "video"}
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["template"] == template_json
        # Ensure it's a copy, not a reference
        assert result["template"] is not template_json

    def test_preserves_kind(self) -> None:
        original = {"source": "marketplace", "template": {}, "kind": "reel"}
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["kind"] == "reel"

    def test_sets_user_id(self) -> None:
        original = {"source": "marketplace", "template": {}, "kind": "video"}
        result = prepare_save_as_copy(original, "Copy", "user-abc")
        assert result["user_id"] == "user-abc"

    def test_preserves_marketplace_item_id(self) -> None:
        original = {
            "source": "marketplace",
            "template": {},
            "kind": "video",
            "marketplace_item_id": "item-xyz",
        }
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["marketplace_item_id"] == "item-xyz"

    def test_handles_missing_template_gracefully(self) -> None:
        original = {"source": "marketplace", "kind": "video"}
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["template"] == {}

    def test_handles_non_dict_template(self) -> None:
        original = {"source": "marketplace", "template": "invalid", "kind": "video"}
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["template"] == {}

    def test_defaults_kind_to_video(self) -> None:
        original = {"source": "marketplace", "template": {}}
        result = prepare_save_as_copy(original, "Copy", "user-1")
        assert result["kind"] == "video"
