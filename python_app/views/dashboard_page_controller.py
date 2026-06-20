"""DashboardPageController — owns dashboard-page orchestration.

Extracted from ``MainWindow`` as part of the *main-window-decomposition* spec
(Requirement 5). The controller owns the dashboard data-refresh pipeline (a
background query whose results are marshalled back to the UI thread via
``bus.ui_invoke``), KPI/stage-bar/table population, profile-combo syncing, and
the failures-table context menu.

The controller does **not** hold a reference to ``MainWindow``. Instead it
receives a small, typed set of dependencies:

* ``db_cfg_accessor`` — returns the active :class:`DbCfg` or ``None`` when the
  database is not configured. The refresh is guarded by this accessor so the
  controller degrades gracefully — when it returns ``None`` the DB query is
  skipped and the dashboard shows a "not configured" state (Requirement
  5.3 / 12.4).
* ``bus`` — the :class:`UiBus` used to marshal background results back onto the
  UI thread via ``bus.ui_invoke``. The controller never calls
  ``QApplication.processEvents()``.
* ``settings_accessor`` — returns the current music-settings dict.
* ``widget_accessors`` — a ``dict[str, Callable[[], object]]`` registry that
  resolves widgets (e.g. ``"failures_table"``) and host-provided collaborators
  / callbacks (e.g. ``"set_global_status"``). The :meth:`_widget` helper
  returns ``None`` when a key is missing, keeping the controller
  constructable — and unit-testable — without a ``QApplication``.
* ``stats_builder`` — an optional ``Callable`` that computes the dashboard
  stats model from a :class:`DbCfg`. The heavy stats/row-scan computation lives
  in the progress domain; injecting it keeps this controller decoupled. When it
  is ``None`` the background query is skipped (the controller stays
  constructable for isolated unit tests).

Recognised ``widget_accessors`` keys (all optional):

    Widgets:        ``window``, ``status_label``, ``summary_label``,
                    ``kpi_labels`` (dict), ``stage_bars`` (dict),
                    ``failures_table``, ``activity_table``, ``from_date``,
                    ``to_date``, ``profile_combo``, ``active_only``
    Collaborators:  ``music_data``
    Shared state:   ``app_closing``, ``suno_credits``
    Host callbacks: ``log``, ``set_global_status``, ``progress_cancel_row``,
                    ``progress_restart_images``, ``progress_restart_converter``,
                    ``progress_restart_merge_only``
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QTableWidgetItem,
)

from ..app.ui_bus import UiBus
from ..database.persistence import DbCfg
from .helpers.widget_factory import calendar_picker_value as _calendar_picker_value


class DashboardPageController:
    """Owns dashboard refresh, profile-combo syncing, and the failures menu."""

    def __init__(
        self,
        *,
        db_cfg_accessor: Callable[[], DbCfg | None],
        bus: UiBus,
        settings_accessor: Callable[[], dict],
        widget_accessors: dict[str, Callable[[], object]],
        stats_builder: Callable[..., dict] | None = None,
    ) -> None:
        self._db_cfg_accessor = db_cfg_accessor
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._widget_accessors: dict[str, Callable[[], object]] = dict(widget_accessors or {})
        self._stats_builder = stats_builder

        # Refresh-coalescing / staleness state (controller-owned).
        self._refresh_token: int = 0
        self._refresh_inflight: bool = False
        self._refresh_started_at: float = 0.0

    # ------------------------------------------------------------------
    # Dependency accessors (safe — return None / defaults when missing)
    # ------------------------------------------------------------------
    def _db_cfg(self) -> DbCfg | None:
        try:
            return self._db_cfg_accessor()
        except Exception:
            return None

    def _settings(self) -> dict:
        try:
            return self._settings_accessor() or {}
        except Exception:
            return {}

    def _music_data(self) -> dict:
        data = self._widget("music_data")
        return data if isinstance(data, dict) else {}

    def _widget(self, name: str) -> Any:
        """Resolve a widget / collaborator by name, or ``None`` when missing."""
        fn = self._widget_accessors.get(name)
        if fn is None:
            return None
        try:
            return fn()
        except Exception:
            return None

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a host-provided callback by name; no-op when not registered."""
        fn = self._widget(name)
        if not callable(fn):
            return None
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None

    def _window(self) -> Any:
        return self._widget("window")

    def _is_app_closing(self) -> bool:
        return bool(self._widget("app_closing"))

    def _log(self, msg: str) -> None:
        self._call("log", msg)

    def _set_global_status(self, msg: str, *, source: str = "") -> None:
        self._call("set_global_status", msg, source=source)

    def _ui_invoke(self, fn: Callable[[], None]) -> None:
        """Marshal *fn* onto the UI thread, honouring the app-closing flag."""
        try:
            if self._is_app_closing():
                return
            bus = self._bus
            if bus is None:
                return
            bus.ui_invoke.emit(fn)
        except Exception:
            return

    # ------------------------------------------------------------------
    # Profile combo
    # ------------------------------------------------------------------
    def dashboard_sync_profile_combo(self) -> None:
        """Repopulate the profile combo from the current ``music_data`` profiles."""
        combo = self._widget("profile_combo")
        if combo is None:
            return
        current = ""
        try:
            current = str(combo.currentData() or "").strip()
        except Exception:
            current = ""
        raw_profiles = self._music_data().get("profiles")
        profiles = raw_profiles if isinstance(raw_profiles, list) else []
        items: list[tuple[str, str]] = [("", "All Channels")]
        for p in profiles:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id", "")).strip()
            name = str(p.get("name", "")).strip()
            if pid and name:
                items.append((pid, name))
        combo.blockSignals(True)
        combo.clear()
        for pid, name in items:
            combo.addItem(name, pid)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def dashboard_selected_profile_id(self) -> str:
        """Return the currently-selected profile id, or ``""`` for All Channels."""
        combo = self._widget("profile_combo")
        if combo is None:
            return ""
        try:
            return str(combo.currentData() or "").strip()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Failures table
    # ------------------------------------------------------------------
    def dashboard_failure_meta_at(self, row_index: int) -> dict:
        """Return the ``_meta`` dict stored on the failures row, or ``{}``."""
        table = self._widget("failures_table")
        if table is None:
            return {}
        if row_index < 0 or row_index >= int(table.rowCount()):
            return {}
        item = table.item(row_index, 1)
        if item is None:
            item = table.item(row_index, 0)
        if item is None:
            return {}
        meta = item.data(Qt.ItemDataRole.UserRole)
        return dict(meta) if isinstance(meta, dict) else {}

    def on_dashboard_failures_context_menu(self, pos: QPoint) -> None:
        """Show the right-click action menu for a failures-table row."""
        table = self._widget("failures_table")
        if table is None:
            return
        row = int(table.rowAt(pos.y()))
        meta = self.dashboard_failure_meta_at(row)
        if not meta:
            return

        window = self._window()
        menu = QMenu(window)
        out_dir = str(meta.get("outDir", "")).strip()
        batch_id = str(meta.get("batchId", "")).strip()
        act_open = menu.addAction("Open Output Folder")
        act_copy = menu.addAction("Copy Batch ID")
        menu.addSeparator()
        act_cancel_row = menu.addAction("Cancel Row (Stop All Jobs)")
        menu.addSeparator()
        act_img_all = menu.addAction("Restart Image (BG + TH)")
        act_img_bg = menu.addAction("Restart Background Only")
        act_img_th = menu.addAction("Restart Thumbnail Only")
        menu.addSeparator()
        act_conv = menu.addAction("Restart Converter (Generate Missing MP4)")
        act_conv_force = menu.addAction("Force Converter (Rebuild MP4)")
        act_merge = menu.addAction("Restart Merge Only")
        menu.addSeparator()
        act_all = menu.addAction("Restart From Image (Image → Converter → Merge)")

        if not out_dir:
            act_open.setEnabled(False)
            act_conv.setEnabled(False)
            act_conv_force.setEnabled(False)
            act_merge.setEnabled(False)
        if not self._db_cfg():
            act_img_all.setEnabled(False)
            act_img_bg.setEnabled(False)
            act_img_th.setEnabled(False)
            act_all.setEnabled(False)
            act_cancel_row.setEnabled(False)

        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_open:
            if out_dir and Path(out_dir).exists():
                try:
                    os.startfile(out_dir)  # type: ignore[attr-defined]
                except Exception as exc:
                    QMessageBox.warning(window, "Dashboard", f"Cannot open folder:\n{exc}")
            return
        if chosen == act_copy:
            try:
                QApplication.clipboard().setText(batch_id)
            except Exception:
                pass
            return
        if chosen == act_cancel_row:
            self._call("progress_cancel_row", meta)
            return
        if chosen == act_img_all:
            self._call("progress_restart_images", meta, background=True, thumbnail=True)
            return
        if chosen == act_img_bg:
            self._call("progress_restart_images", meta, background=True, thumbnail=False)
            return
        if chosen == act_img_th:
            self._call("progress_restart_images", meta, background=False, thumbnail=True)
            return
        if chosen == act_conv:
            self._call("progress_restart_converter", meta, force_rebuild=False)
            return
        if chosen == act_conv_force:
            self._call("progress_restart_converter", meta, force_rebuild=True)
            return
        if chosen == act_merge:
            self._call("progress_restart_merge_only", meta)
            return
        if chosen == act_all:
            self._call("progress_restart_images", meta, background=True, thumbnail=True)
            self._call("progress_restart_converter", meta, force_rebuild=False)
            return

    # ------------------------------------------------------------------
    # Refresh pipeline
    # ------------------------------------------------------------------
    def refresh_dashboard_async(self, *, force: bool = False) -> None:
        """Refresh dashboard data on a background thread.

        Fetches stats from the Platform API and updates KPI cards,
        donut charts, line chart, and activity table.
        """
        import threading

        status_label = self._widget("status_label")
        if status_label is None:
            return

        inflight = bool(self._refresh_inflight)
        if inflight and not bool(force):
            started_at = float(self._refresh_started_at or 0.0)
            if started_at > 0.0 and (time.time() - started_at) > 12.0:
                self._refresh_inflight = False
                inflight = False
            else:
                return

        token_store = self._widget("token_store")
        if token_store is None:
            return

        try:
            tokens = token_store.load()
            access_token = tokens.access_token
        except Exception:
            return

        self._refresh_inflight = True
        self._refresh_started_at = time.time()
        status_label.setText("Refreshing…")

        token = int(self._refresh_token or 0) + 1
        self._refresh_token = token

        def work() -> None:
            try:
                from python_app.services.stats_client import StatsClient
                client = StatsClient()
                try:
                    stats = client.get_dashboard_stats(access_token)
                finally:
                    client.close()

                def apply() -> None:
                    if int(self._refresh_token or 0) != token:
                        return
                    self._apply_api_stats(stats)
                    elapsed = time.time() - self._refresh_started_at
                    msg = f"Refreshed at {time.strftime('%H:%M:%S')} · total {elapsed:.2f}s"
                    label = self._widget("status_label")
                    if label is not None:
                        label.setText(msg)
                    self._refresh_inflight = False
                    self._refresh_started_at = 0.0

                self._ui_invoke(apply)
            except Exception as exc:
                err_msg = str(exc)

                def apply_err() -> None:
                    self._refresh_inflight = False
                    self._refresh_started_at = 0.0
                    label = self._widget("status_label")
                    if label is not None:
                        label.setText(f"API error: {err_msg}")
                self._ui_invoke(apply_err)

        threading.Thread(target=work, daemon=True).start()

    def _apply_api_stats(self, stats) -> None:
        """Apply API stats to KPI cards, donut charts, line chart, and activity table."""
        from PyQt6.QtGui import QColor

        # KPI cards
        kpi = self._widget("kpi_labels")
        if isinstance(kpi, dict):
            def set_k(key: str, value) -> None:
                lab = kpi.get(key)
                if isinstance(lab, QLabel):
                    lab.setText("—" if value is None else str(value))

            set_k("credits", stats.credits_spent)
            set_k("songs", stats.songs_generated)
            set_k("images", stats.images_generated)
            set_k("mp4", stats.videos_generated)
            set_k("youtube", stats.videos_generated)

        # Donut charts
        total = max(1, stats.credits_total) if stats.credits_total else 1
        donut_credits = self._widget("donut_credits")
        if donut_credits is not None:
            pct = int((stats.credits_remaining / total) * 100) if total else 0
            donut_credits.setValue(pct)

        donut_songs = self._widget("donut_songs")
        if donut_songs is not None and stats.songs_quota:
            pct = int((stats.songs_remaining / stats.songs_quota) * 100) if stats.songs_remaining is not None else 0
            donut_songs.setValue(pct)

        donut_images = self._widget("donut_images")
        if donut_images is not None:
            donut_images.setValue(0)

        # Line chart
        line_chart = self._widget("line_chart")
        if line_chart is not None and stats.usage_by_day:
            labels = [d.date[-5:] for d in stats.usage_by_day]
            series = {
                "Songs": [d.songs for d in stats.usage_by_day],
                "Images": [d.images for d in stats.usage_by_day],
                "Videos": [d.videos for d in stats.usage_by_day],
            }
            colors = {
                "Songs": QColor("#7466F1"),
                "Images": QColor("#1ABCFE"),
                "Videos": QColor("#0ACF83"),
            }
            line_chart.setData(labels, series, colors)

        # Activity table
        activity_table = self._widget("activity_table")
        if activity_table is not None and stats.recent_activity:
            activity_table.setRowCount(len(stats.recent_activity))
            for r, evt in enumerate(stats.recent_activity):
                cols = [evt.timestamp[:19], evt.kind, "", "", evt.status, evt.detail]
                for c, text in enumerate(cols):
                    item = QTableWidgetItem(str(text))
                    if c in {0, 4}:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    activity_table.setItem(r, c, item)

    def apply_dashboard_model(self, model: dict) -> None:
        """Populate KPI labels, stage bars, and the failures/activity tables."""
        if not isinstance(model, dict):
            return
        profiles = {
            str((p or {}).get("id", "")).strip(): dict(p)
            for p in (self._music_data().get("profiles") or [])
            if isinstance(p, dict)
        }

        kpi = self._widget("kpi_labels")
        if isinstance(kpi, dict):
            def set_k(key: str, value: int | None) -> None:
                lab = kpi.get(key)
                if isinstance(lab, QLabel):
                    lab.setText("—" if value is None else str(value))

            set_k("activeBatches", int(model.get("activeBatches", 0) or 0))
            set_k("failedItems", int(model.get("failedItems", 0) or 0))
            set_k("songs", int(model.get("songs", 0) or 0))
            set_k("images", int(model.get("images", 0) or 0))
            set_k("mp4", int(model.get("mp4", 0) or 0))
            set_k("merged", int(model.get("merged", 0) or 0))
            set_k("youtube", int(model.get("youtube", 0) or 0))
            set_k("credits", model.get("credits", None))

        stage_counts = dict(model.get("stageCounts") or {})
        total = max(1, int(model.get("totalRows", 0) or 0))
        bars = self._widget("stage_bars")
        if isinstance(bars, dict):
            for stage, bar in bars.items():
                if not isinstance(bar, QProgressBar):
                    continue
                c = int(stage_counts.get(stage, 0) or 0)
                bar.setMaximum(total)
                bar.setValue(c)
                bar.setFormat(f"{c}/{total}")

        failures = model.get("failures") if isinstance(model.get("failures"), list) else []
        failures_table = self._widget("failures_table")
        if failures_table is not None:
            failures_table.setRowCount(len(failures))
            for r, row in enumerate(failures):
                meta = dict((row or {}).get("_meta") or {})
                run_date = str(row.get("runDate", "")).strip()
                updated = str(row.get("updated", "")).strip()
                when = f"{run_date} {updated}".strip()
                cols = [
                    when,
                    str(row.get("batch", "")).strip(),
                    str(row.get("channel", "")).strip(),
                    str(row.get("stage", "")).strip(),
                    str(row.get("status", "")).strip(),
                    str(row.get("notes", "")).strip(),
                ]
                for c, text in enumerate(cols):
                    item = QTableWidgetItem(text)
                    if c in {0, 3, 4}:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if c == 1:
                        item.setData(Qt.ItemDataRole.UserRole, meta)
                    failures_table.setItem(r, c, item)

        activity = model.get("activity") if isinstance(model.get("activity"), list) else []
        activity_table = self._widget("activity_table")
        if activity_table is not None:
            activity_table.setRowCount(len(activity))
            for r, evt in enumerate(activity):
                pid = str((evt or {}).get("profileId", "")).strip()
                role = str((evt or {}).get("role", "")).strip().upper()
                prof_name = str((profiles.get(pid, {}) or {}).get("name", "")).strip()
                channel = f"{prof_name} · {role}" if prof_name and role else (prof_name or role or "—")
                batch_id = str((evt or {}).get("batchId", "")).strip()
                cols = [
                    str((evt or {}).get("ts", "")).strip()[-19:],
                    str((evt or {}).get("kind", "")).strip(),
                    batch_id[-24:] if len(batch_id) > 24 else batch_id,
                    channel,
                    str((evt or {}).get("stage", "")).strip(),
                    str((evt or {}).get("detail", "")).strip(),
                ]
                for c, text in enumerate(cols):
                    item = QTableWidgetItem(text)
                    if c in {0, 4}:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    activity_table.setItem(r, c, item)

        summary_label = self._widget("summary_label")
        if summary_label is not None:
            summary_label.setText(
                f"Rows: {int(model.get('totalRows', 0) or 0)} · "
                f"Active: {int(model.get('activeBatches', 0) or 0)} · "
                f"Failures: {int(model.get('failedItems', 0) or 0)}"
            )
