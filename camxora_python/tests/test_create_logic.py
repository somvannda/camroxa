"""Create studio UI — ported generate / files / download behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from features.create.views.create_view import CreateView
from features.create.widgets.file_panel import FilePanel
from shared.models.web_music import WebMusicClipResponse, WebMusicGenerationResponse
from shared.services.platform_api import PlatformApi


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_create_files_lists_version_tables(qapp: QApplication, tmp_path: Path) -> None:
    version_one = tmp_path / "Version 1"
    version_two = tmp_path / "Version 2"
    version_one.mkdir()
    version_two.mkdir()
    (version_one / "Night Drive.mp3").write_bytes(b"id3")
    (version_one / "Night Drive.lrc").write_text("[00:00.00]night", encoding="utf-8")
    (version_two / "Night Drive.mp3").write_bytes(b"id3")
    card = FilePanel()
    card.set_folder(str(tmp_path))
    assert card.table.columnCount() == 7
    assert card.table.horizontalHeaderItem(1).text() == "Version"
    assert card.table.horizontalHeaderItem(2).text() == "MP3"
    assert card.table.horizontalHeaderItem(6).text() == "State"
    assert card.table.rowCount() == 2
    assert card.table.item(0, 0).text() == "Night Drive"
    assert card.table.item(0, 1).text() == "Version 1"
    assert card.table.item(0, 2).text() == "3 B"
    assert card.table.item(0, 3).text() == "No"
    assert card.table.item(0, 4).text() == "Yes"
    assert card.table.item(0, 5).text() == "No"
    assert card.table.item(1, 0).text() == "Night Drive"
    assert card.table.item(1, 1).text() == "Version 2"
    assert card.table.item(1, 2).text() == "3 B"


def test_create_files_shows_generating_shells_then_ready(qapp: QApplication, tmp_path: Path) -> None:
    card = FilePanel()
    card.set_folder(str(tmp_path))
    card.begin_generate(2, "Night Drive")
    assert card.table.rowCount() == 4
    assert card.table.item(0, 0).text() == "Night Drive (1)"
    assert card.table.item(0, 1).text() == "Version 1"
    assert card.table.item(0, 6).text() == ""
    assert card.row_state(0) == "Generating…"
    card.attach_task(1, "task-1", "Night Drive")
    card.mark_ready(1, "", "")
    assert card.row_state(0) == "Ready"
    card.mark_failed(2)
    assert card.row_state(2) == "Failed"


def test_create_files_loads_database_history_and_search(qapp: QApplication, tmp_path: Path) -> None:
    card = FilePanel()
    card.set_folder(str(tmp_path))
    card.set_history(
        [
            WebMusicGenerationResponse(
                id="aaaa1111-ffff-0000-0000-000000000001",
                title="Rain Song",
                status="success",
                clips=[WebMusicClipResponse(variant="ok", ready=True)],
            ),
            WebMusicGenerationResponse(
                id="bbbb2222-ffff-0000-0000-000000000002",
                title="Sun Walk",
                status="success",
                clips=[WebMusicClipResponse(variant="ok", ready=True)],
            ),
        ]
    )
    assert card.table.rowCount() == 4
    card.search.setText("rain")
    assert card.table.rowCount() == 2
    assert card.table.item(0, 0).text() == "Rain Song"


def test_create_files_click_ready_does_not_download_or_generate(qapp: QApplication) -> None:
    card = FilePanel()
    downloads: list[tuple] = []
    retries: list[tuple] = []
    card.download_requested.connect(lambda *args: downloads.append(args))
    card.retry_download_requested.connect(lambda *args: retries.append(args))
    card.set_history(
        [
            WebMusicGenerationResponse(
                id="abcd1234-ffff-0000-0000-000000000001",
                title="ខ្ញុំមិនចុះចាញ់",
                status="success",
                clips=[WebMusicClipResponse(variant="ok", ready=True)],
            )
        ]
    )
    card._on_cell_double_clicked(0, 0)
    card._on_cell_double_clicked(0, 1)
    assert downloads == []
    assert retries == []
    assert "right-click" in card.player.track.text().lower()


def test_create_files_keeps_title_after_ready(qapp: QApplication, tmp_path: Path) -> None:
    version_one = tmp_path / "Version 1"
    version_one.mkdir()
    path = version_one / "Night Drive (1) abcd1234.mp3"
    path.write_bytes(b"id3")
    card = FilePanel()
    card.set_folder(str(tmp_path))
    card.begin_generate(1, "Night Drive")
    card.mark_ready(1, str(path), "")
    assert card.table.item(0, 0).text() == "Night Drive"


def test_create_player_transport_and_encrypted_guard(qapp: QApplication, tmp_path: Path) -> None:
    version_one = tmp_path / "Version 1"
    version_one.mkdir()
    good = version_one / "Clear Song.mp3"
    good.write_bytes(b"ID3" + b"\x00" * 32)
    bad = version_one / "Locked Song.mp3"
    bad.write_bytes(b"CXO1" + b"\x00" * 32)
    card = FilePanel()
    card.set_folder(str(tmp_path))
    assert card.player.play.text() == "Play"
    assert card.player.stop.text() == "Stop"
    assert card.player.next.text() == "Next"
    assert card.player.back.text() == "Back"
    card.play_path(str(bad))
    assert "Encrypted" in card.player.track.text()
    card.play_path(str(good))
    assert card.player.track.text() == "Clear Song"
    assert card._playlist_index == 0


def test_create_download_uses_file_folder_not_generate_save(qapp: QApplication, tmp_path: Path) -> None:
    version_one = tmp_path / "Downloads" / "Version 1"
    version_one.mkdir(parents=True)
    path = version_one / "Older Hit abcd1234.mp3"
    path.write_bytes(b"ID3")
    generate_folder = tmp_path / "GenerateSave"
    generate_folder.mkdir()
    card = FilePanel()
    card.set_folder(str(generate_folder))
    card.set_history(
        [
            WebMusicGenerationResponse(
                id="abcd1234-ffff-0000-0000-000000000001",
                title="Older Hit",
                status="success",
                clips=[WebMusicClipResponse(variant="ok", ready=True)],
            )
        ]
    )
    card._history[0].path_v1 = str(path)
    picked: list[str] = []
    card.download_requested.connect(lambda *args: picked.append(args[-1]))
    card._emit_download(card._history[0], "mp3", "v1")
    assert picked == [str(tmp_path / "Downloads")]
    assert picked[0] != str(generate_folder)


def test_create_files_double_click_plays_or_opens_without_download(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version_one = tmp_path / "Version 1"
    version_one.mkdir()
    mp3 = version_one / "Stone Beat abcd1234.mp3"
    wav = version_one / "Stone Beat abcd1234.wav"
    lrc = version_one / "Stone Beat abcd1234.lrc"
    mp3.write_bytes(b"ID3" + b"\x00" * 32)
    wav.write_bytes(b"RIFF" + b"\x00" * 32)
    lrc.write_text("[00:00.00]stone", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(
        "features.create.widgets.file_panel.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()),
    )
    card = FilePanel()
    card.set_folder(str(tmp_path))
    card.set_history(
        [
            WebMusicGenerationResponse(
                id="abcd1234-ffff-0000-0000-000000000001",
                title="Stone Beat",
                status="success",
                clips=[WebMusicClipResponse(variant="ok", ready=True)],
            )
        ]
    )
    downloads: list[tuple] = []
    card.download_requested.connect(lambda *args: downloads.append(args))
    played: list[str] = []
    card.play_requested.connect(lambda path: played.append(path))

    assert card.table.rowCount() == 2
    card._on_cell_double_clicked(0, 2)
    assert played == [str(mp3)]
    card._on_cell_double_clicked(0, 3)
    assert played[-1] == str(wav)
    card._on_cell_double_clicked(0, 4)
    assert [Path(path) for path in opened] == [lrc]
    card._on_cell_double_clicked(0, 5)
    assert "right-click" in card.player.track.text().lower()
    assert downloads == []
    assert card.table.item(0, 2).text().endswith("B")
    assert card.table.item(0, 5).text() == "No"


def test_create_form_defaults_and_simple_hides_advanced(qapp: QApplication) -> None:
    view = CreateView()
    view.show()
    qapp.processEvents()
    assert view.form.advanced_tab.isChecked()
    assert view.form.lyrics.editor.isReadOnly()
    assert view.form.model_code() == "V6"
    assert view.form.download_wav.isChecked() is False
    assert view.form.vocal_gender() is None
    view.form.simple_tab.click()
    qapp.processEvents()
    assert view.form.mode() == "simple"
    assert view.form.lyrics.isVisible()
    assert not view.form.style_influence.isVisible()


def test_create_generate_requires_save_folder(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        "features.create.views.create_view.emit_footer_error",
        lambda message: messages.append(message),
    )
    view = CreateView(PlatformApi())
    view.form.styles.editor.setPlainText("rock")
    view.form.simple_tab.click()
    view._on_generate()
    assert messages == ["Choose a Save to folder before generating."]
    assert view.form.status.text() == ""
    assert view.form.generate.isEnabled()
