"""Progress view tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from features.progress.views.progress_view import ProgressView
from features.progress.widgets.error_banner import ERROR_MESSAGE
from features.progress.widgets.operational_rows_card import EMPTY_MESSAGE, LOADING_MESSAGE
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
