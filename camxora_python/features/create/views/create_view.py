"""Create workspace page inside the existing desktop shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QSplitter, QVBoxLayout, QWidget

from features.create.constants import FILES_PANEL_MIN_WIDTH, FORM_SPLIT_RATIO
from features.create.create_styles import build_create_page_qss
from features.create.services.audio_service import AudioService
from features.create.widgets.create_form import CreateForm
from features.create.widgets.create_header import CreateHeader
from features.create.widgets.file_panel import FilePanel
from features.create.widgets.planning_bar import PlanningBar
from features.create.workers.create_generate_worker import (
    CreateClipDownloadWorker,
    CreateGenerateResult,
    CreateGenerateWorker,
    CreateHistoryWorker,
)
from features.video.services.video_local_store import VideoLocalStore
from shared.lib.create_generate import (
    CreateGeneratePlan,
    planned_day_count,
    planned_song_count,
    validate_create_plan,
)
from shared.lib.music_composer import get_inclusive_day_span
from shared.lib.ui_font import ensure_khmer_siemreap_loaded, studio_font
from shared.services.app_logger import log_error, log_info
from shared.services.platform_api import PlatformApi
from shared.services.shell_status import clear_footer_error, emit_footer_error, emit_shell_status
from shared.services.workspace_cache import WorkspaceCache
from shared.workers.data_workers import MusicLanguagesWorker


class CreateView(QWidget):
    """Studio Create chrome wired to web-music generate / history / download."""

    def __init__(
        self,
        api: PlatformApi | None = None,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("create_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ensure_khmer_siemreap_loaded()
        self.setStyleSheet(build_create_page_qss())
        self.setFont(studio_font(12))
        self._api = api
        self._cache = cache
        self._audio = AudioService(self)
        self._generate_worker: CreateGenerateWorker | None = None
        self._history_worker: CreateHistoryWorker | None = None
        self._download_worker: CreateClipDownloadWorker | None = None
        self._last_plan: CreateGeneratePlan | None = None
        self._language_worker: MusicLanguagesWorker | None = None
        self._language_options: list[tuple[str, str]] = [("en", "English")]

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.page_header = CreateHeader()
        self.planning = PlanningBar()
        root.addWidget(self.page_header)
        root.addWidget(self.planning)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(10)
        self.form = CreateForm()
        self.files = FilePanel()
        self.form.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.files.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.form.setMinimumWidth(420)
        self.files.setMinimumWidth(FILES_PANEL_MIN_WIDTH)
        self.splitter.addWidget(self.form)
        self.splitter.addWidget(self.files)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 6)
        self.splitter.setStretchFactor(1, 4)
        root.addWidget(self.splitter, 1)
        self._apply_split_ratio()

        self.planning.changed.connect(self._on_planning_changed)
        self.form.generate_requested.connect(self._on_generate)
        self.form.folder_changed.connect(self.files.set_folder)
        self.files.download_requested.connect(self._on_download_clip)
        self.files.retry_download_requested.connect(self._on_retry_download)
        self.files.retry_song_requested.connect(self._on_retry_song)
        self.files.refresh_requested.connect(self._refresh_history)
        self.files.track_selected.connect(lambda title: self._audio.set_track(title, ""))
        self.files.play_requested.connect(self._on_play_requested)
        self.files.player.play_clicked.connect(self._on_play_clicked)
        self.files.player.stop_clicked.connect(self._audio.stop)
        self.files.player.back_clicked.connect(lambda: self.files.select_relative(-1))
        self.files.player.next_clicked.connect(lambda: self.files.select_relative(1))
        self.files.player.seeked.connect(self._audio.seek)
        self._audio.track_changed.connect(self.files.player.set_track)
        self._audio.playing_changed.connect(self.files.player.set_playing)
        self._audio.position_changed.connect(self.files.player.set_position)
        self._audio.finished.connect(lambda: self.files.select_relative(1))
        self._bootstrap_language_options_from_cache()
        self._reload_video_templates()
        self._on_planning_changed()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_split_ratio()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_split_ratio()

    def activate_page(self) -> None:
        self.refresh_language_options()
        self._reload_video_templates()
        self._on_planning_changed()
        folder = self.form.save_folder()
        if folder:
            self.files.set_folder(folder)
        self._refresh_history()

    def deactivate_page(self) -> None:
        return

    def _apply_split_ratio(self) -> None:
        width = self.splitter.width()
        if width <= 1:
            return
        form = int(round(width * FORM_SPLIT_RATIO / 100))
        self.splitter.setSizes([form, width - form])

    def _bootstrap_language_options_from_cache(self) -> None:
        if self._cache is None:
            return
        cached = self._cache.get_language_options()
        if cached:
            self._apply_language_options(cached)

    def refresh_language_options(self) -> None:
        if self._api is None:
            return
        if self._language_worker is not None and self._language_worker.isRunning():
            return
        worker = MusicLanguagesWorker(self._api, self)
        worker.succeeded.connect(self._on_language_options_loaded)
        worker.failed.connect(lambda _message: None)
        worker.finished.connect(lambda: setattr(self, "_language_worker", None))
        self._language_worker = worker
        worker.start()

    def _on_language_options_loaded(self, payload: object) -> None:
        if not isinstance(payload, list) or not payload:
            return
        options: list[tuple[str, str]] = []
        for item in payload:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                code = str(item[0] or "").strip()
                label = str(item[1] or "").strip()
                if code and label:
                    options.append((code, label))
        if not options:
            return
        if self._cache is not None:
            self._cache.apply_warmup(language_options=options)
        self._apply_language_options(options)

    def _apply_language_options(self, options: list[tuple[str, str]]) -> None:
        self._language_options = list(options)
        self.planning.set_language_options(self._language_options)

    def _reload_video_templates(self) -> None:
        try:
            templates = VideoLocalStore().read_templates()
        except Exception:
            templates = []
        options: list[tuple[str, str]] = []
        for item in templates:
            template_id = str(item.get("id") or "").strip()
            if not template_id:
                continue
            name = str(item.get("name") or "").strip() or template_id
            options.append((template_id, name))
        self.form.set_video_templates(options)

    def _on_planning_changed(self) -> None:
        values = self.planning.values()
        from_date = str(values.get("from_date") or "")
        to_date = str(values.get("to_date") or "")
        days = get_inclusive_day_span(from_date, to_date)
        if not days:
            self.page_header.set_meta("Invalid date range")
            return
        count = int(values.get("song_count") or 0)
        songs = count * days
        day_label = "1 planned day" if days == 1 else f"{days} planned days"
        song_label = "1 song" if songs == 1 else f"{songs} songs"
        self.page_header.set_meta(f"{day_label} · {song_label}")

    def _current_plan(self) -> CreateGeneratePlan:
        values = self.planning.values()
        from_date = str(values.get("from_date") or "")
        to_date = str(values.get("to_date") or "")
        mode = self.form.mode()
        songs_per_day = int(values.get("song_count") or 0)
        return CreateGeneratePlan(
            mode=mode,
            model=self.form.model_code(),
            title=self.form.title_text(),
            lyrics=self.form.lyrics_text(),
            styles=self.form.styles_text(),
            prompt=self.form.styles_text() if mode == "simple" else "",
            negative_tags=self.form.negative_tags(),
            vocal_gender=self.form.vocal_gender(),
            style_weight=self.form.style_weight(),
            weirdness=self.form.weirdness_value(),
            audio_weight=self.form.audio_weight_value(),
            song_count=planned_song_count(songs_per_day, from_date, to_date),
            songs_per_day=max(0, songs_per_day),
            planned_days=planned_day_count(from_date, to_date),
            save_folder=self.form.save_folder(),
            version_mode=self.form.version_mode(),
            language=str(values.get("language") or "en"),
            secondary_language=str(values.get("secondary_language") or ""),
            auto_image=self.form.auto_image.isChecked(),
            auto_video=self.form.auto_video.isChecked(),
            auto_merge=self.form.auto_merge.isChecked(),
            download_wav=self.form.download_wav.isChecked(),
            download_lrc=self.form.download_lrc.isChecked(),
            download_srt=self.form.download_srt.isChecked(),
            template_v1_id=self.form.template_v1_id(),
            template_v2_id=self.form.template_v2_id(),
        )

    def _on_generate(self) -> None:
        if self._api is None:
            self._show_error("Sign in to generate songs.")
            return
        if self._generate_worker is not None and self._generate_worker.isRunning():
            return
        plan = self._current_plan()
        error = validate_create_plan(plan)
        if error:
            self._show_error(error)
            return
        clear_footer_error()
        self.form.set_generating(True)
        self.form.set_status(
            f"Generating {plan.song_count} song{'s' if plan.song_count != 1 else ''}…"
        )
        self._last_plan = plan
        self.files.begin_generate(plan.song_count, plan.title)
        worker = CreateGenerateWorker(self._api, plan, parent=self)
        self._bind_generate_worker(worker)
        self._generate_worker = worker
        log_info(
            f"Create Generate Music → POST /web-music/generate × {plan.song_count}",
            category="create",
        )
        worker.start()

    def _bind_generate_worker(self, worker: CreateGenerateWorker) -> None:
        worker.progressed.connect(self.form.set_status)
        worker.song_started.connect(self.files.update_pending_title)
        worker.song_submitted.connect(self.files.attach_task)
        worker.song_saved.connect(self.files.mark_ready)
        worker.song_failed.connect(self.files.mark_failed)
        worker.files_changed.connect(self.files.refresh)
        worker.draft_ready.connect(self._on_draft_ready)
        worker.succeeded.connect(self._on_generate_finished)
        worker.failed.connect(self._on_generate_failed)
        worker.finished.connect(self._finish_generate_worker)

    def _busy(self) -> bool:
        generate_busy = self._generate_worker is not None and self._generate_worker.isRunning()
        download_busy = self._download_worker is not None and self._download_worker.isRunning()
        return generate_busy or download_busy

    def _on_download_clip(
        self,
        task_id: str,
        title: str,
        kind: str,
        variant: str,
        folder: str,
    ) -> None:
        if self._api is None:
            self._show_error("Sign in to download files.")
            return
        if self._busy():
            return
        dest = (folder or "").strip()
        if not dest:
            self._show_error("Choose a download folder.")
            return
        emit_shell_status(f"Downloading {kind.upper()} for {title or 'song'}…")
        worker = CreateClipDownloadWorker(
            self._api,
            dest,
            task_id,
            title,
            kind,
            variant,
            parent=self,
        )
        worker.progressed.connect(emit_shell_status)
        worker.file_saved.connect(self.files.mark_file)
        worker.succeeded.connect(self._on_download_finished)
        worker.failed.connect(self._on_generate_failed)
        worker.finished.connect(lambda: setattr(self, "_download_worker", None))
        self._download_worker = worker
        log_info(
            f"Create download {kind} task={task_id} variant={variant} (no new Suno charge)",
            category="create",
        )
        worker.start()

    def _on_download_finished(self, path: object) -> None:
        clear_footer_error()
        emit_shell_status(f"Saved {path}", tone="success")
        self.files.refresh()

    def _on_retry_download(self, index: int, task_id: str, title: str) -> None:
        if self._api is None or self._busy():
            return
        plan = self._last_plan or self._current_plan()
        self.files.attach_task(index, task_id, title)
        self.form.set_generating(True)
        self.form.set_status(f"Retrying download for {title or f'song {index}'}…")
        worker = CreateGenerateWorker(
            self._api,
            plan,
            parent=self,
            only_index=index,
            existing_task_id=task_id,
            retry_title=title,
        )
        self._bind_generate_worker(worker)
        self._generate_worker = worker
        log_info(
            f"Create retry download task={task_id} song={index} (no new Suno charge)",
            category="create",
        )
        worker.start()

    def _on_retry_song(self, index: int) -> None:
        if self._api is None or self._busy():
            return
        plan = self._current_plan()
        error = validate_create_plan(plan)
        if error:
            self._show_error(error)
            return
        self._last_plan = plan
        self.form.set_generating(True)
        self.form.set_status(f"Retrying song {index} (new Suno job)…")
        worker = CreateGenerateWorker(self._api, plan, parent=self, only_index=index)
        self._bind_generate_worker(worker)
        self._generate_worker = worker
        log_info(f"Create retry generate song={index}", category="create")
        worker.start()

    def _on_draft_ready(self, title: str, lyrics: str) -> None:
        if title:
            self.form.set_title(title)
        if lyrics:
            self.form.set_lyrics(lyrics)

    def _on_generate_finished(self, payload: object) -> None:
        result = payload if isinstance(payload, CreateGenerateResult) else None
        saved = result.saved if result else 0
        if result and result.last_title:
            self.form.set_title(result.last_title)
        if result and result.last_lyrics:
            self.form.set_lyrics(result.last_lyrics)
        self.files.refresh()
        clear_footer_error()
        self.form.set_status(
            f"Saved {saved} song{'s' if saved != 1 else ''} to Version 1/ and Version 2/. "
            "Same tracks are in your web Create workspace."
        )
        log_info(f"Create generate finished: {saved} song(s)", category="create")

    def _on_generate_failed(self, message: str) -> None:
        self._show_error(message)
        log_error(message, category="create")

    def _finish_generate_worker(self) -> None:
        self._generate_worker = None
        self.form.set_generating(False)
        self._refresh_history()

    def _refresh_history(self) -> None:
        if self._api is None or self._busy():
            return
        if self._history_worker is not None and self._history_worker.isRunning():
            return
        worker = CreateHistoryWorker(self._api, self)
        worker.succeeded.connect(self._on_history_loaded)
        worker.failed.connect(self._on_history_failed)
        worker.finished.connect(lambda: setattr(self, "_history_worker", None))
        self._history_worker = worker
        worker.start()

    def _on_history_loaded(self, payload: object) -> None:
        if not isinstance(payload, list):
            return
        self.files.set_history(payload)

    def _on_history_failed(self, message: str) -> None:
        if message:
            log_error(message, category="create")

    def _on_play_requested(self, path: str) -> None:
        self._audio.set_track(self.files.current_title(), path)
        self._audio.player.play()

    def _on_play_clicked(self) -> None:
        if self._audio.player.source().isEmpty():
            self.files.play_current()
            return
        self._audio.toggle()

    def _show_error(self, message: str) -> None:
        emit_footer_error(message)
        self.form.set_status("")
