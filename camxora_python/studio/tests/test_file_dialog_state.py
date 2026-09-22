from pathlib import Path

from PySide6.QtCore import QSettings

from studio.app import file_dialog_state


def test_last_open_dir_round_trip(tmp_path: Path, monkeypatch):
    ini = tmp_path / "settings.ini"
    monkeypatch.setattr(file_dialog_state, "_SETTINGS_PATH", ini)

    assert file_dialog_state.last_open_dir("add_song") == ""

    song_dir = tmp_path / "music"
    song_dir.mkdir()
    song_file = song_dir / "track.wav"
    song_file.write_bytes(b"")
    file_dialog_state.set_last_open_dir("add_song", [str(song_file)])

    assert file_dialog_state.last_open_dir("add_song") == str(song_dir)


def test_last_open_dir_ignores_missing_path(tmp_path: Path, monkeypatch):
    ini = tmp_path / "settings.ini"
    monkeypatch.setattr(file_dialog_state, "_SETTINGS_PATH", ini)

    settings = QSettings(str(ini), QSettings.Format.IniFormat)
    settings.setValue("file_dialog/add_song", str(tmp_path / "gone"))
    settings.sync()

    assert file_dialog_state.last_open_dir("add_song") == ""
