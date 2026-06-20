from __future__ import annotations

from unittest.mock import patch

import pytest

from python_app.services.image_generation import _get_thumbnail_overlay_mode


class TestGetThumbnailOverlayMode:
    """Tests for _get_thumbnail_overlay_mode helper function."""

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_returns_ai_when_field_present(self, mock_get_config):
        mock_get_config.return_value = {
            "mode": "bg_thumb",
            "thumbnailOverlayMode": "ai",
        }
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_returns_preset_text_when_field_present(self, mock_get_config):
        mock_get_config.return_value = {
            "mode": "bg_thumb",
            "thumbnailOverlayMode": "preset_text",
        }
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "preset_text"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_when_field_absent(self, mock_get_config):
        mock_get_config.return_value = {
            "mode": "bg_thumb",
            "backgroundPrompt": "some prompt",
        }
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_when_field_invalid(self, mock_get_config):
        mock_get_config.return_value = {
            "mode": "bg_thumb",
            "thumbnailOverlayMode": "invalid_mode",
        }
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_when_config_is_empty(self, mock_get_config):
        mock_get_config.return_value = {}
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_when_config_is_none(self, mock_get_config):
        mock_get_config.return_value = None
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_on_database_exception(self, mock_get_config):
        mock_get_config.side_effect = Exception("DB connection failed")
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_when_field_is_empty_string(self, mock_get_config):
        mock_get_config.return_value = {
            "thumbnailOverlayMode": "",
        }
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"

    @patch("python_app.services.image_generation.db_get_profile_image_config")
    def test_defaults_to_ai_when_field_is_numeric(self, mock_get_config):
        mock_get_config.return_value = {
            "thumbnailOverlayMode": 123,
        }
        result = _get_thumbnail_overlay_mode("db_cfg", "profile-1", {})
        assert result == "ai"
