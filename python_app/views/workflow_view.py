from __future__ import annotations

import threading
import time
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, QDate
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QSizePolicy,
)

from .components import WorkflowTimeline
from .helpers import widget_factory
from .helpers.style_helper import apply_cta_button, set_panel_role


class WorkflowViewMixin:
    def _build_workflow_workspace_page(self) -> QWidget:
        page = QWidget()
        set_panel_role(page, "center")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title = QLabel("Workflow")
        self._set_label_role(title, "sectionTitle")
        header_layout.addWidget(title)
        header_layout.addWidget(QLabel("Run"))
        self.workflow_run_combo = QComboBox()
        self._apply_card_field(self.workflow_run_combo)
        self.workflow_run_combo.setMinimumWidth(420)
        self.workflow_run_combo.currentIndexChanged.connect(lambda _: self._on_workflow_run_changed())
        header_layout.addWidget(self.workflow_run_combo)
        header_layout.addStretch(1)

        self.workflow_from_date = widget_factory.create_calendar_picker(lambda: self._refresh_workflow_async(force=True), self.ui, width=118)
        self.workflow_to_date = widget_factory.create_calendar_picker(lambda: self._refresh_workflow_async(force=True), self.ui, width=118)
        today = QDate.currentDate().toString("yyyy-MM-dd")
        widget_factory.set_calendar_picker_value(self.workflow_from_date, today)
        widget_factory.set_calendar_picker_value(self.workflow_to_date, today)
        header_layout.addWidget(QLabel("From"))
        header_layout.addWidget(self.workflow_from_date)
        header_layout.addWidget(QLabel("To"))
        header_layout.addWidget(self.workflow_to_date)

        self.workflow_active_only = QCheckBox("Active only")
        self._set_widget_property(self.workflow_active_only, "uiRole", "toggle")
        self.workflow_active_only.toggled.connect(lambda _: self._refresh_workflow_async(force=True))
        header_layout.addWidget(self.workflow_active_only)

        self.workflow_refresh_button = QPushButton("Refresh")
        self._set_button_role(self.workflow_refresh_button, "secondary")
        self.workflow_refresh_button.clicked.connect(lambda: self._refresh_workflow_async(force=True))
        header_layout.addWidget(self.workflow_refresh_button)

        layout.addWidget(header)

        right_card, right_body = widget_factory.make_panel_section(
            "Timeline", self.ui,
            subtitle_text="Real-time overview (per selected batch + channel).",
            soft=False,
        )
        right_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.workflow_timeline = WorkflowTimeline()
        right_body.addWidget(self.workflow_timeline)
        self.workflow_notes = QLabel("Select a run to see details.")
        self._set_label_role(self.workflow_notes, "statusMuted")
        self.workflow_notes.setWordWrap(True)
        right_body.addWidget(self.workflow_notes)
        self.workflow_status_label = QLabel("Ready")
        self._set_label_role(self.workflow_status_label, "statusMuted")
        right_body.addWidget(self.workflow_status_label)
        self.workflow_generate_button = QPushButton("Generate")
        apply_cta_button(self.workflow_generate_button, "success", self.ui)
        self.workflow_generate_button.setMinimumWidth(140)
        self.workflow_generate_button.setFixedHeight(32)
        self.workflow_generate_button.clicked.connect(self._on_workflow_generate_clicked)
        right_body.addWidget(self.workflow_generate_button)
        layout.addWidget(right_card, 1)

        self._workflow_rows_cache: list[dict] = []
        self._workflow_selected_key: tuple[str, str, str] | None = None
        self._workflow_combo_keys: list[tuple[str, str, str]] = []
        self._workflow_inflight = False
        self._workflow_started_at = 0.0
        self._workflow_refresh_token = 0

        return page

    def _on_workflow_generate_clicked(self) -> None:
        from_ymd = widget_factory.calendar_picker_value(getattr(self, "workflow_from_date", None))
        to_ymd = widget_factory.calendar_picker_value(getattr(self, "workflow_to_date", None))
        self.music_run_from_date = str(from_ymd or "").strip()
        self.music_run_to_date = str(to_ymd or "").strip()
        self._persist_music_runtime_state()
        self._music_controller.on_music_generate_clicked()

    def _ensure_workflow_timers(self) -> None:
        t = getattr(self, "_workflow_live_refresh_timer", None)
        if t is None:
            t = QTimer(self)
            t.setInterval(2000)
            t.timeout.connect(lambda: self._refresh_workflow_async(force=False))
            self._workflow_live_refresh_timer = t

    def _refresh_workflow_async(self, *, force: bool = False) -> None:
        if not hasattr(self, "workflow_run_combo"):
            return
        if bool(getattr(self, "_app_closing", False)):
            return

        inflight = bool(getattr(self, "_workflow_inflight", False))
        if inflight and not bool(force):
            started_at = float(getattr(self, "_workflow_started_at", 0.0) or 0.0)
            if started_at > 0.0 and (time.time() - started_at) > 12.0:
                self._workflow_inflight = False
            else:
                return

        if not getattr(self, "db_cfg", None):
            self.workflow_run_combo.blockSignals(True)
            self.workflow_run_combo.clear()
            self.workflow_run_combo.blockSignals(False)
            self.workflow_status_label.setText("Configure Postgres in Settings → Database")
            self.workflow_notes.setText("Database is not configured.")
            return

        from_ymd = widget_factory.calendar_picker_value(getattr(self, "workflow_from_date", None))
        to_ymd = widget_factory.calendar_picker_value(getattr(self, "workflow_to_date", None))
        active_only = bool(getattr(self, "workflow_active_only", None).isChecked()) if hasattr(self, "workflow_active_only") else False

        token = int(getattr(self, "_workflow_refresh_token", 0) or 0) + 1
        self._workflow_refresh_token = token
        self._workflow_inflight = True
        self._workflow_started_at = time.time()
        self.workflow_status_label.setText("Refreshing…")

        def work():
            try:
                rows = self._progress_controller._collect_progress_rows(limit=80, active_only=active_only, from_ymd=from_ymd, to_ymd=to_ymd)
                elapsed = time.time() - float(getattr(self, "_workflow_started_at", time.time()))

                def apply():
                    if bool(getattr(self, "_app_closing", False)):
                        return
                    if int(getattr(self, "_workflow_refresh_token", 0) or 0) != token:
                        return
                    self._apply_workflow_rows(rows)
                    self.workflow_status_label.setText(f"Refreshed at {time.strftime('%H:%M:%S')} · {elapsed:.2f}s")
                    self._workflow_inflight = False
                    self._workflow_started_at = 0.0

                self.bus.ui_invoke.emit(apply)
            except Exception as exc:
                err_msg = str(exc)
                def apply_err():
                    self.workflow_status_label.setText(f"Workflow refresh failed: {err_msg}")
                    self._workflow_inflight = False
                    self._workflow_started_at = 0.0

                self.bus.ui_invoke.emit(apply_err)

        threading.Thread(target=work, daemon=True).start()

    def _apply_workflow_rows(self, rows: list[dict]) -> None:
        rows2 = [r for r in (rows or []) if isinstance(r, dict)]
        self._workflow_rows_cache = rows2
        prev_key = getattr(self, "_workflow_selected_key", None)
        keys2: list[tuple[str, str, str]] = []
        labels2: list[str] = []
        selected_idx = -1
        for r, row in enumerate(rows2):
            meta = dict((row or {}).get("_meta") or {})
            bid = str(meta.get("batchId", "")).strip()
            pid = str(meta.get("profileId", "")).strip()
            role = str(meta.get("role", "")).strip().upper()
            key = (bid, pid, role)
            label = f'{str(row.get("channel", "")).strip()} · {str(row.get("stage", "")).strip()} · {str(row.get("status", "")).strip()}'
            keys2.append(key)
            labels2.append(label)
            if prev_key is not None and key == prev_key:
                selected_idx = r

        if len(rows2) <= 0:
            self._workflow_selected_key = None
            self._workflow_combo_keys = []
            self.workflow_run_combo.blockSignals(True)
            try:
                self.workflow_run_combo.clear()
            finally:
                self.workflow_run_combo.blockSignals(False)
            self.workflow_notes.setText("No runs found for the selected range.")
            self.workflow_timeline.set_steps([])
            return

        if selected_idx < 0:
            selected_idx = int(self.workflow_run_combo.currentIndex())
        selected_idx = int(max(0, min(len(rows2) - 1, selected_idx)))

        keys_prev = list(getattr(self, "_workflow_combo_keys", []) or [])
        same_keys = len(keys_prev) == len(keys2) and all(a == b for a, b in zip(keys_prev, keys2))

        if not same_keys:
            self.workflow_run_combo.blockSignals(True)
            try:
                self.workflow_run_combo.clear()
                for r, (key, label) in enumerate(zip(keys2, labels2)):
                    self.workflow_run_combo.addItem(label)
                    self.workflow_run_combo.setItemData(r, key, Qt.ItemDataRole.UserRole)
            finally:
                self.workflow_run_combo.blockSignals(False)
            self._workflow_combo_keys = keys2
        else:
            for r, label in enumerate(labels2):
                try:
                    if str(self.workflow_run_combo.itemText(r)) != str(label):
                        self.workflow_run_combo.setItemText(r, label)
                except Exception:
                    pass
            self._workflow_combo_keys = keys2

        if int(self.workflow_run_combo.currentIndex()) != selected_idx:
            self.workflow_run_combo.blockSignals(True)
            try:
                self.workflow_run_combo.setCurrentIndex(selected_idx)
            finally:
                self.workflow_run_combo.blockSignals(False)

        self._apply_workflow_selected_row(rows2[selected_idx])

    def _on_workflow_run_changed(self) -> None:
        if not hasattr(self, "workflow_run_combo"):
            return
        idx = int(self.workflow_run_combo.currentIndex())
        if idx < 0:
            return
        if idx >= len(getattr(self, "_workflow_rows_cache", []) or []):
            return
        row = (getattr(self, "_workflow_rows_cache", []) or [])[idx]
        self._apply_workflow_selected_row(row)

    def _apply_workflow_selected_row(self, row: dict) -> None:
        meta = dict((row or {}).get("_meta") or {})
        bid = str(meta.get("batchId", "")).strip()
        pid = str(meta.get("profileId", "")).strip()
        role = str(meta.get("role", "")).strip().upper()
        if bid and pid and role:
            self._workflow_selected_key = (bid, pid, role)

        steps = self._build_workflow_step_states(row)
        self.workflow_timeline.set_steps(steps)
        notes = str(row.get("notesFull", "") or row.get("notes", "") or "").strip()
        if not notes:
            notes = "No blocking notes."
        self.workflow_notes.setText(notes)

    def _build_workflow_step_states(self, row: dict) -> list[dict]:
        meta = dict((row or {}).get("_meta") or {})
        expected = int(meta.get("expected", 0) or 0)
        saved = int(meta.get("saved", 0) or 0)
        stage_raw = str(row.get("stage", "")).strip()
        stage_key = str(stage_raw).strip().lower()
        if stage_key == "you tube":
            stage_key = "youtube"
        status = str(row.get("status", "")).strip()
        img = str(row.get("image", "")).strip()
        conv = str(row.get("converter", "")).strip()
        merge = str(row.get("merge", "")).strip()
        yt_text = str(row.get("youtube", "")).strip()
        yt_status = str(meta.get("youtubeStatus", "")).strip().upper()

        def clamp_pct(p: float) -> int:
            return int(max(0, min(100, round(float(p)))))

        def parse_counts(s: str, key: str) -> tuple[int, int]:
            t = str(s or "")
            idx = t.find(key)
            if idx < 0:
                return (0, 0)
            frag = t[idx + len(key):].strip()
            if frag.startswith(":"):
                frag = frag[1:].strip()
            parts = frag.split()
            if not parts:
                return (0, 0)
            nums = parts[0].split("/")
            if len(nums) != 2:
                return (0, 0)
            try:
                return (int(nums[0]), int(nums[1]))
            except Exception:
                return (0, 0)

        def parse_dt(s: str) -> datetime | None:
            t = str(s or "").strip()
            if not t:
                return None
            try:
                t2 = t.replace("Z", "+00:00")
                return datetime.fromisoformat(t2)
            except Exception:
                try:
                    return datetime.fromisoformat(t.replace(" ", "T"))
                except Exception:
                    return None

        def fmt_dur(start_dt: datetime | None, end_dt: datetime | None) -> str:
            if start_dt is None or end_dt is None:
                return "—"
            try:
                sec = max(0.0, (end_dt - start_dt).total_seconds())
            except Exception:
                return "—"
            if sec < 60.0:
                return f"{int(round(sec))}s"
            mins = sec / 60.0
            return f"{mins:.1f} min"

        now_dt = datetime.now()

        bg_state = "—"
        th_state = "—"
        if "BG" in img and "TH" in img:
            try:
                segs = [x.strip() for x in img.split("·")]
                for s in segs:
                    if s.upper().startswith("BG"):
                        bg_state = s.split()[-1].strip()
                    if s.upper().startswith("TH"):
                        th_state = s.split()[-1].strip()
            except Exception:
                pass

        mp4_done, mp4_total = parse_counts(conv, "MP4")

        music_pct = 0 if expected <= 0 else clamp_pct(saved / float(max(1, expected)) * 100.0)
        img_pct = 0
        if str(bg_state).upper() == "READY":
            img_pct += 50
        if str(th_state).upper() == "READY":
            img_pct += 50
        conv_pct = 0 if expected <= 0 else clamp_pct(mp4_done / float(max(1, expected)) * 100.0) if mp4_total <= 0 else clamp_pct(mp4_done / float(max(1, mp4_total)) * 100.0)
        merge_pct = 100 if merge and merge != "—" else 0
        yt_pct = 0
        if yt_status == "READY":
            yt_pct = 100
        else:
            try:
                if "Uploading" in yt_text and "%" in yt_text:
                    n = "".join([ch for ch in yt_text if ch.isdigit()])
                    yt_pct = clamp_pct(int(n))
            except Exception:
                yt_pct = 0

        cancelled = stage_key == "cancelled" or status.strip().lower() == "cancelled"
        errored = stage_key == "error" or status.strip().lower() == "failed"

        def state_for_step(step_key: str, pct: int) -> str:
            if cancelled:
                return "cancelled"
            if errored:
                if step_key == "image" and ("FAILED" in str(bg_state).upper() or "FAILED" in str(th_state).upper()):
                    return "failed"
                if step_key == "youtube" and yt_status in {"FAILED", "BLOCKED"}:
                    return "failed"
                if step_key == stage_key:
                    return "failed"
            order = ["music", "image", "converter", "merge", "youtube"]
            if stage_key == "done":
                return "done"
            try:
                cur = order.index(stage_key)
            except Exception:
                cur = -1
            idx = order.index(step_key)
            if cur < 0:
                return "done" if pct >= 100 else "inactive"
            if idx < cur:
                return "done"
            if idx == cur:
                if pct >= 100:
                    return "done"
                if step_key == "youtube" and yt_status in {"FAILED", "BLOCKED"}:
                    return "failed"
                return "running"
            return "inactive"

        music_min = parse_dt(str(meta.get("musicMinCreatedAt", "")).strip())
        music_max = parse_dt(str(meta.get("musicMaxCreatedAt", "")).strip())
        music_end = music_max if saved >= expected and music_max is not None else now_dt
        music_dur = fmt_dur(music_min, music_end)

        bg_created = parse_dt(str(meta.get("bgCreatedAt", "")).strip())
        th_created = parse_dt(str(meta.get("thCreatedAt", "")).strip())
        bg_updated = parse_dt(str(meta.get("bgUpdatedAt", "")).strip())
        th_updated = parse_dt(str(meta.get("thUpdatedAt", "")).strip())
        img_start = min([d for d in (bg_created, th_created) if d is not None], default=None)
        img_end = max([d for d in (bg_updated, th_updated) if d is not None], default=None)
        img_done = str(bg_state).upper() == "READY" and str(th_state).upper() == "READY"
        img_dur = fmt_dur(img_start, img_end if img_done and img_end is not None else now_dt)

        mp4_min_mt = float(meta.get("mp4MinMTime", 0.0) or 0.0)
        mp4_max_mt = float(meta.get("mp4MaxMTime", 0.0) or 0.0)
        conv_start = datetime.fromtimestamp(mp4_min_mt) if mp4_min_mt > 0 else None
        conv_end_dt = datetime.fromtimestamp(mp4_max_mt) if mp4_max_mt > 0 else None
        conv_done = mp4_done >= max(1, expected)
        conv_dur = fmt_dur(conv_start, conv_end_dt if conv_done and conv_end_dt is not None else now_dt)

        merged_mt = float(meta.get("mergedMTime", 0.0) or 0.0)
        merge_end_dt = datetime.fromtimestamp(merged_mt) if merged_mt > 0 else None
        merge_start = conv_end_dt
        merge_done = bool(merge_pct >= 100 and merge_end_dt is not None)
        merge_dur = fmt_dur(merge_start, merge_end_dt if merge_done and merge_end_dt is not None else now_dt)

        yt_created = parse_dt(str(meta.get("youtubeCreatedAt", "")).strip())
        yt_updated = parse_dt(str(meta.get("youtubeUpdatedAt", "")).strip())
        yt_done = yt_status == "READY" and yt_updated is not None
        yt_dur = fmt_dur(yt_created, yt_updated if yt_done else now_dt)

        return [
            {
                "key": "music",
                "title": "Music Generation",
                "lucide": "music",
                "percent": int(music_pct),
                "state": state_for_step("music", int(music_pct)),
                "durationText": music_dur,
                "details": [f"{saved}/{max(1, expected)} songs", status if stage_key == "music" else "—"],
            },
            {
                "key": "image",
                "title": "Background + Thumbnail",
                "lucide": "image",
                "percent": int(img_pct),
                "state": state_for_step("image", int(img_pct)),
                "durationText": img_dur,
                "details": [img or "BG — · TH —", "—" if stage_key != "image" else status],
            },
            {
                "key": "converter",
                "title": "Convert (MP4)",
                "lucide": "video",
                "percent": int(conv_pct),
                "state": state_for_step("converter", int(conv_pct)),
                "durationText": conv_dur,
                "details": [f"MP4 {mp4_done}/{max(1, expected)}", "—" if stage_key != "converter" else status],
            },
            {
                "key": "merge",
                "title": "Merge",
                "lucide": "git-merge",
                "percent": int(merge_pct),
                "state": state_for_step("merge", int(merge_pct)),
                "durationText": merge_dur,
                "details": [merge if merge and merge != "—" else "Waiting to merge", "—" if stage_key != "merge" else status],
            },
            {
                "key": "youtube",
                "title": "YouTube Upload",
                "lucide": "youtube",
                "percent": int(yt_pct),
                "state": state_for_step("youtube", int(yt_pct)),
                "durationText": yt_dur,
                "details": [yt_text or "—", "—" if stage_key != "youtube" else status],
            },
        ]
