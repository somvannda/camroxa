"""Smoke tests for the native Create workspace."""

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QSizePolicy, QToolButton

from features.create.views.create_view import CreateView
from features.create.widgets.studio_controls import (
    ModeTab,
    StudioCheckBox,
    StudioComboBox,
    StudioDateEdit,
    StudioRadioButton,
)
from shared.constants.navigation import get_route_by_key, get_workspace_routes
from shared.lib.ui_font import ensure_khmer_siemreap_loaded


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_create_route_is_in_workspace() -> None:
    route = get_route_by_key("create")
    assert route.label == "Create"
    assert route.path == "/app/create"
    assert any(item.key == "create" for item in get_workspace_routes())


def test_create_view_builds(qapp: QApplication) -> None:
    view = CreateView()
    assert view.objectName() == "create_workspace"
    assert view.form.advanced_tab.isChecked()
    assert view.planning.count.value() == 4
    assert view.files.table.rowCount() == 12
    assert view.font().pixelSize() == 12


def test_create_controls_match_studio_chrome(qapp: QApplication) -> None:
    view = CreateView()
    assert isinstance(view.planning.from_date, StudioDateEdit)
    assert view.planning.from_date._icon_btn.objectName() == "DateCalendarButton"
    assert view.form.folder_button.text().strip() == "Choose a Save to folder"
    assert view.form._title_block.objectName() == "TransparentBlock"
    assert isinstance(view.planning.primary, StudioComboBox)
    assert view.planning.from_date.maximumWidth() == 132
    assert view.planning.primary.maximumWidth() == 128
    assert view.planning.count.maximumWidth() == 64
    assert isinstance(view.form.simple_tab, ModeTab)
    assert isinstance(view.form.advanced_tab, ModeTab)
    assert view.form.advanced_tab.height() >= 34
    assert isinstance(view.form.model, StudioComboBox)
    assert isinstance(view.form.versions, StudioComboBox)
    radios = view.form.findChildren(StudioRadioButton)
    assert [radio.text() for radio in radios] == ["Male", "Female", "Both"]
    assert radios[0].isChecked()
    checks = view.form.findChildren(StudioCheckBox)
    assert any(box.text() == "Download WAV" for box in checks)
    assert view.form.findChild(QToolButton) is None or all(
        btn.toolTip() != "More information" for btn in view.form.findChildren(QToolButton)
    )
    assert view.form.generate.height() == 44
    assert view.files.table.font().pixelSize() == 15
    assert view.files.table.columnWidth(6) == 96
    combos = view.findChildren(QComboBox)
    assert combos
    assert all(isinstance(combo, StudioComboBox) for combo in combos)
    assert view.findChild(QFrame, "ModeTabRow") is None
    assert view.form.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert view.layout().spacing() == 10
    assert view.layout().contentsMargins().left() == 10


def test_create_khmer_fields_use_siemreap(qapp: QApplication) -> None:
    family = ensure_khmer_siemreap_loaded()
    assert "siemreap" in family.lower().replace(" ", "")
    view = CreateView()
    widgets = (
        view.form.lyrics.editor,
        view.form.styles.editor,
        view.form.title,
        view.form.negative,
        view.files.table,
        view.files.player.track,
    )
    for widget in widgets:
        names = [widget.font().family(), *widget.font().families()]
        assert any("siemreap" in name.lower().replace(" ", "") for name in names), names


def test_create_simple_tab_hides_advanced_fields(qapp: QApplication) -> None:
    view = CreateView()
    view.show()
    qapp.processEvents()
    view.form.simple_tab.click()
    qapp.processEvents()
    assert view.form.lyrics.isVisible()
    assert view.form.styles.isVisible()
    assert not view.form._negative_block.isVisible()
    assert not view.form._gender_block.isVisible()
    assert not view.form.style_influence.isVisible()
    assert not view.form.weirdness.isVisible()
    assert not view.form.audio_weight.isVisible()
    view.form.advanced_tab.click()
    assert view.form._negative_block.isVisible()
    assert view.form._gender_block.isVisible()
    assert view.form.style_influence.isVisible()


def test_create_split_is_sixty_forty(qapp: QApplication) -> None:
    view = CreateView()
    view.resize(1600, 900)
    view.show()
    qapp.processEvents()
    sizes = view.splitter.sizes()
    assert 0.58 <= sizes[0] / sum(sizes) <= 0.62
    view.resize(1920, 1080)
    qapp.processEvents()
    wide = view.splitter.sizes()
    assert 0.58 <= wide[0] / sum(wide) <= 0.62
