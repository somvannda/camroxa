"""Progress view tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from features.progress.views.progress_view import ProgressView, STAGE_OPTIONS
from features.progress.widgets.error_banner import ERROR_MESSAGE
from features.progress.widgets.operational_rows_card import (
    EMPTY_MESSAGE,
    LOADING_MESSAGE,
    EffectiveProgressRow,
    OperationalRowsCard,
    _COL_CHANNEL,
    _COL_EXPORT,
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


def test_error_banner_without_rows(qapp: QApplication) -> None:
    view = ProgressView(PlatformApi())
    view._on_failed("network")
    assert not view._error_banner.isHidden()
    label = view._error_banner.findChild(QLabel)
    assert label is not None
    assert label.text() == ERROR_MESSAGE
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
