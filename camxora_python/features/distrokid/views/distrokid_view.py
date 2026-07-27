"""DistroKid workspace — entitlement, Connect, settings, and local history."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from features.distrokid.lib.distrokid_settings import DistroKidSettings, DistroKidSettingsStore
from features.distrokid.lib.upload_history import UploadHistory
from features.distrokid.workers.distrokid_connect_worker import DistroKidConnectWorker
from shared.models.auth import ProfileResponse
from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class DistroKidView(QFrame):
    """DistroKid add-on status, Connect DistroKid, form defaults, upload history."""

    def __init__(self, api: PlatformApi | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._store = DistroKidSettingsStore()
        self._settings = self._store.load()
        self._active = False
        self._connect_worker: DistroKidConnectWorker | None = None
        self._profiles: list[ProfileResponse] = []
        self._channel_artist_inputs: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        eyebrow = QLabel("DISTRIBUTION")
        eyebrow.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(eyebrow)

        title = QLabel("DistroKid")
        title.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(title)

        self._status = QLabel(
            "DistroKid add-on is not active. Purchase DistroKid ($5/mo) in the "
            "user portal Billing page to unlock WAV conversion (600/mo) and DistroKid delivery."
        )
        self._status.setObjectName(SUBTITLE_LABEL_ID)
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._status)

        self._usage = QLabel("WAV usage: —")
        self._usage.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._usage)

        actions = QHBoxLayout()
        self._connect_btn = QPushButton("Connect DistroKid")
        self._connect_btn.setToolTip("Open DistroKid in a persistent browser for Google Sign-In.")
        self._connect_btn.clicked.connect(self._on_connect)
        actions.addWidget(self._connect_btn)
        self._save_btn = QPushButton("Save settings")
        self._save_btn.clicked.connect(self._on_save)
        actions.addWidget(self._save_btn)
        self._refresh_btn = QPushButton("Refresh history")
        self._refresh_btn.clicked.connect(self._refresh_history)
        actions.addWidget(self._refresh_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        artist_title = QLabel("Artist delivery")
        artist_title.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(artist_title)

        artist_hint = QLabel(
            "Map each channel to a DistroKid artist (reuse the same name on multiple "
            "channels), or use one/two-artist shortcuts. Leave blank to use the channel profile name."
        )
        artist_hint.setObjectName(SUBTITLE_LABEL_ID)
        artist_hint.setWordWrap(True)
        layout.addWidget(artist_hint)

        mode_row = QHBoxLayout()
        self._artist_mode_group = QButtonGroup(self)
        self._mode_per_channel = QRadioButton("Per channel")
        self._mode_single = QRadioButton("One artist")
        self._mode_dual = QRadioButton("Two artists (Primary / Secondary)")
        self._artist_mode_group.addButton(self._mode_per_channel, 0)
        self._artist_mode_group.addButton(self._mode_single, 1)
        self._artist_mode_group.addButton(self._mode_dual, 2)
        mode_row.addWidget(self._mode_per_channel)
        mode_row.addWidget(self._mode_single)
        mode_row.addWidget(self._mode_dual)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        artist_form = QFormLayout()
        artist_form.setSpacing(8)
        self._single_artist = QLineEdit(self._settings.single_artist_name)
        self._single_artist.setPlaceholderText("DistroKid artist for all channels")
        artist_form.addRow("Artist name", self._single_artist)

        self._primary_artist = QLineEdit(self._settings.primary_artist_name)
        self._primary_artist.setPlaceholderText("All Primary-role channels → DistroKid artist")
        artist_form.addRow("Primary role artist", self._primary_artist)

        self._secondary_artist = QLineEdit(self._settings.secondary_artist_name)
        self._secondary_artist.setPlaceholderText("All Secondary-role channels → DistroKid artist")
        artist_form.addRow("Secondary role artist", self._secondary_artist)

        self._artist_fallback = QLineEdit(self._settings.artist_name)
        self._artist_fallback.setPlaceholderText("Fallback when a mapping is blank")
        artist_form.addRow("Fallback artist", self._artist_fallback)
        layout.addLayout(artist_form)

        self._channel_artists_title = QLabel("Channel → DistroKid artist")
        self._channel_artists_title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._channel_artists_title)
        self._channel_artists_form = QFormLayout()
        self._channel_artists_form.setSpacing(8)
        self._channel_artists_empty = QLabel("No channels loaded yet.")
        self._channel_artists_empty.setObjectName(SUBTITLE_LABEL_ID)
        self._channel_artists_form.addRow(self._channel_artists_empty)
        layout.addLayout(self._channel_artists_form)

        self._artist_mode_group.idClicked.connect(lambda _id: self._sync_artist_mode_fields())
        if self._settings.artist_mode == "single":
            self._mode_single.setChecked(True)
        elif self._settings.artist_mode == "dual":
            self._mode_dual.setChecked(True)
        else:
            self._mode_per_channel.setChecked(True)
        self._sync_artist_mode_fields()

        form = QFormLayout()
        form.setSpacing(8)
        self._genre = QLineEdit(self._settings.upload_form.primary_genre)
        form.addRow("Primary genre", self._genre)
        self._subgenre = QLineEdit(self._settings.upload_form.subgenre)
        form.addRow("Subgenre", self._subgenre)

        self._auto_submit = QCheckBox("Auto-submit after form fill")
        self._auto_submit.setChecked(self._settings.auto_submit)
        form.addRow("", self._auto_submit)

        self._keep_open = QCheckBox("Keep browser open after upload / connect")
        self._keep_open.setChecked(self._settings.keep_browser_open)
        form.addRow("", self._keep_open)

        self._delete_wav = QCheckBox("Delete WAV after successful DistroKid submit")
        self._delete_wav.setChecked(self._settings.delete_wav_after_upload)
        form.addRow("", self._delete_wav)

        self._delay = QSpinBox()
        self._delay.setRange(0, 300)
        self._delay.setValue(int(self._settings.upload_form.delay_between_albums))
        self._delay.setSuffix(" s")
        form.addRow("Delay between albums", self._delay)

        self._max_albums = QSpinBox()
        self._max_albums.setRange(1, 200)
        self._max_albums.setValue(int(self._settings.upload_form.max_albums_per_session))
        form.addRow("Max albums / session", self._max_albums)
        layout.addLayout(form)

        hist_label = QLabel("Upload history")
        hist_label.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(hist_label)
        self._history = QListWidget()
        self._history.setMinimumHeight(160)
        layout.addWidget(self._history, stretch=1)

        hint = QLabel(
            "Enable DistroKid on the Music page. After long Video + Merge finish, "
            "CAMXORA downloads Suno WAVs and uploads WAV + thumbnail to DistroKid. "
            "Short/Reel files are never merged. DistroKid errors are soft and do not fail the video run."
        )
        hint.setObjectName(SUBTITLE_LABEL_ID)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._set_controls_enabled(False)
        self._refresh_history()

    def set_api(self, api: PlatformApi | None) -> None:
        self._api = api

    def set_profiles(self, profiles: list[ProfileResponse] | None) -> None:
        self._profiles = list(profiles or [])
        self._rebuild_channel_artist_fields()
        self._sync_artist_mode_fields()

    def set_entitlement(self, *, active: bool, expires_at: str | None = None) -> None:
        self._active = active
        self._set_controls_enabled(active)
        if active:
            expiry = f" Expires {expires_at}." if expires_at else ""
            self._status.setText(
                f"DistroKid add-on is active.{expiry} "
                "WAV quota: up to 600 tracks/month (Primary + Secondary)."
            )
            self._refresh_usage()
        else:
            self._status.setText(
                "DistroKid add-on is not active. Purchase DistroKid ($5/mo) in the "
                "user portal Billing page to unlock WAV conversion (600/mo) and DistroKid delivery."
            )
            self._usage.setText("WAV usage: —")

    def _clear_channel_artist_form(self) -> None:
        while self._channel_artists_form.rowCount():
            self._channel_artists_form.removeRow(0)
        self._channel_artist_inputs.clear()

    def _rebuild_channel_artist_fields(self) -> None:
        self._clear_channel_artist_form()
        if not self._profiles:
            self._channel_artists_empty = QLabel("No channels loaded yet.")
            self._channel_artists_empty.setObjectName(SUBTITLE_LABEL_ID)
            self._channel_artists_form.addRow(self._channel_artists_empty)
            return
        saved = dict(self._settings.channel_artists or {})
        for profile in self._profiles:
            profile_id = str(profile.id or "").strip()
            if not profile_id:
                continue
            field = QLineEdit(saved.get(profile_id) or "")
            field.setPlaceholderText(f"DistroKid artist for {profile.name}")
            self._channel_artist_inputs[profile_id] = field
            self._channel_artists_form.addRow(str(profile.name or profile_id), field)

    def _current_artist_mode(self) -> str:
        if self._mode_single.isChecked():
            return "single"
        if self._mode_dual.isChecked():
            return "dual"
        return "per_channel"

    def _collect_channel_artists(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for profile_id, field in self._channel_artist_inputs.items():
            artist = field.text().strip()
            if artist:
                out[profile_id] = artist
        return out

    def _sync_artist_mode_fields(self) -> None:
        mode = self._current_artist_mode()
        single = mode == "single"
        dual = mode == "dual"
        per_channel = mode == "per_channel"
        self._single_artist.setEnabled(self._active and single)
        self._primary_artist.setEnabled(self._active and dual)
        self._secondary_artist.setEnabled(self._active and dual)
        self._channel_artists_title.setVisible(per_channel)
        for row in range(self._channel_artists_form.rowCount()):
            label_item = self._channel_artists_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = self._channel_artists_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            for item in (label_item, field_item):
                if item is None:
                    continue
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(per_channel)
                    widget.setEnabled(self._active and per_channel)
        # Empty-state row uses SpanningRole / field-only
        if self._channel_artists_form.rowCount() == 1 and not self._channel_artist_inputs:
            field_item = self._channel_artists_form.itemAt(0, QFormLayout.ItemRole.FieldRole)
            spanning = self._channel_artists_form.itemAt(0, QFormLayout.ItemRole.SpanningRole)
            for item in (field_item, spanning):
                if item is None:
                    continue
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(per_channel)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self._connect_btn,
            self._save_btn,
            self._refresh_btn,
            self._mode_per_channel,
            self._mode_single,
            self._mode_dual,
            self._single_artist,
            self._primary_artist,
            self._secondary_artist,
            self._artist_fallback,
            self._genre,
            self._subgenre,
            self._auto_submit,
            self._keep_open,
            self._delete_wav,
            self._delay,
            self._max_albums,
        ):
            widget.setEnabled(enabled)
        self._sync_artist_mode_fields()

    def _refresh_usage(self) -> None:
        if self._api is None or not self._active:
            return
        try:
            usage = self._api.distrokid_wav_usage()
            used = usage.get("used")
            limit = usage.get("limit")
            period = usage.get("period_key") or ""
            self._usage.setText(f"WAV usage: {used}/{limit} ({period})")
        except Exception as exc:  # noqa: BLE001
            self._usage.setText(f"WAV usage: unavailable ({exc})")

    def _on_save(self) -> None:
        settings = DistroKidSettings(
            artist_mode=self._current_artist_mode(),  # type: ignore[arg-type]
            single_artist_name=self._single_artist.text().strip(),
            primary_artist_name=self._primary_artist.text().strip(),
            secondary_artist_name=self._secondary_artist.text().strip(),
            channel_artists=self._collect_channel_artists(),
            artist_name=self._artist_fallback.text().strip(),
            auto_submit=self._auto_submit.isChecked(),
            keep_browser_open=self._keep_open.isChecked(),
            delete_wav_after_upload=self._delete_wav.isChecked(),
            upload_form=self._settings.upload_form,
        )
        settings.upload_form.primary_genre = self._genre.text().strip() or "Electronic"
        settings.upload_form.subgenre = self._subgenre.text().strip() or "House"
        settings.upload_form.delay_between_albums = int(self._delay.value())
        settings.upload_form.max_albums_per_session = int(self._max_albums.value())
        self._store.save(settings)
        self._settings = settings
        QMessageBox.information(self, "DistroKid", "Settings saved.")

    def _on_connect(self) -> None:
        if self._connect_worker is not None and self._connect_worker.isRunning():
            QMessageBox.information(self, "DistroKid", "Connect is already running.")
            return
        self._connect_btn.setEnabled(False)
        worker = DistroKidConnectWorker(keep_browser_open=self._keep_open.isChecked(), parent=None)
        worker.progressed.connect(lambda msg: self._status.setText(str(msg)))
        worker.succeeded.connect(self._on_connect_succeeded)
        worker.failed.connect(self._on_connect_failed)
        worker.finished.connect(self._on_connect_finished)
        self._connect_worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_connect_succeeded(self, ok: bool) -> None:
        if ok:
            QMessageBox.information(
                self,
                "DistroKid",
                "Connected. Session is saved in the Camxora DistroKid browser profile.",
            )
        else:
            QMessageBox.warning(self, "DistroKid", "Login did not complete. Try again.")

    def _on_connect_failed(self, message: str) -> None:
        QMessageBox.critical(self, "DistroKid", f"Could not open DistroKid browser:\n{message}")

    def _on_connect_finished(self) -> None:
        self._connect_worker = None
        self._connect_btn.setEnabled(self._active)

    def _refresh_history(self) -> None:
        self._history.clear()
        local = UploadHistory().get_successful()
        for entry in reversed(local[-40:]):
            name = entry.get("album_name") or "?"
            when = entry.get("uploaded_at") or ""
            count = entry.get("track_count") or 0
            self._history.addItem(f"[local] {when} — {name} ({count} tracks)")
        if self._api is None or not self._active:
            return
        try:
            remote = self._api.distrokid_history_list(limit=40)
            for entry in remote:
                name = entry.get("album_name") or "?"
                title = entry.get("track_title") or ""
                when = entry.get("uploaded_at") or ""
                self._history.addItem(f"[cloud] {when} — {name} / {title}")
        except Exception as exc:  # noqa: BLE001
            self._history.addItem(f"[cloud] unavailable: {exc}")
