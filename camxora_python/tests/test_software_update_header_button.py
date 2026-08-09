from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from shared.services.software_update_service import SoftwareUpdateService
from shared.widgets.software_update_header_button import SoftwareUpdateHeaderButton


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _reset_update_service(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "1.2.0",
    )
    monkeypatch.setattr(
        "shared.lib.software_update_persistence.get_updates_work_dir",
        lambda: tmp_path / "updates",
    )
    (tmp_path / "updates").mkdir()
    SoftwareUpdateService._instance = None


def test_header_button_shows_for_session_notice(qapp) -> None:
    del qapp
    button = SoftwareUpdateHeaderButton()
    assert button.isHidden()
    SoftwareUpdateService.instance().apply_session_notice(
        {
            "version": "1.2.1",
            "download_url": "https://example.com/a.exe",
            "mandatory": True,
        }
    )
    assert button.isVisible()
    assert "1.2.1" in button.toolTip()
    assert "Update available" in button.toolTip()
