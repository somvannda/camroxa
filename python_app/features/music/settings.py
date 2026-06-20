"""Music settings coordinator.

Encapsulates Suno/music settings read, write, and UI-population logic
extracted from MainWindow to reduce its size and improve maintainability.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..ports import (
    ConfirmQuestionFn,
    FileDialogFn,
    TablePopulateFn,
    WarningFn,
)

if TYPE_CHECKING:
    from ...app.main_window import MainWindow


@dataclass(slots=True)
class MusicSunoSettingsPatch:
    """Collected patch dict ready to be persisted via _persist_setting_patch."""
    data: dict = field(default_factory=dict)


class MusicSettingsCoordinator:
    """Coordinates music/Suno settings persistence and UI population."""

    def __init__(
        self,
        host: "MainWindow",
        *,
        table_populate_fn: TablePopulateFn | None = None,
        warning_fn: WarningFn | None = None,
        confirm_question_fn: ConfirmQuestionFn | None = None,
        file_dialog_fn: FileDialogFn | None = None,
    ) -> None:
        self.host = host
        self._table_populate_fn = table_populate_fn
        self._warning_fn = warning_fn
        self._confirm_question_fn = confirm_question_fn
        self._file_dialog_fn = file_dialog_fn

    # ------------------------------------------------------------------
    # Read settings from UI widgets → patch dict
    # ------------------------------------------------------------------

    def _w(self, attr: str, default: str = "") -> str:
        """Safely read widget text/currentData from host, returning stripped string or default."""
        host = self.host
        w = getattr(host, attr, None)
        if w is None:
            return str(default).strip()
        try:
            if hasattr(w, "text"):
                return str(w.text() or default).strip()
            if hasattr(w, "currentData"):
                return str(w.currentData() or default).strip()
            if hasattr(w, "value"):
                return str(w.value() or default).strip()
        except RuntimeError:
            pass
        return str(default).strip()

    def _wi(self, attr: str, default: int) -> int:
        """Safely read widget integer value from host."""
        try:
            return int(self._w(attr, str(default)) or str(default))
        except Exception:
            return default

    def gather_suno_settings_patch(self) -> dict:
        """Collect all music settings from UI widgets into a persistence-ready dict."""
        host = self.host
        raw_output_dir = self._w("music_suno_output_dir")
        try:
            normalized_output_dir = os.path.normpath(raw_output_dir) if raw_output_dir else raw_output_dir
        except Exception:
            normalized_output_dir = raw_output_dir
        return {
            # Suno access
            "sunoOutputDir": normalized_output_dir,
            "sunoCallbackUrl": self._w("music_suno_callback_url"),
            "sunoTimeoutMs": max(1000, self._wi("music_suno_timeout", 90000)),
            "sunoRetryCount": max(0, self._wi("music_suno_retry_count", 3)),
            "sunoDefaultVersion": self._w("music_suno_default_version", "v5.5"),
            "sunoMergeEnabled": self._w("music_suno_merge_enabled", "off") == "on",
            "sunoMergeGroupSize": max(0, self._wi("music_suno_merge_group_size", 0)),
            "sunoCreditsReserve": max(0, self._wi("music_suno_credits_reserve", 10)),
            "sunoCreditsCostMusic": max(0, self._wi("music_suno_credits_cost_music", 5)),
            "sunoCreditsCostLyrics": max(0, self._wi("music_suno_credits_cost_lyrics", 1)),
            # Model settings (API keys removed — managed by Platform API)
            "slaiSongModel": self._w("music_settings_slai_song_model"),
            "sunoApiBaseUrl": self._w("music_settings_suno_api_base_url"),
            "openaiApiKey": self._w("music_settings_openai_key"),
            "slaiImgModel": self._w("music_settings_slai_img_model"),
            "falImgModel": self._w("music_settings_fal_img_model", "flux-dev-i2i"),
            "youtubeClientId": self._w("music_settings_youtube_client_id"),
            "youtubeClientSecret": self._w("music_settings_youtube_client_secret"),
            # Image Provider Selection
            "imageBackgroundProvider": self._w("music_settings_image_bg_provider", "slai"),
            "imageThumbnailProvider": self._w("music_settings_image_thumb_provider", "slai"),
            # AI Providers
            "songDraftProvider": self._w("music_settings_title_album_provider", "deepseek"),
            "lyricsProvider": self._w("music_settings_lyrics_provider"),
            # Paths
            "ffmpegPath": self._w("music_settings_ffmpeg_path"),
            "downloadsDir": self._w("music_settings_downloads_dir"),
            "mergedDir": self._w("music_settings_merged_dir"),
            # Misc
            "poolsGenerateCount": max(1, self._wi("music_pools_generate_count", 1)),
            "backgroundSourceMode": self._w("music_settings_background_source_mode", "samples") or "samples",
            "thumbnailOverlayMode": self._w("music_settings_thumbnail_overlay_mode", "ai") or "ai",
            "autoUploadYouTube": self._w("music_settings_auto_upload_youtube", "off") == "on",
            "autoVideoAfterSuno": self._w("music_settings_auto_video_after_suno", "off") == "on",
            # Performance
            "perfMusicWorkers": max(1, self._wi("perf_music_workers_spin", 1)),
            "perfImageWorkers": max(1, self._wi("perf_image_workers_spin", 4)),
            "perfExportWorkers": max(1, self._wi("perf_export_workers_spin", 1)),
        }

    # ------------------------------------------------------------------
    # Write settings dict → UI widgets
    # ------------------------------------------------------------------

    def _sw(self, attr: str, value: str) -> None:
        """Safely set text on a widget attribute of host, ignoring RuntimeError if widget was deleted."""
        host = self.host
        w = getattr(host, attr, None)
        if w is None:
            return
        try:
            w.setText(str(value or ""))
        except RuntimeError:
            pass

    def populate_suno_settings_ui(self, settings: dict) -> None:
        """Populate all Suno-related music settings UI fields from a settings dict."""
        host = self.host

        self._sw("music_suno_output_dir", settings.get("sunoOutputDir", ""))
        self._sw("music_suno_callback_url", settings.get("sunoCallbackUrl", ""))
        self._sw("music_suno_timeout", str(int(settings.get("sunoTimeoutMs", 90000) or 90000)))
        self._sw("music_suno_retry_count", str(int(settings.get("sunoRetryCount", 3) or 3)))
        if hasattr(host, "music_suno_default_version"):
            version = str(settings.get("sunoDefaultVersion", "v5.5")).strip() or "v5.5"
            idx = host.music_suno_default_version.findData(version)
            host.music_suno_default_version.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_suno_merge_enabled"):
            merge_mode = "on" if bool(settings.get("sunoMergeEnabled", False)) else "off"
            idx = host.music_suno_merge_enabled.findData(merge_mode)
            host.music_suno_merge_enabled.setCurrentIndex(idx if idx >= 0 else 0)
        self._sw("music_suno_merge_group_size", str(int(settings.get("sunoMergeGroupSize", 5) or 0)))
        self._sw("music_suno_credits_reserve", str(int(settings.get("sunoCreditsReserve", 10) or 0)))
        self._sw("music_suno_credits_cost_music", str(int(settings.get("sunoCreditsCostMusic", 5) or 0)))
        self._sw("music_suno_credits_cost_lyrics", str(int(settings.get("sunoCreditsCostLyrics", 1) or 0)))
        if hasattr(host, "music_suno_prompt_prefix"):
            host.music_suno_prompt_prefix.setText(str(settings.get("sunoPromptPrefix", "")).strip())
        if hasattr(host, "music_suno_instrumental_mode"):
            inst_mode = "on" if bool(settings.get("sunoInstrumentalMode", False)) else "off"
            idx = host.music_suno_instrumental_mode.findData(inst_mode)
            host.music_suno_instrumental_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_default_profile"):
            default_profile = str(settings.get("defaultProfileId", "")).strip()
            idx = host.music_default_profile.findData(default_profile)
            host.music_default_profile.setCurrentIndex(idx if idx >= 0 else 0)

        # Path settings (were missing)
        if hasattr(host, "music_settings_ffmpeg_path"):
            host.music_settings_ffmpeg_path.setText(str(settings.get("ffmpegPath", "")).strip())
        if hasattr(host, "music_settings_downloads_dir"):
            host.music_settings_downloads_dir.setText(str(settings.get("downloadsDir", "")).strip())
        if hasattr(host, "music_settings_merged_dir"):
            host.music_settings_merged_dir.setText(str(settings.get("mergedDir", "")).strip())

        # Image settings
        if hasattr(host, "music_settings_image_provider"):
            provider = str(settings.get("imageProvider", "slai")).strip() or "slai"
            idx = host.music_settings_image_provider.findData(provider)
            host.music_settings_image_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_slai_image_model"):
            host.music_slai_image_model.setText(str(settings.get("slaiImgModel", "")).strip())
        if hasattr(host, "music_image_output_dir"):
            host.music_image_output_dir.setText(str(settings.get("imageOutputDir", "")).strip())
        if hasattr(host, "music_image_max_concurrent"):
            host.music_image_max_concurrent.setText(str(int(settings.get("imageMaxConcurrent", 1) or 1)))
        if hasattr(host, "music_image_timeout"):
            host.music_image_timeout.setText(str(int(settings.get("imageTimeoutMs", 60000) or 60000)))
        if hasattr(host, "music_image_retry_count"):
            host.music_image_retry_count.setText(str(int(settings.get("imageRetryCount", 2) or 2)))
        if hasattr(host, "music_image_upload_to_s3"):
            upload_mode = "on" if bool(settings.get("imageUploadToS3", False)) else "off"
            idx = host.music_image_upload_to_s3.findData(upload_mode)
            host.music_image_upload_to_s3.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_image_upload_s3_bucket"):
            host.music_image_upload_s3_bucket.setText(str(settings.get("imageUploadS3Bucket", "")).strip())
        if hasattr(host, "music_image_upload_s3_key_prefix"):
            host.music_image_upload_s3_key_prefix.setText(str(settings.get("imageUploadS3KeyPrefix", "")).strip())
        if hasattr(host, "music_image_s3_region"):
            host.music_image_s3_region.setText(str(settings.get("imageS3Region", "us-east-1")).strip() or "us-east-1")

        # Video settings
        if hasattr(host, "music_settings_video_template"):
            host.music_settings_video_template.setText(str(settings.get("videoTemplateId", "")).strip())
        if hasattr(host, "music_settings_video_output_dir"):
            host.music_settings_video_output_dir.setText(str(settings.get("videoOutputDir", "")).strip())
        if hasattr(host, "music_settings_video_max_concurrent"):
            host.music_settings_video_max_concurrent.setText(str(int(settings.get("videoMaxConcurrent", 1) or 1)))
        if hasattr(host, "music_settings_video_timeout"):
            host.music_settings_video_timeout.setText(str(int(settings.get("videoTimeoutMs", 120000) or 120000)))
        if hasattr(host, "music_settings_video_retry_count"):
            host.music_settings_video_retry_count.setText(str(int(settings.get("videoRetryCount", 2) or 2)))
        if hasattr(host, "music_settings_video_upload_to_s3"):
            upload_mode = "on" if bool(settings.get("videoUploadToS3", False)) else "off"
            idx = host.music_settings_video_upload_to_s3.findData(upload_mode)
            host.music_settings_video_upload_to_s3.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_video_upload_s3_bucket"):
            host.music_settings_video_upload_s3_bucket.setText(str(settings.get("videoUploadS3Bucket", "")).strip())
        if hasattr(host, "music_settings_video_upload_s3_key_prefix"):
            host.music_settings_video_upload_s3_key_prefix.setText(str(settings.get("videoUploadS3KeyPrefix", "")).strip())
        if hasattr(host, "music_settings_video_s3_region"):
            host.music_settings_video_s3_region.setText(str(settings.get("videoS3Region", "us-east-1")).strip() or "us-east-1")
        if hasattr(host, "music_settings_video_background_path"):
            host.music_settings_video_background_path.setText(str(settings.get("videoBackgroundPath", "")).strip())
        if hasattr(host, "music_settings_video_logo_path"):
            host.music_settings_video_logo_path.setText(str(settings.get("videoLogoPath", "")).strip())
        if hasattr(host, "music_settings_video_mp3_dir"):
            host.music_settings_video_mp3_dir.setText(str(settings.get("videoMp3Dir", "")).strip())
        if hasattr(host, "music_settings_video_export_workers_spin"):
            val = max(1, min(10, int(settings.get("videoExportWorkers", 1) or 1)))
            host.music_settings_video_export_workers_spin.blockSignals(True)
            host.music_settings_video_export_workers_spin.setValue(val)
            host.music_settings_video_export_workers_spin.blockSignals(False)
        if hasattr(host, "music_settings_video_speed_mode"):
            mode = str(settings.get("videoExportSpeedMode", "balanced")).strip() or "balanced"
            idx = host.music_settings_video_speed_mode.findData(mode)
            host.music_settings_video_speed_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_video_auto_merge"):
            auto_merge = "on" if bool(settings.get("videoAutoMergeMp4", False)) else "off"
            idx = host.music_settings_video_auto_merge.findData(auto_merge)
            host.music_settings_video_auto_merge.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_merge_output_dir"):
            host.music_settings_merge_output_dir.setText(str(settings.get("mergeOutputDir", "")).strip())
        if hasattr(host, "music_settings_merge_workers_spin"):
            val = max(1, min(4, int(settings.get("mergeWorkers", 1) or 1)))
            host.music_settings_merge_workers_spin.blockSignals(True)
            host.music_settings_merge_workers_spin.setValue(val)
            host.music_settings_merge_workers_spin.blockSignals(False)

        # YouTube settings
        if hasattr(host, "music_settings_youtube_client_id"):
            host.music_settings_youtube_client_id.setText(str(settings.get("youtubeClientId", "")).strip())
        if hasattr(host, "music_settings_youtube_client_secret"):
            host.music_settings_youtube_client_secret.setText(str(settings.get("youtubeClientSecret", "")).strip())

        # API Keys (removed — now managed by Platform API)
        # Only populate model settings and non-AI-service keys
        if hasattr(host, "music_settings_slai_song_model"):
            host.music_settings_slai_song_model.setText(str(settings.get("slaiSongModel", "") or ""))
        if hasattr(host, "music_settings_openai_key"):
            host.music_settings_openai_key.setText(str(settings.get("openaiApiKey", "") or ""))
        if hasattr(host, "music_settings_slai_img_model"):
            host.music_settings_slai_img_model.setText(str(settings.get("slaiImgModel", "") or ""))
        if hasattr(host, "music_settings_fal_img_model"):
            fal_model = str(settings.get("falImgModel", "flux-dev-i2i")).strip() or "flux-dev-i2i"
            idx = host.music_settings_fal_img_model.findData(fal_model)
            host.music_settings_fal_img_model.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_image_bg_provider"):
            provider = str(settings.get("imageBackgroundProvider", "slai")).strip() or "slai"
            idx = host.music_settings_image_bg_provider.findData(provider)
            host.music_settings_image_bg_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_image_thumb_provider"):
            provider = str(settings.get("imageThumbnailProvider", "slai")).strip() or "slai"
            idx = host.music_settings_image_thumb_provider.findData(provider)
            host.music_settings_image_thumb_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_suno_api_base_url"):
            host.music_settings_suno_api_base_url.setText(str(settings.get("sunoApiBaseUrl", "")).strip())
        if hasattr(host, "music_settings_youtube_client_id"):
            host.music_settings_youtube_client_id.setText(str(settings.get("youtubeClientId", "")).strip())
        if hasattr(host, "music_settings_youtube_client_secret"):
            host.music_settings_youtube_client_secret.setText(str(settings.get("youtubeClientSecret", "")).strip())
        if hasattr(host, "music_suno_default_version"):
            version = str(settings.get("sunoDefaultVersion", "v5.5")).strip() or "v5.5"
            idx = host.music_suno_default_version.findData(version)
            host.music_suno_default_version.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_suno_merge_enabled"):
            merge_mode = "on" if bool(settings.get("sunoMergeEnabled", False)) else "off"
            idx = host.music_suno_merge_enabled.findData(merge_mode)
            host.music_suno_merge_enabled.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_suno_merge_group_size"):
            host.music_suno_merge_group_size.setText(str(int(settings.get("sunoMergeGroupSize", 5) or 0)))
        if hasattr(host, "music_suno_credits_reserve"):
            host.music_suno_credits_reserve.setText(str(int(settings.get("sunoCreditsReserve", 10) or 0)))
        if hasattr(host, "music_suno_credits_cost_music"):
            host.music_suno_credits_cost_music.setText(str(int(settings.get("sunoCreditsCostMusic", 5) or 0)))
        if hasattr(host, "music_suno_credits_cost_lyrics"):
            host.music_suno_credits_cost_lyrics.setText(str(int(settings.get("sunoCreditsCostLyrics", 1) or 0)))
        if hasattr(host, "music_suno_max_concurrent"):
            host.music_suno_max_concurrent.setText(str(int(settings.get("sunoMaxConcurrent", 1) or 1)))
        if hasattr(host, "music_suno_upload_to_s3"):
            upload_mode = "on" if bool(settings.get("sunoUploadToS3", False)) else "off"
            idx = host.music_suno_upload_to_s3.findData(upload_mode)
            host.music_suno_upload_to_s3.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_suno_upload_s3_bucket"):
            host.music_suno_upload_s3_bucket.setText(str(settings.get("sunoUploadS3Bucket", "")).strip())
        if hasattr(host, "music_suno_upload_s3_key_prefix"):
            host.music_suno_upload_s3_key_prefix.setText(str(settings.get("sunoUploadS3KeyPrefix", "")).strip())
        if hasattr(host, "music_suno_s3_region"):
            host.music_suno_s3_region.setText(str(settings.get("sunoS3Region", "us-east-1")).strip() or "us-east-1")
        if hasattr(host, "music_song_draft_provider"):
            provider = str(settings.get("songDraftProvider", "deepseek")).strip() or "deepseek"
            idx = host.music_song_draft_provider.findData(provider)
            host.music_song_draft_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_lyrics_provider"):
            lyrics_provider = str(settings.get("lyricsProvider", "")).strip() or ""
            idx = host.music_lyrics_provider.findData(lyrics_provider)
            host.music_lyrics_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_openai_api_key"):
            host.music_openai_api_key.setText(str(settings.get("openaiApiKey", "")).strip())
        if hasattr(host, "music_openai_lyrics_model"):
            model = str(settings.get("openaiLyricsModel", "gpt-4o-mini")).strip() or "gpt-4o-mini"
            idx = host.music_openai_lyrics_model.findData(model)
            host.music_openai_lyrics_model.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_deepseek_lyrics_model"):
            model = str(settings.get("deepseekLyricsModel", "deepseek-chat")).strip() or "deepseek-chat"
            idx = host.music_deepseek_lyrics_model.findData(model)
            host.music_deepseek_lyrics_model.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_default_song_count"):
            host.music_default_song_count.setText(str(int(settings.get("defaultSongCount", 1) or 1)))
        if hasattr(host, "music_suno_default_mode"):
            mode = str(settings.get("sunoDefaultMode", "custom")).strip() or "custom"
            idx = host.music_suno_default_mode.findData(mode)
            host.music_suno_default_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_suno_default_tags"):
            host.music_suno_default_tags.setText(str(settings.get("sunoDefaultTags", "")).strip())
        if hasattr(host, "music_suno_prompt_prefix"):
            host.music_suno_prompt_prefix.setText(str(settings.get("sunoPromptPrefix", "")).strip())
        if hasattr(host, "music_suno_instrumental_mode"):
            inst_mode = "on" if bool(settings.get("sunoInstrumentalMode", False)) else "off"
            idx = host.music_suno_instrumental_mode.findData(inst_mode)
            host.music_suno_instrumental_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_default_profile"):
            default_profile = str(settings.get("defaultProfileId", "")).strip()
            idx = host.music_default_profile.findData(default_profile)
            host.music_default_profile.setCurrentIndex(idx if idx >= 0 else 0)

    def populate_performance_settings_ui(self, settings: dict) -> None:
        """Populate performance-related settings UI fields."""
        host = self.host
        if hasattr(host, "perf_video_export_workers_spin"):
            val = max(1, min(10, int(settings.get("videoExportWorkers", 1) or 1)))
            host.perf_video_export_workers_spin.blockSignals(True)
            host.perf_video_export_workers_spin.setValue(val)
            host.perf_video_export_workers_spin.blockSignals(False)
        if hasattr(host, "perf_export_workers_spin"):
            val = max(1, min(10, int(settings.get("videoExportWorkers", 1) or 1)))
            host.perf_export_workers_spin.blockSignals(True)
            host.perf_export_workers_spin.setValue(val)
            host.perf_export_workers_spin.blockSignals(False)
        if hasattr(host, "perf_merge_workers_spin"):
            val = max(1, min(2, int(settings.get("perfMergeWorkers", 1) or 1)))
            host.perf_merge_workers_spin.blockSignals(True)
            host.perf_merge_workers_spin.setValue(val)
            host.perf_merge_workers_spin.blockSignals(False)
        if hasattr(host, "perf_youtube_workers_spin"):
            val = max(1, min(5, int(settings.get("perfYouTubeWorkers", 1) or 1)))
            host.perf_youtube_workers_spin.blockSignals(True)
            host.perf_youtube_workers_spin.setValue(val)
            host.perf_youtube_workers_spin.blockSignals(False)
        if hasattr(host, "youtube_upload_chunk_spin"):
            val = int(settings.get("youtubeUploadChunkSizeMb", 256) or 256)
            val = max(8, min(512, int(round(float(val) / 8.0) * 8)))
            host.youtube_upload_chunk_spin.blockSignals(True)
            host.youtube_upload_chunk_spin.setValue(val)
            host.youtube_upload_chunk_spin.blockSignals(False)

    def populate_misc_settings_ui(self, settings: dict) -> None:
        """Populate miscellaneous music settings UI fields."""
        host = self.host
        if hasattr(host, "music_settings_background_source_mode"):
            mode = str(settings.get("backgroundSourceMode", "samples")).strip() or "samples"
            idx = host.music_settings_background_source_mode.findData(mode)
            host.music_settings_background_source_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_thumbnail_overlay_mode"):
            mode = str(settings.get("thumbnailOverlayMode", "ai")).strip() or "ai"
            idx = host.music_settings_thumbnail_overlay_mode.findData(mode)
            host.music_settings_thumbnail_overlay_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_pools_generate_count"):
            host.music_pools_generate_count.setText(str(int(settings.get("poolsGenerateCount", 1) or 1)))
        if hasattr(host, "music_settings_auto_video_after_suno"):
            mode = "on" if bool(settings.get("autoVideoAfterSuno", False)) else "off"
            idx = host.music_settings_auto_video_after_suno.findData(mode)
            host.music_settings_auto_video_after_suno.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(host, "music_settings_auto_upload_youtube"):
            mode = "on" if bool(settings.get("autoUploadYouTube", False)) else "off"
            idx = host.music_settings_auto_upload_youtube.findData(mode)
            host.music_settings_auto_upload_youtube.setCurrentIndex(idx if idx >= 0 else 0)

    def on_music_test_db_clicked(self) -> None:
        host = self.host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            host._set_music_settings_status("Database test failed: configure .env first")
            return
        result = test_db_connection(cfg)
        host._set_music_settings_status(str(result.get("message", "")).strip())
        if bool(result.get("ok", False)):
            host._set_music_status(str(result.get("message", "")).strip())

    def on_music_migrate_db_clicked(self) -> None:
        host = self.host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            host._set_music_settings_status("Migration failed: configure .env first")
            return
        result = host.persistence_coordinator.migrate_database(cfg)
        host._set_music_settings_status(str(result.get("message", "")).strip())
        if bool(result.get("ok", False)):
            self.refresh_music_pool_stats()
            self.refresh_music_pool_table()
            host._set_music_status(str(result.get("message", "")).strip())

    def music_current_pool_kind(self) -> str:
        host = self.host
        if hasattr(host, "music_pools_kind_tabs"):
            idx = int(host.music_pools_kind_tabs.currentIndex())
            return ["openings", "titles", "albums"][idx] if 0 <= idx < 3 else "openings"
        return "openings"

    def refresh_music_pool_stats(self, force: bool = False) -> None:
        host = self.host
        if getattr(host, "_current_primary_page", "") != "settings" or str(host.music_settings_tabs.tabText(host.music_settings_tabs.currentIndex()) or "").strip().lower() != "pools":
            if not force:
                host._music_pools_dirty = True
                return
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            host._music_pool_stats = {}
            for prefix in ("music_pools", "music_settings"):
                for kind in ("openings", "titles", "albums"):
                    unused_label = getattr(host, f"{prefix}_{kind}_unused", None)
                    total_label = getattr(host, f"{prefix}_{kind}_total", None)
                    if unused_label is not None:
                        unused_label.setText("—")
                    if total_label is not None:
                        total_label.setText("Total —")
            if hasattr(host, "music_pools_db_label"):
                host.music_pools_db_label.setText("Not configured")
            return
        try:
            stats = music_pools_stats(cfg)
        except Exception as exc:
            host._set_music_pools_status(f"Pool stats failed: {exc}")
            host._set_music_settings_status(f"Pool stats failed: {exc}")
            return
        host._music_pool_stats = stats
        for prefix in ("music_pools", "music_settings"):
            for kind in ("openings", "titles", "albums"):
                unused_label = getattr(host, f"{prefix}_{kind}_unused", None)
                total_label = getattr(host, f"{prefix}_{kind}_total", None)
                if unused_label is not None:
                    unused_label.setText(str(int(((stats.get(kind) or {}).get("unused", 0) or 0))))
                if total_label is not None:
                    total_label.setText(f"Total {int(((stats.get(kind) or {}).get('total', 0) or 0))}")
        if hasattr(host, "music_pools_db_label"):
            host.music_pools_db_label.setText(f"{cfg.user}@{cfg.host}:{cfg.port}/{cfg.database}")
        host._set_music_settings_status("Phrase pool stats refreshed")

    def refresh_music_pool_table(self, force: bool = False) -> None:
        host = self.host
        if not hasattr(host, "music_pools_table"):
            return
        if getattr(host, "_current_primary_page", "") != "settings" or str(host.music_settings_tabs.tabText(host.music_settings_tabs.currentIndex()) or "").strip().lower() != "pools":
            if not force:
                host._music_pools_dirty = True
                return
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            host._set_music_pools_status("Pools unavailable: configure Database settings first")
            host.music_pools_table.blockSignals(True)
            host.music_pools_table.clearContents()
            host.music_pools_table.setRowCount(0)
            host.music_pools_table.blockSignals(False)
            if hasattr(host, "music_pools_preview"):
                host.music_pools_preview.clear()
            if hasattr(host, "music_pools_page_label"):
                host.music_pools_page_label.setText("Page 1 / 1")
            return
        kind = self.music_current_pool_kind()
        limit = max(10, min(500, int(getattr(host, "_music_pools_page_size", 100) or 100)))
        offset = max(0, int(getattr(host, "_music_pools_page", 0) or 0)) * limit
        from ...database.music_pools import list_pool as music_list_pool
        result = music_list_pool(cfg, kind, limit, offset)
        rows = list(result.get("rows") or [])
        host._music_pools_rows = rows
        selected_id = str(getattr(host, "_music_pools_selected_id", "") or "").strip()
        table = host.music_pools_table
        table.blockSignals(True)
        if kind == "openings":
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["ID", "Used", "Line 1", "Line 2"])
        else:
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["ID", "Used", "Text"])
        table.setRowCount(len(rows))
        table_rows: list[list[tuple[int, str, str]]] = []
        for row_idx, row in enumerate(rows):
            values = (
                [str(row.get("id", "")), str(row.get("usedCount", 0)), str(row.get("line1", "")), str(row.get("line2", ""))]
                if kind == "openings"
                else [str(row.get("id", "")), str(row.get("usedCount", 0)), str(row.get("text", ""))]
            )
            row_data: list[tuple[int, str, str]] = []
            for col_idx, value in enumerate(values):
                row_data.append((col_idx, value, str(row.get("id", "")).strip()))
            table_rows.append(row_data)
            if str(row.get("id", "")).strip() == selected_id:
                table.selectRow(row_idx)
        if self._table_populate_fn is not None:
            self._table_populate_fn(table_rows)
        if rows and not selected_id:
            host._music_pools_selected_id = str(rows[0].get("id", "")).strip()
            table.selectRow(0)
        table.blockSignals(False)
        total_for_tab = int((((getattr(host, "_music_pool_stats", {}) or {}).get(kind) or {}).get("total", 0) or 0))
        total_pages = max(1, (total_for_tab + limit - 1) // limit)
        current_page = min(total_pages, int(getattr(host, "_music_pools_page", 0) or 0) + 1)
        if hasattr(host, "music_pools_page_label"):
            host.music_pools_page_label.setText(f"Page {current_page} / {total_pages}")
        self.refresh_music_pool_preview()

    def refresh_music_pool_preview(self) -> None:
        host = self.host
        rows = list(getattr(host, "_music_pools_rows", []) or [])
        selected_id = str(getattr(host, "_music_pools_selected_id", "") or "").strip()
        current = None
        for row in rows:
            if str((row or {}).get("id", "")).strip() == selected_id:
                current = row
                break
        text = ""
        if isinstance(current, dict):
            if self.music_current_pool_kind() == "openings":
                text = f"{str(current.get('line1', '')).strip()}\n{str(current.get('line2', '')).strip()}".strip()
            else:
                text = str(current.get("text", "")).strip()
        if hasattr(host, "music_pools_preview"):
            host.music_pools_preview.setPlainText(text)

    def on_music_pool_row_selected(self) -> None:
        host = self.host
        row = int(host.music_pools_table.currentRow()) if hasattr(host, "music_pools_table") else -1
        rows = list(getattr(host, "_music_pools_rows", []) or [])
        if 0 <= row < len(rows):
            host._music_pools_selected_id = str((rows[row] or {}).get("id", "")).strip()
            self.refresh_music_pool_preview()

    def on_music_pool_kind_changed(self) -> None:
        host = self.host
        host._music_pools_page = 0
        host._music_pools_selected_id = ""
        self.refresh_music_pool_table()

    def on_music_pool_prev_page(self) -> None:
        host = self.host
        host._music_pools_page = max(0, int(getattr(host, "_music_pools_page", 0) or 0) - 1)
        self.refresh_music_pool_table()

    def on_music_pool_next_page(self) -> None:
        host = self.host
        host._music_pools_page = max(0, int(getattr(host, "_music_pools_page", 0) or 0) + 1)
        self.refresh_music_pool_table()

    def on_music_pool_generate(self) -> None:
        host = self.host
        kind = self.music_current_pool_kind()
        count = max(1, int(host.music_pools_generate_count.text() or "10000")) if hasattr(host, "music_pools_generate_count") else 10000
        ok, msg = host._music_coordinator.generate_pool(kind, count)
        if ok:
            host._music_pools_dirty = False
            self.refresh_music_pool_stats(force=True)
            self.refresh_music_pool_table(force=True)
            host._set_music_pools_status(msg)
        else:
            if self._warning_fn is not None:
                self._warning_fn("Pools", msg)
            host._set_music_pools_status(f"Generate failed: {msg}")

    def on_music_pool_import(self, kind: str | None = None) -> None:
        host = self.host
        pool_kind = str(kind or self.music_current_pool_kind())
        if self._file_dialog_fn is None:
            return
        file_path = self._file_dialog_fn("Select a text file", "Text Files (*.txt *.csv);;All Files (*)")
        if not file_path:
            return
        ok, msg = host._music_coordinator.import_pool(pool_kind, file_path)
        if ok:
            host._music_pools_dirty = False
            self.refresh_music_pool_stats(force=True)
            self.refresh_music_pool_table(force=True)
            host._set_music_pools_status(msg)
        else:
            if self._warning_fn is not None:
                self._warning_fn("Pools", msg)
            host._set_music_pools_status(f"Import failed: {msg}")

    def on_music_pool_clear(self, kind: str | None = None) -> None:
        host = self.host
        pool_kind = str(kind or self.music_current_pool_kind())
        if self._confirm_question_fn is None:
            return
        if not self._confirm_question_fn("Pools", f"Delete all rows from {pool_kind}?"):
            return
        ok, msg = host._music_coordinator.clear_pool(pool_kind)
        if ok:
            host._music_pools_dirty = False
            self.refresh_music_pool_stats(force=True)
            self.refresh_music_pool_table(force=True)
            host._set_music_pools_status(msg)
        else:
            if self._warning_fn is not None:
                self._warning_fn("Pools", msg)
