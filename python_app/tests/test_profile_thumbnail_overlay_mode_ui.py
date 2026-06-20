"""Tests for profile-level thumbnail overlay mode dropdown integration."""

import unittest
from unittest.mock import MagicMock, patch

from python_app.features.profiles.management import MusicProfileManagementCoordinator


class FakeComboBox:
    """Minimal combo box mock for testing profile refresh logic."""

    def __init__(self):
        self._items = []  # list of (text, data) tuples
        self._current_index = 0
        self._signals_blocked = False

    def addItem(self, text, userData=None):
        self._items.append((text, userData))

    def findData(self, data):
        for i, (_, d) in enumerate(self._items):
            if d == data:
                return i
        return -1

    def setCurrentIndex(self, idx):
        self._current_index = idx

    def currentIndex(self):
        return self._current_index

    def currentData(self):
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][1]
        return None

    def blockSignals(self, block):
        self._signals_blocked = block


class TestRefreshProfileThumbnailOverlayMode(unittest.TestCase):
    """Tests for _refresh_profile_thumbnail_overlay_mode in MusicProfileManagementCoordinator."""

    def _make_coordinator(self, combo):
        host = MagicMock()
        host.music_settings_profile_thumbnail_overlay_mode = combo
        coord = MusicProfileManagementCoordinator.__new__(MusicProfileManagementCoordinator)
        coord.host = host
        return coord

    def _make_combo(self):
        combo = FakeComboBox()
        combo.addItem("AI (FAL/SLAI)", userData="ai")
        combo.addItem("Preset Text (Local)", userData="preset_text")
        return combo

    def test_defaults_to_ai_when_field_absent(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        profile = {"imageConfig": {"mode": "bg_thumb"}}
        coord._refresh_profile_thumbnail_overlay_mode(profile)
        assert combo.currentData() == "ai"

    def test_sets_preset_text_when_field_present(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        profile = {"imageConfig": {"thumbnailOverlayMode": "preset_text"}}
        coord._refresh_profile_thumbnail_overlay_mode(profile)
        assert combo.currentData() == "preset_text"

    def test_sets_ai_when_field_is_ai(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        profile = {"imageConfig": {"thumbnailOverlayMode": "ai"}}
        coord._refresh_profile_thumbnail_overlay_mode(profile)
        assert combo.currentData() == "ai"

    def test_defaults_to_ai_when_image_config_missing(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        profile = {}
        coord._refresh_profile_thumbnail_overlay_mode(profile)
        assert combo.currentData() == "ai"

    def test_defaults_to_ai_when_profile_is_none(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        coord._refresh_profile_thumbnail_overlay_mode(None)
        assert combo.currentData() == "ai"

    def test_defaults_to_ai_when_field_invalid(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        profile = {"imageConfig": {"thumbnailOverlayMode": "invalid_value"}}
        coord._refresh_profile_thumbnail_overlay_mode(profile)
        # "invalid_value" won't be found, so falls back to index 0 = "ai"
        assert combo.currentData() == "ai"

    def test_blocks_signals_during_refresh(self):
        combo = self._make_combo()
        coord = self._make_coordinator(combo)
        profile = {"imageConfig": {"thumbnailOverlayMode": "preset_text"}}
        # After refresh, signals should be unblocked
        coord._refresh_profile_thumbnail_overlay_mode(profile)
        assert combo._signals_blocked is False


class TestSaveProfileThumbnailOverlayMode(unittest.TestCase):
    """Tests that save_profile_details reads thumbnailOverlayMode from the combo."""

    def test_image_cfg_includes_thumbnail_overlay_mode(self):
        """When the combo is present, image_cfg should include thumbnailOverlayMode."""
        combo = FakeComboBox()
        combo.addItem("AI (FAL/SLAI)", userData="ai")
        combo.addItem("Preset Text (Local)", userData="preset_text")
        combo.setCurrentIndex(1)  # "preset_text"

        host = MagicMock()
        host.music_settings_profile_thumbnail_overlay_mode = combo

        # Also need the image mode combo
        image_mode_combo = FakeComboBox()
        image_mode_combo.addItem("Background + Thumbnail", userData="bg_thumb")
        host.music_settings_profile_image_mode = image_mode_combo

        # Minimal required attributes for save_profile_details
        host.music_settings_profile_name = MagicMock()
        host.music_settings_profile_name.text.return_value = "Test Profile"
        host.music_settings_profile_folder = MagicMock()
        host.music_settings_profile_folder.text.return_value = "test"
        host.music_settings_profile_prefix = MagicMock()
        host.music_settings_profile_prefix.text.return_value = "run"
        host.music_settings_profile_logo = MagicMock()
        host.music_settings_profile_logo.text.return_value = ""
        host.music_settings_profile_video_template = MagicMock()
        host.music_settings_profile_video_template.currentData.return_value = ""

        # Set up profile selection
        host._music_settings_selected_profile_id = "test-id"
        host.music_data = {"profiles": [{"id": "test-id", "name": "Test"}]}

        coord = MusicProfileManagementCoordinator(host=host)

        # Mock the save call to capture the updates dict
        saved_updates = {}
        def mock_save(pid, updates):
            saved_updates.update(updates)

        host._music_coordinator = MagicMock()
        host._music_coordinator.save_profile = mock_save
        host._refresh_music_settings_profile_list = MagicMock()
        host._refresh_music_profile_lists = MagicMock()
        host._refresh_music_ui = MagicMock()
        host._set_music_settings_status = MagicMock()

        coord.save_profile_details()

        assert "imageConfig" in saved_updates
        assert saved_updates["imageConfig"]["thumbnailOverlayMode"] == "preset_text"


if __name__ == "__main__":
    unittest.main()
