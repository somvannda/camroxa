from pathlib import Path

from studio.core.playlist_assets import (
    bundled_background_path,
    bundled_thumbnail_path,
    ensure_template_background_dir,
    find_background_in_dir,
    find_thumbnail_in_dir,
    playlist_templates_assets_root,
    resolve_playlist_background,
    template_background_dir,
)
from studio.core.playlist_settings import PlaylistSettings


def test_playlist_templates_assets_root_exists():
    root = playlist_templates_assets_root()
    assert root.name == "playlist_templates"
    assert (root / "README.md").is_file()


def test_bundled_minimal_white_background():
    path = bundled_background_path("minimal-white")
    assert path is not None
    assert path.is_file()
    assert path.name == "background.png"


def test_bundled_forest_mist_background_when_present():
    path = bundled_background_path("forest-mist")
    if path is None:
        import pytest

        pytest.skip("add assets/playlist_templates/forest-mist/background.png")
    assert path.is_file()
    assert path.name == "background.png"


def test_resolve_prefers_project_background(tmp_path):
    custom = tmp_path / "custom.png"
    custom.write_bytes(b"fake")
    settings = PlaylistSettings(sub_template_id="minimal-white", background_path=str(custom))
    assert resolve_playlist_background(settings) == custom


def test_find_background_in_dir(tmp_path):
    folder = tmp_path / "test-template"
    folder.mkdir()
    img = folder / "background.png"
    img.write_bytes(b"x")
    assert find_background_in_dir(folder) == img


def test_find_thumbnail_in_dir(tmp_path):
    folder = tmp_path / "test-template"
    folder.mkdir()
    img = folder / "thumbnail.png"
    img.write_bytes(b"x")
    assert find_thumbnail_in_dir(folder) == img


def test_bundled_minimal_white_thumbnail_when_present():
    path = bundled_thumbnail_path("minimal-white")
    if path is None:
        import pytest

        pytest.skip("add assets/playlist_templates/minimal-white/thumbnail.png")
    assert path.is_file()
    assert path.name == "thumbnail.png"


def test_bundled_forest_mist_thumbnail_when_present():
    path = bundled_thumbnail_path("forest-mist")
    if path is None:
        import pytest

        pytest.skip("add assets/playlist_templates/forest-mist/thumbnail.png")
    assert path.is_file()
    assert path.name == "thumbnail.png"


def test_ensure_template_background_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "core.playlist_assets._ASSETS_ROOT",
        tmp_path / "playlist_templates",
    )
    folder = ensure_template_background_dir("cyberpunk")
    assert folder.is_dir()
