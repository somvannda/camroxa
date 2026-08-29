"""Progress view tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_controls import StudioCheckBox, StudioComboBox, StudioDateEdit
from features.progress.views.progress_view import ProgressView, STAGE_OPTIONS
from features.progress.widgets.error_banner import ERROR_MESSAGE
from features.progress.widgets.operational_rows_card import (
    EMPTY_MESSAGE,
    LOADING_MESSAGE,
    TABLE_HEADERS,
    EffectiveProgressRow,
    OperationalRowsCard,
    _COL_CHANNEL,
    _COL_EXPORT,
    _COL_MERGE,
    _COL_STAGE,
    _EXPORT_COLUMN_WIDTH,
    _MERGE_COLUMN_WIDTH,
    _ROW_HEIGHT,
    _STAGE_COLUMN_WIDTH,
)
from shared.models.platform import ProgressListResponse, ProgressRow, ProgressRowMeta, UserSettingsResponse
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import WorkflowLoadResult


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _sample_row() -> ProgressRow:
    return ProgressRow(
        batch="abc123",
        run_date="2026-07-07",
        channel="OK Channel",
        status="Running",
        music="2/5",
        image="1/2",
        converter="Pending",
        merge="Pending",
        youtube="Pending",
        stage="Music",
        notes="Working",
        updated="14:00:00",
        meta=ProgressRowMeta(
            batch_id="batch-1",
            profile_id="profile-1",
            role="primary",
            expected=5,
            saved=2,
            bg_ready=1,
            bg_total=2,
            th_ready=1,
            th_total=2,
        ),
    )


def test_loading_state(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view.show()
    assert view._summary_label.text() == "Loading progress rows..."
    assert view._rows_card._table.item(0, 0).text() == LOADING_MESSAGE


def test_progress_uses_studio_header_controls(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view.show()
    header = view.widget().findChild(CreateHeader)
    assert header is not None
    assert header.objectName() == "CreateHeader"
    assert view.objectName() == "progress_workspace"
    assert isinstance(view._from_date, StudioDateEdit)
    assert isinstance(view._to_date, StudioDateEdit)
    assert isinstance(view._active_only, StudioCheckBox)
    assert isinstance(view._limit, StudioComboBox)
    assert isinstance(view._stage_filter, StudioComboBox)
    assert view._refresh_btn.objectName() == "SecondaryButton"
    assert header.findChild(StudioDateEdit) is None
    rows_index = view.widget().layout().indexOf(view._rows_splitter)
    filter_index = view.widget().layout().indexOf(view._filter_strip)
    assert 0 <= filter_index < rows_index


def test_error_banner_without_rows(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view._on_failed("network")
    assert not view._error_banner.isHidden()
    assert view._error_banner._label.text() == ERROR_MESSAGE
    assert view._rows_card._table.item(0, 0).text() == EMPTY_MESSAGE


def test_stale_data_on_error(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    row = _sample_row()
    result = WorkflowLoadResult(response=ProgressListResponse(rows=[row]), runtime_by_key={})
    view._on_loaded(result)
    view._on_failed("network")
    assert not view._error_banner.isHidden()
    assert view._rows_card._table.rowCount() == 1
    assert view._stats_row._active_card._value.text() == "1"


def test_success_binds_stats_and_table(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    row = _sample_row()
    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=[row], summary="Ready"),
        runtime_by_key={},
    )
    view._on_loaded(result)
    assert view._stats_row._active_card._value.text() == "1"
    run_cell = view._rows_card._table.item(0, 0).text()
    assert run_cell == "2026-07-07"
    view._rows_card._table.selectRow(0)
    assert "batch-1" in view._detail_card._batch_id.text()
    assert "Ready" in view._summary_label.text()


def test_manual_mode_banner(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view.show()
    view._on_settings_loaded(UserSettingsResponse.model_validate({"imageSourceMode": "manual"}))
    assert not view._manual_banner.isHidden()


def _effective_row(**overrides: object) -> EffectiveProgressRow:
    row = _sample_row()
    if "row" in overrides and isinstance(overrides["row"], ProgressRow):
        row = overrides["row"]
    return EffectiveProgressRow(
        row=row,
        effective_status=str(overrides.get("effective_status", row.status)),
        effective_converter=str(overrides.get("effective_converter", row.converter)),
        effective_merge=str(overrides.get("effective_merge", row.merge)),
        effective_stage=str(overrides.get("effective_stage", row.stage)),
        effective_notes=str(overrides.get("effective_notes", row.notes)),
        effective_converter_percent=overrides.get("effective_converter_percent"),  # type: ignore[arg-type]
        effective_merge_percent=overrides.get("effective_merge_percent"),  # type: ignore[arg-type]
    )


def test_set_rows_clears_stale_export_widgets(qapp: QApplication) -> None:
    card = OperationalRowsCard()
    export_pending = _effective_row(
        effective_stage="Export",
        effective_status="Pending",
        effective_converter="Pending · no exports yet",
    )
    music_row = _effective_row(effective_stage="Music", effective_status="Running")

    card.set_rows([export_pending, export_pending, export_pending])
    for row_index in range(3):
        assert card._table.cellWidget(row_index, _COL_EXPORT) is not None

    card.set_rows([music_row, music_row, music_row])
    for row_index in range(3):
        assert card._table.cellWidget(row_index, _COL_EXPORT) is None
        channel_item = card._table.item(row_index, _COL_CHANNEL)
        assert channel_item is not None
        assert "OK Channel" in channel_item.text()


def test_stage_filter_meta_shows_loaded_and_visible_counts(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    rows = [
        _sample_row().model_copy(update={"stage": "Music", "channel": f"Channel {index}"})
        for index in range(3)
    ]
    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=rows, summary="3 rows loaded"),
        runtime_by_key={},
    )
    view._on_loaded(result)

    export_index = next(index for index, (label, _) in enumerate(STAGE_OPTIONS) if label == "Export")
    view._stage_filter.setCurrentIndex(export_index)
    view._render_table()

    assert "0 visible rows" in view._meta_label.text()
    assert "3 loaded rows" in view._meta_label.text()
    assert view._rows_card._table.item(0, 0).text() == EMPTY_MESSAGE


def test_stage_filter_matches_converter_alias(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    row = _sample_row().model_copy(update={"stage": "Converter"})
    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=[row], summary="1 rows loaded"),
        runtime_by_key={},
    )
    view._on_loaded(result)

    export_index = next(index for index, (label, _) in enumerate(STAGE_OPTIONS) if label == "Export")
    view._stage_filter.setCurrentIndex(export_index)
    view._render_table()

    assert "1 visible row" in view._meta_label.text()
    assert view._rows_card._table.rowCount() == 1
    assert view._rows_card._table.item(0, _COL_CHANNEL) is not None


def test_active_only_then_limit_fills_display_slots(qapp: QApplication) -> None:
    """Active only + Limit=10 means up to 10 active rows, not 10 mixed then drop Done."""
    from features.progress.views.progress_view import filter_effective_progress_rows

    entries = [
        _effective_row(
            row=_sample_row().model_copy(update={"channel": f"Done {index}", "stage": "Done"}),
            effective_stage="Done",
        )
        for index in range(8)
    ] + [
        _effective_row(
            row=_sample_row().model_copy(update={"channel": f"Music {index}", "stage": "Music"}),
            effective_stage="Music",
        )
        for index in range(12)
    ]

    filtered = filter_effective_progress_rows(
        entries,
        active_only=True,
        stage="all",
        limit=10,
    )
    assert len(filtered) == 10
    assert all(entry.effective_stage == "Music" for entry in filtered)


def test_active_only_hides_idle_long_completed_keeps_youtube(qapp: QApplication) -> None:
    from features.progress.views.progress_view import filter_effective_progress_rows

    idle = _effective_row(
        row=_sample_row().model_copy(
            update={"stage": "Merge", "status": "Completed", "merge": "Long completed"}
        ),
        effective_stage="Merge",
        effective_status="Completed",
        effective_merge="Long completed",
    )
    youtube = _effective_row(
        row=_sample_row().model_copy(update={"stage": "YouTube", "status": "In Progress"}),
        effective_stage="YouTube",
        effective_status="In Progress",
    )
    music = _effective_row(
        row=_sample_row().model_copy(update={"stage": "Music", "status": "Running"}),
        effective_stage="Music",
        effective_status="Running",
    )
    filtered = filter_effective_progress_rows(
        [idle, youtube, music],
        active_only=True,
        stage="all",
        limit=None,
    )
    assert [entry.effective_stage for entry in filtered] == ["YouTube", "Music"]


def test_stage_filter_applies_before_limit(qapp: QApplication) -> None:
    from features.progress.views.progress_view import filter_effective_progress_rows

    entries = [
        _effective_row(effective_stage="Music"),
        _effective_row(effective_stage="Export"),
        _effective_row(effective_stage="Converter"),
        _effective_row(effective_stage="Image"),
        _effective_row(effective_stage="Export"),
    ]
    filtered = filter_effective_progress_rows(
        entries,
        active_only=False,
        stage="export",
        limit=2,
    )
    assert len(filtered) == 2
    assert {entry.effective_stage for entry in filtered} <= {"Export", "Converter"}


def test_progress_view_api_filters_overfetch_without_server_active_only(
    qapp: QApplication,
) -> None:
    view = ProgressView(PlatformApi())
    view._limit.setCurrentText("10")
    view._active_only.setChecked(True)
    filters = view._current_filters()
    assert filters.active_only is False
    assert filters.limit == 50


def test_change_run_folder_auto_continues_matching_row_once(qapp: QApplication) -> None:
    """After "Change Run Folder & Resume", the next refresh runs Continue Progress
    exactly once for that row — not the whole pipeline, and not repeated on later
    unrelated refreshes."""
    view = ProgressView(PlatformApi())
    row = _sample_row().model_copy(
        update={"meta": _sample_row().meta.model_copy(update={"role": "OK"})}
    )
    view._pending_auto_continue_key = ("batch-1", "profile-1", "OK")
    view._continue_progress = MagicMock()  # type: ignore[method-assign]

    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=[row], summary="Ready"),
        runtime_by_key={},
    )
    view._on_loaded(result)

    assert view._pending_auto_continue_key is None
    view._continue_progress.assert_called_once()
    (called_entry,) = view._continue_progress.call_args.args
    assert isinstance(called_entry, EffectiveProgressRow)
    assert called_entry.row.meta.batch_id == "batch-1"

    # A later, unrelated refresh must not re-trigger Continue Progress.
    view._continue_progress.reset_mock()
    view._on_loaded(result)
    view._continue_progress.assert_not_called()


def test_change_run_folder_recreates_channel_and_album_subfolders(
    qapp: QApplication, monkeypatch
) -> None:
    """Picking a new drive/folder must recreate {channel}/{date_album} underneath
    it — mirroring how a batch is generated — instead of dumping files flat into
    whatever folder the user picked."""
    import features.progress.views.progress_view as progress_view_module

    view = ProgressView(PlatformApi())
    row = _sample_row().model_copy(
        update={
            "meta": _sample_row().meta.model_copy(
                update={"run_dir": r"E:\SUNO\bass-drive\2026-08-02_Grateful-Hearts-Rest"}
            )
        }
    )

    monkeypatch.setattr(
        progress_view_module.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: r"D:\NewDrive"),
    )

    created_workers: list[MagicMock] = []

    def fake_worker(api, *, batch_id, profile_id, role, new_run_dir, parent=None):
        worker = MagicMock()
        worker.new_run_dir = new_run_dir
        worker.succeeded = MagicMock()
        worker.failed = MagicMock()
        worker.finished = MagicMock()
        worker.isRunning.return_value = False
        created_workers.append(worker)
        return worker

    monkeypatch.setattr(progress_view_module, "RunFolderRecoveryWorker", fake_worker)

    view._change_run_folder(row)

    assert len(created_workers) == 1
    assert created_workers[0].new_run_dir == r"D:\NewDrive\bass-drive\2026-08-02_Grateful-Hearts-Rest"


def test_change_run_folder_rejects_when_recreated_path_matches_current(
    qapp: QApplication, monkeypatch
) -> None:
    """If the picked folder's recreated {channel}/{date_album} path resolves back
    to the row's current run_dir, this must be treated as a no-op, not a move."""
    import features.progress.views.progress_view as progress_view_module

    view = ProgressView(PlatformApi())
    current = r"E:\SUNO\bass-drive\2026-08-02_Grateful-Hearts-Rest"
    row = _sample_row().model_copy(
        update={"meta": _sample_row().meta.model_copy(update={"run_dir": current})}
    )

    monkeypatch.setattr(
        progress_view_module.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: r"E:\SUNO"),
    )

    created_workers: list[MagicMock] = []
    monkeypatch.setattr(
        progress_view_module,
        "RunFolderRecoveryWorker",
        lambda *a, **k: created_workers.append(k) or MagicMock(),
    )

    view._show_retry_notice = MagicMock()  # type: ignore[method-assign]
    view._change_run_folder(row)

    assert created_workers == []
    view._show_retry_notice.assert_called_once_with("That is already this row's run folder.")


def test_flush_pending_auto_continue_noop_when_row_not_found(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view._pending_auto_continue_key = ("missing-batch", "missing-profile", "OK")
    view._continue_progress = MagicMock()  # type: ignore[method-assign]

    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=[_sample_row()], summary="Ready"),
        runtime_by_key={},
    )
    view._on_loaded(result)

    assert view._pending_auto_continue_key is None
    view._continue_progress.assert_not_called()


def test_finished_rows_allow_explicit_rebuild_not_continue_export() -> None:
    row = _sample_row()
    row.stage = "Done"
    row.meta.run_dir = r"C:\Media\Suno\channel\2026-07-07_Album"
    row.meta.long_ready = True
    entry = EffectiveProgressRow(
        row=row,
        effective_status="Done",
        effective_converter="Completed",
        effective_merge="Completed",
        effective_stage="Done",
        effective_notes="",
    )
    assert OperationalRowsCard._is_pipeline_finished(entry) is True
    assert OperationalRowsCard._can_show_start_export(entry) is False
    assert OperationalRowsCard._can_start_video_merge(entry) is False
    assert OperationalRowsCard._can_start_video_export(entry) is True


def test_stage_column_uses_compact_badge_and_progress_bar(qapp: QApplication) -> None:
    card = OperationalRowsCard()
    card.set_rows([_effective_row(effective_stage="Completed")])
    qapp.processEvents()
    assert card._table.item(0, _COL_STAGE).text() == "Completed"
    assert card._table.cellWidget(0, _COL_STAGE) is not None
    assert card._table.columnWidth(_COL_STAGE) == _STAGE_COLUMN_WIDTH
    assert card._table.columnWidth(_COL_EXPORT) == _EXPORT_COLUMN_WIDTH
    assert card._table.columnWidth(_COL_MERGE) == _MERGE_COLUMN_WIDTH
    assert "YouTube" not in TABLE_HEADERS
    assert card._table.columnCount() == 10
    assert card._table.rowHeight(0) == _ROW_HEIGHT
    from PySide6.QtWidgets import QProgressBar

    progress = card._table.cellWidget(0, 4)
    assert progress is not None
    assert progress.findChild(QProgressBar) is not None


def test_detail_card_uses_compact_title_and_pipeline_rows(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view.show()
    row = _sample_row()
    row.album = "Northbound Nerve Surge"
    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=[row], summary="Ready"),
        runtime_by_key={},
    )
    view._on_loaded(result)
    view._rows_card._table.selectRow(0)
    qapp.processEvents()
    detail = view._detail_card
    assert detail._header.objectName() == "ProgressDetailTitle"
    assert detail._header.text() == "Northbound Nerve Surge"
    assert "OK Channel" in detail._meta.text()
    assert "batch-1" in detail._batch_id.text()
    assert "Pending" in detail._converter_label.text()
    assert detail._status_badge.text() == "Running"
    assert "Music / Running" in detail._state.text()
    assert detail._open_run_btn.text() == "Open Run Folder"
    assert detail._status_badge.property("tone") == "active"
    assert "PIPELINE STATUS" in " ".join(
        child.text()
        for child in detail._content.findChildren(QLabel)
        if child.objectName() == "ProgressDetailSection"
    )


def test_detail_status_tones_pending_vs_downloading() -> None:
    from features.progress.widgets.progress_detail_card import _status_tone

    assert _status_tone("Pending · no exports yet") == "warning"
    assert _status_tone("Downloading") == "active"
    assert _status_tone("Completed") == "success"
    assert _status_tone("—") == "muted"
    assert _status_tone("Not started") == "muted"


def test_export_not_ready_moves_to_detail_status(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view.show()
    row = _sample_row()
    result = WorkflowLoadResult(
        response=ProgressListResponse(rows=[row], summary="Ready"),
        runtime_by_key={},
    )
    view._on_loaded(result)
    view._rows_card._table.selectRow(0)
    view._warning_banner.set_message("Export not ready:\n• leftover")
    view._update_export_validation()
    assert view._warning_banner.isHidden()
    assert view._warning_banner._label.text() == ""
    view._detail_card.set_export_issues(
        [
            r"Run folder does not exist: C:\Users\Kong Somvannda\AppData\Local\Camxora\Media\Suno\bass-ignition\2028-08-10_Desert-Signal-Reverie",
            "Local long branch assets incomplete: background.",
        ]
    )
    assert view._warning_banner.isHidden()
    assert view._detail_card._notes.wordWrap() is True
    assert view._detail_card._state.wordWrap() is True
    assert "Export not ready" in view._detail_card._notes.text()
    assert "Desert-Signal-Reverie" in view._detail_card._notes.text()
    assert view._detail_card._context_title.text() == "STATUS"


def test_detail_completed_hides_waiting_copy(qapp: QApplication) -> None:
    from features.progress.widgets.progress_detail_card import ProgressDetailCard

    card = ProgressDetailCard()
    row = _sample_row()
    row.notes = "Waiting for desktop MP3 downloads"
    card.set_entry(
        _effective_row(
            row=row,
            effective_stage="Completed",
            effective_status="Completed",
            effective_notes="Waiting for desktop MP3 downloads",
            effective_converter="Completed",
            effective_merge="Completed",
        )
    )
    assert card._context_title.text() == "COMPLETED"
    assert card._notes.isHidden()
    assert "songs" in card._completed_summary.text()
