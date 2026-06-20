"""Music profile CRUD, resolution, and UI delegation coordinator."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..ports import ConfirmQuestionFn, ListPopulateFn, WarningFn

if TYPE_CHECKING:
    from ...app.main_window import MainWindow


@dataclass(slots=True)
class MusicProfileManagementCoordinator:
    """Owns profile CRUD, switching, and resolution logic extracted from MainWindow.

    The host retains UI widgets and controller calls; the coordinator
    encapsulates profile retrieval, persistence, and field mapping.
    """

    host: "MainWindow"
    confirm_question_fn: ConfirmQuestionFn | None = None
    warning_fn: WarningFn | None = None
    list_populate_fn: ListPopulateFn | None = None

    # ------------------------------------------------------------------
    # Profile resolution helpers
    # ------------------------------------------------------------------

    def music_profiles(self) -> list[dict[str, Any]]:
        """Return a fresh copy of all stored profile dicts."""

        music_data = getattr(self.host, "music_data", {})
        rows = music_data.get("profiles") if isinstance(music_data.get("profiles"), list) else []
        return [dict(row) for row in rows if isinstance(row, dict)]

    def music_profile_by_id(self, profile_id: str) -> dict | None:
        """Look up a profile by its string ID."""

        target = str(profile_id or "").strip()
        if not target:
            return None
        for profile in self.music_profiles():
            if isinstance(profile, dict) and str(profile.get("id", "")).strip() == target:
                return profile
        return None

    def selected_profile(self) -> dict | None:
        """Return the currently selected normalized profile."""

        current_id = str(
            getattr(self.host, "_music_settings_selected_profile_id", "") or ""
        ).strip()
        for profile in self.music_profiles():
            if str(profile.get("id", "")).strip() == current_id:
                return profile
        return None

    # ------------------------------------------------------------------
    # Profile list refresh
    # ------------------------------------------------------------------

    def refresh_list(self) -> None:
        """Rebuild the profile QListWidget and select the active profile."""

        host = self.host
        if not hasattr(host, "music_settings_profile_list"):
            return
        rows = self.music_profiles()
        current = str(
            getattr(host, "_music_settings_selected_profile_id", "") or ""
        ).strip()

        # Build (name, id) items for the list
        items: list[tuple[str, str]] = [
            (str(profile.get("name", "Unnamed Profile")), str(profile.get("id", "")).strip())
            for profile in rows
        ]

        if self.list_populate_fn is not None:
            self.list_populate_fn(items)
        else:
            # No-op fallback: clear the list widget directly without Qt imports
            host.music_settings_profile_list.blockSignals(True)
            host.music_settings_profile_list.clear()
            host.music_settings_profile_list.blockSignals(False)

        if rows and not current:
            current = str(rows[0].get("id", "")).strip()
        host._music_settings_selected_profile_id = current or None

        # Select the matching row in the list widget
        for idx in range(host.music_settings_profile_list.count()):
            item = host.music_settings_profile_list.item(idx)
            if item is not None:
                # Use text() comparison since we no longer read UserRole directly
                item_text = str(item.text() or "")
                # Find the matching id from our items list
                if idx < len(items) and items[idx][1] == current:
                    host.music_settings_profile_list.setCurrentRow(idx)
                    host.music_settings_profile_list.scrollToItem(item)
                    break

        self.load_profile_details()

    # ------------------------------------------------------------------
    # Profile detail loading
    # ------------------------------------------------------------------

    def load_profile_details(self) -> None:
        """Populate the Settings -> Profile detail fields from the selected profile."""

        host = self.host
        profile = self.selected_profile()
        has_profile = profile is not None

        self._set_if_present("music_settings_profile_name", str((profile or {}).get("name", "")).strip())
        self._set_if_present("music_settings_profile_folder", str((profile or {}).get("folderName", "")).strip())
        self._set_if_present("music_settings_profile_prefix", str((profile or {}).get("runPrefix", "")).strip())
        self._set_if_present("music_settings_profile_logo", str((profile or {}).get("logoPath", "")).strip())

        self._refresh_profile_video_templates(profile)
        self._refresh_profile_reel_templates(profile)
        self._refresh_profile_output_resolution(profile)
        self._refresh_profile_youtube_oauth_apps(profile)
        self._refresh_profile_youtube_status(profile)
        self._refresh_profile_youtube_visibility(profile)
        self._refresh_profile_youtube_publish_date(profile)
        self._refresh_profile_youtube_category(profile)
        self._refresh_profile_youtube_playlist(profile)
        self._refresh_profile_youtube_tags(profile)
        self._refresh_profile_youtube_title(profile)
        self._refresh_profile_youtube_description(profile)
        self._refresh_profile_youtube_made_for_kids(profile)
        self._refresh_profile_youtube_ai_use(profile)
        self._refresh_profile_image_mode(profile)
        self._refresh_profile_thumbnail_overlay_mode(profile)
        self._refresh_profile_image_prompts(profile)
        self._refresh_profile_image_dirs(profile)
        self._refresh_profile_image_random(profile)
        self._refresh_profile_image_samples(profile)

    def _set_if_present(self, attr: str, value: str) -> None:
        widget = getattr(self.host, attr, None)
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(value)

    def _refresh_profile_video_templates(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_video_template"):
            return
        has_profile = profile is not None
        sel_id = str((profile or {}).get("videoTemplateId", "")).strip() if has_profile else ""
        host._refresh_music_settings_profile_video_templates(sel_id)

    def _refresh_profile_reel_templates(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_reel_template"):
            return
        has_profile = profile is not None
        sel_id = str((profile or {}).get("reelTemplateId", "")).strip() if has_profile else ""
        host._refresh_music_settings_profile_reel_templates(sel_id)

    def _refresh_profile_output_resolution(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_output_resolution"):
            return
        res = str((profile or {}).get("outputResolution", "")).strip()
        combo = host.music_settings_profile_output_resolution
        idx = combo.findData(res)
        combo.blockSignals(True)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_profile_youtube_oauth_apps(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_youtube_oauth_app"):
            return
        has_profile = profile is not None
        sel_id = str((profile or {}).get("youtubeOauthAppId", "")).strip() if has_profile else ""
        host._refresh_music_settings_profile_youtube_oauth_apps(sel_id)

    def _refresh_profile_youtube_status(self, profile: dict | None) -> None:
        """Update the YouTube status label with channel name if connected."""
        host = self.host
        if not hasattr(host, "music_settings_profile_youtube_status"):
            return
        if not host.db_cfg or not profile:
            host.music_settings_profile_youtube_status.setText("Not connected")
            host._set_label_role(host.music_settings_profile_youtube_status, "statusMuted")
            return
        try:
            from ...database.youtube_db import db_get_youtube_account

            profile_id = str(profile.get("id", "")).strip()
            acc = db_get_youtube_account(host.db_cfg, profile_id)
            if acc and str(acc.channel_title or "").strip():
                channel_title = str(acc.channel_title).strip()
                channel_id = str(acc.channel_id or "").strip()
                display = f"Connected: {channel_title}"
                if channel_id:
                    display += f" ({channel_id})"
                host.music_settings_profile_youtube_status.setText(display)
                host._set_label_role(host.music_settings_profile_youtube_status, "statusGood")
            else:
                host.music_settings_profile_youtube_status.setText("Not connected")
                host._set_label_role(host.music_settings_profile_youtube_status, "statusMuted")
        except Exception:
            host.music_settings_profile_youtube_status.setText("Not connected")
            host._set_label_role(host.music_settings_profile_youtube_status, "statusMuted")

    def _refresh_profile_youtube_visibility(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_youtube_visibility"):
            return
        mode = str((profile or {}).get("youtubeVisibilityMode", "")).strip() or "unlisted"
        idx = host.music_settings_profile_youtube_visibility.findData(mode)
        host.music_settings_profile_youtube_visibility.setCurrentIndex(idx if idx >= 0 else 0)

    def _refresh_profile_youtube_publish_date(self, profile: dict | None) -> None:
        import re

        host = self.host
        if not hasattr(host, "music_settings_profile_youtube_publish_date"):
            return

        publish_at = str((profile or {}).get("youtubePublishAt", "")).strip()
        dt: datetime.datetime | None = None
        time_text = ""
        if publish_at:
            if "T" in publish_at:
                try:
                    safe = publish_at[:-1] + "+00:00" if publish_at.endswith("Z") else publish_at
                    dt = datetime.datetime.fromisoformat(safe)
                    try:
                        dt = dt.astimezone()
                    except Exception:
                        pass
                    time_text = f"{dt.hour:02d}:{dt.minute:02d}"
                except Exception:
                    dt = None
                    time_text = ""
            else:
                time_text = publish_at

        # Use Python datetime.date and let the view layer convert to QDate
        target_date: datetime.date = (
            datetime.date(dt.year, dt.month, dt.day) if dt is not None else datetime.date.today()
        )

        # The widget's setDate method expects a QDate, so we delegate through
        # a helper that the host provides or call a simple date-setting approach
        # that the adapter/view layer handles. For now we use the widget's
        # setDate via a tuple accessor pattern if available, otherwise pass
        # individual values.
        date_widget = host.music_settings_profile_youtube_publish_date
        if hasattr(date_widget, "set_date_from_python"):
            # Custom adapter method
            date_widget.set_date_from_python(target_date)
        elif hasattr(date_widget, "setDate"):
            # Fallback: construct date at view boundary (host is responsible)
            # We pass the date values so the host/adapter can convert
            date_widget.setDate(target_date)

        if hasattr(host, "music_settings_profile_youtube_publish_hour") and hasattr(host, "music_settings_profile_youtube_publish_minute"):
            hh = 0
            mm = 0
            m2 = re.match(r"^(\d{1,2}):(\d{2})$", str(time_text or "").strip())
            if m2:
                try:
                    hh = max(0, min(23, int(m2.group(1))))
                    mm = max(0, min(59, int(m2.group(2))))
                except Exception:
                    hh = 0
                    mm = 0
            mm = max(0, min(55, int(mm / 5) * 5))

            hour_combo = host.music_settings_profile_youtube_publish_hour
            minute_combo = host.music_settings_profile_youtube_publish_minute
            hidx = hour_combo.findData(hh)
            midx = minute_combo.findData(mm)
            hour_combo.blockSignals(True)
            minute_combo.blockSignals(True)
            if hidx >= 0:
                hour_combo.setCurrentIndex(hidx)
            if midx >= 0:
                minute_combo.setCurrentIndex(midx)
            hour_combo.blockSignals(False)
            minute_combo.blockSignals(False)

    def _refresh_profile_youtube_category(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_youtube_category"):
            return
        raw = str((profile or {}).get("youtubeCategoryId", "")).strip()
        mapped = {
            "music": "10",
            "entertainment": "24",
            "people & blogs": "22",
            "people and blogs": "22",
            "gaming": "20",
            "film & animation": "1",
            "film and animation": "1",
            "autos & vehicles": "2",
            "autos and vehicles": "2",
        }
        resolved = mapped.get(raw.lower()) if raw.lower() in mapped else raw
        combo = host.music_settings_profile_youtube_category
        idx = combo.findData(resolved)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _refresh_profile_youtube_playlist(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_youtube_playlist"):
            return
        pid = str((profile or {}).get("youtubePlaylistId", "")).strip()
        combo = host.music_settings_profile_youtube_playlist
        idx = combo.findData(pid)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _refresh_profile_youtube_tags(self, profile: dict | None) -> None:
        self._set_if_present(
            "music_settings_profile_youtube_tags",
            str((profile or {}).get("youtubeTags", "")).strip(),
        )

    def _refresh_profile_youtube_title(self, profile: dict | None) -> None:
        self._set_if_present(
            "music_settings_profile_youtube_title",
            str((profile or {}).get("youtubeTitleTemplate", "")).strip(),
        )

    def _refresh_profile_youtube_description(self, profile: dict | None) -> None:
        widget = getattr(self.host, "music_settings_profile_youtube_description", None)
        if widget is not None and hasattr(widget, "setPlainText"):
            widget.setPlainText(str((profile or {}).get("youtubeDescriptionTemplate", "")).strip())

    def _refresh_profile_youtube_made_for_kids(self, profile: dict | None) -> None:
        widget = getattr(self.host, "music_settings_profile_youtube_made_for_kids", None)
        if widget is not None and hasattr(widget, "setChecked"):
            widget.setChecked(bool((profile or {}).get("youtubeMadeForKids", False)))

    def _refresh_profile_youtube_ai_use(self, profile: dict | None) -> None:
        widget = getattr(self.host, "music_settings_profile_youtube_ai_use", None)
        if widget is not None and hasattr(widget, "setCurrentIndex"):
            val = bool((profile or {}).get("youtubeContainsSyntheticMedia", False))
            idx = widget.findData(val)
            widget.setCurrentIndex(idx if idx >= 0 else 0)

    def _refresh_profile_image_mode(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_image_mode"):
            return
        img_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        mode = str(img_cfg.get("mode", "bg_thumb")).strip() or "bg_thumb"
        combo = host.music_settings_profile_image_mode
        idx = combo.findData(mode)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _refresh_profile_thumbnail_overlay_mode(self, profile: dict | None) -> None:
        host = self.host
        if not hasattr(host, "music_settings_profile_thumbnail_overlay_mode"):
            return
        img_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        mode = str(img_cfg.get("thumbnailOverlayMode", "ai")).strip() or "ai"
        combo = host.music_settings_profile_thumbnail_overlay_mode
        combo.blockSignals(True)
        idx = combo.findData(mode)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_profile_image_prompts(self, profile: dict | None) -> None:
        host = self.host
        img_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        self._set_if_present(
            "music_settings_profile_image_base_prompt",
            str(img_cfg.get("basePrompt", "")).strip(),
        )
        self._set_if_present(
            "music_settings_profile_image_bg_prompt",
            str(img_cfg.get("backgroundPrompt", "")).strip(),
        )
        self._set_if_present(
            "music_settings_profile_image_thumb_prompt",
            str(img_cfg.get("thumbnailPrompt", "")).strip(),
        )

    def _refresh_profile_image_dirs(self, profile: dict | None) -> None:
        host = self.host
        img_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        self._set_if_present(
            "music_settings_profile_image_bg_dir",
            str(img_cfg.get("backgroundSamplesDir", "")).strip(),
        )
        self._set_if_present(
            "music_settings_profile_image_thumb_dir",
            str(img_cfg.get("thumbnailSamplesDir", "")).strip(),
        )

    def _refresh_profile_image_random(self, profile: dict | None) -> None:
        host = self.host
        img_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        widget_bg = getattr(host, "music_settings_profile_image_bg_random", None)
        if widget_bg is not None and hasattr(widget_bg, "setChecked"):
            widget_bg.setChecked(bool(img_cfg.get("backgroundRandom", False)))

        widget_thumb = getattr(host, "music_settings_profile_image_thumb_random", None)
        if widget_thumb is not None and hasattr(widget_thumb, "setChecked"):
            widget_thumb.setChecked(bool(img_cfg.get("thumbnailRandom", False)))

    def _refresh_profile_image_samples(self, profile: dict | None) -> None:
        host = self.host
        img_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        bg_samples = img_cfg.get("backgroundSamples")
        thumb_samples = img_cfg.get("thumbnailSamples")

        bg_list = getattr(host, "music_settings_profile_image_bg_samples_list", None)
        if bg_list is not None and isinstance(bg_samples, list):
            for i in range(bg_list.count()):
                item = bg_list.item(i)
                if item is not None:
                    # Access user-role data via the item's data method with int role
                    # The adapter/view layer stores data with role 0x0100 (UserRole)
                    path = str(item.data(0x0100) or "").strip()
                    item.setSelected(path in bg_samples)

        thumb_list = getattr(host, "music_settings_profile_image_thumb_samples_list", None)
        if thumb_list is not None and isinstance(thumb_samples, list):
            for i in range(thumb_list.count()):
                item = thumb_list.item(i)
                if item is not None:
                    path = str(item.data(0x0100) or "").strip()
                    item.setSelected(path in thumb_samples)

    # ------------------------------------------------------------------
    # Profile save
    # ------------------------------------------------------------------

    def save_profile(self) -> None:
        """Persist edits for the selected profile."""

        return self.host._save_music_settings_profile_impl()

    def save_profile_details(self) -> None:
        """Read UI controls and persist the selected profile via the music controller."""

        from datetime import datetime as _datetime

        host = self.host
        profile = self.selected_profile()
        if not profile:
            if self.warning_fn is not None:
                self.warning_fn("Profiles", "Select a profile first.")
            return

        template_id = ""
        if hasattr(host, "music_settings_profile_video_template"):
            template_id = str(host.music_settings_profile_video_template.currentData() or "").strip()

        reel_template_id = ""
        if hasattr(host, "music_settings_profile_reel_template"):
            reel_template_id = str(host.music_settings_profile_reel_template.currentData() or "").strip()

        updates: dict[str, Any] = {
            "name": str(host.music_settings_profile_name.text() or "").strip() or "Unnamed Profile",
            "folderName": str(host.music_settings_profile_folder.text() or "").strip(),
            "runPrefix": str(host.music_settings_profile_prefix.text() or "").strip(),
            "logoPath": str(host.music_settings_profile_logo.text() or "").strip(),
            "videoTemplateId": template_id,
            "reelTemplateId": reel_template_id,
        }

        if hasattr(host, "music_settings_profile_output_resolution"):
            updates["outputResolution"] = str(host.music_settings_profile_output_resolution.currentData() or "").strip()

        image_cfg: dict = {}
        if hasattr(host, "music_settings_profile_image_mode"):
            mode = str(host.music_settings_profile_image_mode.currentData() or "bg_thumb").strip() or "bg_thumb"
            image_cfg["mode"] = mode
        if hasattr(host, "music_settings_profile_thumbnail_overlay_mode"):
            overlay_mode = str(host.music_settings_profile_thumbnail_overlay_mode.currentData() or "ai").strip() or "ai"
            image_cfg["thumbnailOverlayMode"] = overlay_mode
        if hasattr(host, "music_settings_profile_image_base_prompt"):
            text = str(host.music_settings_profile_image_base_prompt.toPlainText() or "").strip()
            if text:
                image_cfg["basePrompt"] = text
        if hasattr(host, "music_settings_profile_image_bg_prompt"):
            text = str(host.music_settings_profile_image_bg_prompt.toPlainText() or "").strip()
            if text:
                image_cfg["backgroundPrompt"] = text
        if hasattr(host, "music_settings_profile_image_thumb_prompt"):
            text = str(host.music_settings_profile_image_thumb_prompt.toPlainText() or "").strip()
            if text:
                image_cfg["thumbnailPrompt"] = text
        if hasattr(host, "music_settings_profile_image_thumb_tracklist"):
            # checkState() returns int-compatible enum; 1 = PartiallyChecked
            # Only persist when the widget is in a determinate state.
            widget_state = host.music_settings_profile_image_thumb_tracklist.checkState()
            if widget_state.value != 1:  # not PartiallyChecked
                image_cfg["thumbnailIncludeTrackTitles"] = widget_state.value == 2  # Checked
        if hasattr(host, "music_settings_profile_image_bg_dir"):
            text = str(host.music_settings_profile_image_bg_dir.text() or "").strip()
            if text:
                image_cfg["backgroundSamplesDir"] = text
        if hasattr(host, "music_settings_profile_image_thumb_dir"):
            text = str(host.music_settings_profile_image_thumb_dir.text() or "").strip()
            if text:
                image_cfg["thumbnailSamplesDir"] = text
        if hasattr(host, "music_settings_profile_image_bg_random"):
            image_cfg["backgroundRandom"] = bool(host.music_settings_profile_image_bg_random.isChecked())
        if hasattr(host, "music_settings_profile_image_thumb_random"):
            image_cfg["thumbnailRandom"] = bool(host.music_settings_profile_image_thumb_random.isChecked())
        if hasattr(host, "music_settings_profile_image_bg_samples_list"):
            rows = []
            try:
                rows = [str(it.data(0x0100) or "").strip() for it in host.music_settings_profile_image_bg_samples_list.selectedItems()]
            except Exception:
                rows = []
            rows = [x for x in rows if x][:5]
            if rows:
                image_cfg["backgroundSamples"] = rows
        if hasattr(host, "music_settings_profile_image_thumb_samples_list"):
            rows = []
            try:
                rows = [str(it.data(0x0100) or "").strip() for it in host.music_settings_profile_image_thumb_samples_list.selectedItems()]
            except Exception:
                rows = []
            rows = [x for x in rows if x][:5]
            if rows:
                image_cfg["thumbnailSamples"] = rows
        updates["imageConfig"] = image_cfg

        if hasattr(host, "music_settings_profile_youtube_visibility"):
            mode = str(host.music_settings_profile_youtube_visibility.currentData() or "unlisted").strip() or "unlisted"
            updates["youtubeVisibilityMode"] = mode
            publish_at = ""
            if mode == "scheduled" and hasattr(host, "music_settings_profile_youtube_publish_hour") and hasattr(host, "music_settings_profile_youtube_publish_minute"):
                try:
                    hh = int(host.music_settings_profile_youtube_publish_hour.currentData() or 0)
                except Exception:
                    hh = 0
                try:
                    mm = int(host.music_settings_profile_youtube_publish_minute.currentData() or 0)
                except Exception:
                    mm = 0
                publish_at = f"{max(0, min(23, hh)):02d}:{max(0, min(55, mm)):02d}"
            updates["youtubePublishAt"] = publish_at

        if hasattr(host, "music_settings_profile_youtube_category"):
            combo = host.music_settings_profile_youtube_category
            picked = str(combo.currentData() or "").strip()
            if picked:
                updates["youtubeCategoryId"] = picked
            else:
                import re
                txt = str(combo.currentText() or "").strip()
                m = re.search(r"\((\d+)\)", txt)
                value = (m.group(1) if m else txt).strip()
                updates["youtubeCategoryId"] = value if value.isdigit() else ""

        if hasattr(host, "music_settings_profile_youtube_playlist"):
            combo = host.music_settings_profile_youtube_playlist
            pid = str(combo.currentData() or "").strip()
            updates["youtubePlaylistId"] = "" if pid == "__loading__" else pid

        if hasattr(host, "music_settings_profile_youtube_tags"):
            updates["youtubeTags"] = str(host.music_settings_profile_youtube_tags.text() or "").strip()
        if hasattr(host, "music_settings_profile_youtube_title"):
            updates["youtubeTitleTemplate"] = str(host.music_settings_profile_youtube_title.text() or "").strip()
        if hasattr(host, "music_settings_profile_youtube_description"):
            updates["youtubeDescriptionTemplate"] = str(host.music_settings_profile_youtube_description.toPlainText() or "").strip()
        if hasattr(host, "music_settings_profile_youtube_made_for_kids"):
            updates["youtubeMadeForKids"] = bool(host.music_settings_profile_youtube_made_for_kids.isChecked())
        if hasattr(host, "music_settings_profile_youtube_ai_use"):
            updates["youtubeContainsSyntheticMedia"] = bool(host.music_settings_profile_youtube_ai_use.currentData() or False)
        if hasattr(host, "music_settings_profile_youtube_oauth_app"):
            updates["youtubeOauthAppId"] = str(host.music_settings_profile_youtube_oauth_app.currentData() or "").strip()

        pid = str(profile.get("id", "")).strip()
        try:
            host._music_coordinator.save_profile(pid, updates)
        except Exception as exc:
            msg = str(exc).strip() or "Unknown error"
            if self.warning_fn is not None:
                self.warning_fn("Profiles", f"Save failed: {msg}")
            host._set_music_settings_status(f"Profile save failed: {msg}")
            return

        host._refresh_music_settings_profile_list()
        host._refresh_music_profile_lists()
        host._refresh_music_ui()
        stamp = _datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        name = str(updates.get("name", "")).strip() or str(profile.get("name", "")).strip() or "Profile"
        host._set_music_settings_status(f"Profile saved: {name} \u00b7 {stamp}")

    # ------------------------------------------------------------------
    # Profile creation
    # ------------------------------------------------------------------

    def create_profile(self) -> None:
        """Create a new profile from the Settings input field."""

        host = self.host
        name = str(host.music_settings_new_profile_name.text() or "").strip() if hasattr(host, "music_settings_new_profile_name") else ""
        if not name:
            if self.warning_fn is not None:
                self.warning_fn("Profiles", "Enter a new profile name first.")
            return
        host._music_coordinator.create_profile(name)
        if hasattr(host, "music_settings_new_profile_name"):
            host.music_settings_new_profile_name.clear()
        self.refresh_list()
        host._refresh_music_profile_lists()
        host._refresh_music_ui()
        host._set_music_settings_status(f"Profile created: {name}")

    # ------------------------------------------------------------------
    # Profile deletion
    # ------------------------------------------------------------------

    def delete_profile(self) -> None:
        """Delete the currently selected profile after confirmation."""

        host = self.host
        profile = self.selected_profile()
        if not profile:
            if self.warning_fn is not None:
                self.warning_fn("Profiles", "Select a profile first.")
            return
        if self.confirm_question_fn is not None:
            confirmed = self.confirm_question_fn("Profiles", f'Delete profile "{str(profile.get("name", "")).strip()}"?')
            if not confirmed:
                return
        else:
            # No-op fallback: don't proceed with deletion without confirmation
            return
        host._music_coordinator.delete_profile(str(profile.get("id", "")).strip())
        self.refresh_list()
        host._refresh_music_profile_lists()
        host._refresh_music_ui()
        host._set_music_settings_status("Profile deleted")
