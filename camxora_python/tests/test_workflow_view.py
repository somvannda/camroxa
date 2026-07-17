"""Workflow view tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.workflow.views.workflow_view import WorkflowView
from features.workflow.widgets.error_banner import ERROR_MESSAGE
from features.workflow.widgets.empty_state import EMPTY_TITLE, LOADING_TITLE
from shared.models.platform import ProgressListResponse, ProgressRow, ProgressRowMeta
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


def test_loading_empty_state(qapp: QApplication) -> None:
    view = WorkflowView(PlatformApi())
    view.show()
    assert view._empty_state._title.text() == LOADING_TITLE


def test_stale_data_on_error(qapp: QApplication) -> None:
    view = WorkflowView(PlatformApi())
    row = _sample_row()
    result = WorkflowLoadResult(response=ProgressListResponse(rows=[row]), runtime_by_key={})
    view._on_loaded(result)
    view._on_failed("network")
    assert not view._content.isHidden()
    assert not view._error_banner.isHidden()
    assert view._selected_panel._channel.text() == "OK Channel"


def test_error_banner(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    view = WorkflowView(PlatformApi())
    view._on_failed("network")
    assert not view._error_banner.isHidden()
    label = view._error_banner.findChild(QLabel)
    assert label is not None
    assert label.text() == ERROR_MESSAGE
    assert view._empty_state._title.text() == EMPTY_TITLE


def test_success_bind_lane_and_steps(qapp: QApplication) -> None:
    view = WorkflowView(PlatformApi())
    row = _sample_row()
    result = WorkflowLoadResult(response=ProgressListResponse(rows=[row]), runtime_by_key={})
    view._on_loaded(result)
    assert not view._content.isHidden()
    assert view._stats_row._runs_card._value.text() == "1"
    assert view._lane_list._list.count() == 1
    assert "OK Channel" in view._lane_list._list.item(0).text()
    assert view._selected_panel._channel.text() == "OK Channel"
    assert len(view._selected_panel._stage_cards) == 5


def test_asset_panel_hides_reel_when_not_included(qapp: QApplication) -> None:
    view = WorkflowView(PlatformApi())
    row = _sample_row()
    row.meta.long_ready = True
    row.meta.reel_ready = False
    result = WorkflowLoadResult(response=ProgressListResponse(rows=[row]), runtime_by_key={})
    view._on_loaded(result)
    asset_texts = []
    body = view._selected_panel._assets_panel._body
    for index in range(body.count()):
        widget = body.itemAt(index).widget()
        if widget is not None:
            asset_texts.append(widget.text())
    assert any(text.startswith("Long ") for text in asset_texts)
    assert not any(text.startswith("Reel ") for text in asset_texts)
