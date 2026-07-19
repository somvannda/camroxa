"""Tests for local video template store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from features.video.services import video_local_store
from features.video.services.video_local_store import VideoLocalStore
from shared.lib import app_paths


@pytest.fixture()
def isolated_video_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VideoLocalStore:
    user_templates_path = tmp_path / "user-templates.json"
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setattr(app_paths, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(app_paths, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(app_paths, "get_video_draft_store_dir", lambda: tmp_path / "drafts")
    monkeypatch.setattr(video_local_store, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(video_local_store, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(video_local_store, "get_video_draft_store_dir", lambda: tmp_path / "drafts")
    user_templates_path.write_text(
        json.dumps(
            [
                {
                    "id": "tpl-a",
                    "name": "Template A",
                    "source": "user",
                    "template": {"templateName": "Template A", "style": "straight-bars", "layers": []},
                    "updated_at": "2026-07-08 00:00:00.000",
                },
                {
                    "id": "tpl-b",
                    "name": "Template B",
                    "source": "user",
                    "template": {"templateName": "Template B", "style": "liquid", "layers": []},
                    "updated_at": "2026-07-08 00:00:00.000",
                },
            ]
        ),
        encoding="utf-8",
    )
    prefs_path.write_text(json.dumps({"templateId": "tpl-a"}), encoding="utf-8")
    return VideoLocalStore()


def test_create_blank_template_from_empty_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_templates_path = tmp_path / "user-templates.json"
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setattr(app_paths, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(app_paths, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(app_paths, "get_video_draft_store_dir", lambda: tmp_path / "drafts")
    monkeypatch.setattr(video_local_store, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(video_local_store, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(video_local_store, "get_video_draft_store_dir", lambda: tmp_path / "drafts")

    store = VideoLocalStore()
    empty = store.read_workspace_state()
    assert empty.template_id is None
    assert empty.templates == []

    workspace = store.create_blank_template(name="My First Template")
    assert workspace.template_id
    assert workspace.template_name == "My First Template"
    assert len(workspace.templates) == 1
    assert workspace.template.get("style")
    assert workspace.template.get("layers")


def test_factory_catalog_is_not_auto_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    factory_path = tmp_path / "video_templates_local.json"
    user_templates_path = tmp_path / "user-templates.json"
    prefs_path = tmp_path / "prefs.json"
    factory_path.write_text(
        json.dumps([{"id": "factory-1", "name": "Factory Only", "source": "factory", "template": {}}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(app_paths, "get_video_templates_path", lambda: factory_path)
    monkeypatch.setattr(app_paths, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(app_paths, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(app_paths, "get_video_draft_store_dir", lambda: tmp_path / "drafts")
    monkeypatch.setattr(video_local_store, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(video_local_store, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(video_local_store, "get_video_draft_store_dir", lambda: tmp_path / "drafts")

    store = VideoLocalStore()
    assert store.read_templates() == []
    workspace = store.read_workspace_state()
    assert workspace.templates == []


def test_write_templates_persists_user_overrides(isolated_video_store: VideoLocalStore, tmp_path: Path) -> None:
    isolated_video_store.write_templates(
        [
            {
                "id": "tpl-custom",
                "name": "Custom",
                "source": "user",
                "template": {"templateName": "Custom", "style": "liquid", "layers": []},
                "updated_at": "2026-07-08 00:00:00.000",
            }
        ]
    )
    templates = isolated_video_store.read_templates()
    assert any(item.get("id") == "tpl-custom" for item in templates)


def test_read_workspace_state_selects_pref_template(isolated_video_store: VideoLocalStore) -> None:
    workspace = isolated_video_store.read_workspace_state({"outputResolution": "1920x1080"})
    assert workspace.template_id == "tpl-a"
    assert workspace.template_name == "Template A"
    assert len(workspace.templates) == 2


def test_set_template_updates_prefs(isolated_video_store: VideoLocalStore) -> None:
    workspace = isolated_video_store.set_template("tpl-b")
    assert workspace.template_id == "tpl-b"
    assert workspace.template.get("style") == "liquid"


def test_set_template_restores_saved_logo_and_background(isolated_video_store: VideoLocalStore) -> None:
    isolated_video_store.write_templates(
        [
            {
                "id": "tpl-a",
                "name": "Template A",
                "source": "user",
                "template": {
                    "templateName": "Template A",
                    "style": "straight-bars",
                    "layers": [],
                    "logoPath": "C:/logos/a.png",
                    "previewBackground": "C:/backgrounds/a.png",
                },
                "updated_at": "2026-07-08 00:00:00.000",
            },
            {
                "id": "tpl-b",
                "name": "Template B",
                "source": "user",
                "template": {
                    "templateName": "Template B",
                    "style": "liquid",
                    "layers": [],
                    "logoPath": "C:/logos/b.png",
                    "previewBackground": "C:/backgrounds/b.png",
                },
                "updated_at": "2026-07-08 00:00:00.000",
            },
        ]
    )
    isolated_video_store.write_prefs(
        {
            "templateId": "tpl-a",
            "logoPath": "C:/logos/a.png",
            "backgroundPath": "C:/backgrounds/a.png",
        }
    )

    switched = isolated_video_store.set_template("tpl-b")
    assert switched.logo_path == "C:/logos/b.png"
    assert switched.background_path == "C:/backgrounds/b.png"

    restored = isolated_video_store.set_template("tpl-a")
    assert restored.logo_path == "C:/logos/a.png"
    assert restored.background_path == "C:/backgrounds/a.png"


def test_patch_template_updates_name_and_style(isolated_video_store: VideoLocalStore) -> None:
    workspace = isolated_video_store.patch_template(
        {"templateName": "Renamed", "style": "flying-glow"},
        settings={"outputResolution": "1920x1080"},
    )
    assert workspace.template_name == "Renamed"
    assert workspace.template.get("style") == "flying-glow"


def test_patch_template_persists_preview_background(isolated_video_store: VideoLocalStore) -> None:
    workspace = isolated_video_store.patch_template(
        {
            "templateName": "With Preview BG",
            "previewBackground": "C:/backgrounds/design.png",
            "logoPath": "C:/logos/a.png",
            "previewLogo": "C:/logos/a.png",
        },
        settings={"outputResolution": "1920x1080"},
    )
    assert workspace.template.get("previewBackground") == "C:/backgrounds/design.png"
    assert workspace.background_path == "C:/backgrounds/design.png"

    reread = isolated_video_store.read_workspace_state({"outputResolution": "1920x1080"})
    assert reread.background_path == "C:/backgrounds/design.png"
    assert reread.template.get("previewBackground") == "C:/backgrounds/design.png"


def test_delete_template_falls_back_to_neighbor(isolated_video_store: VideoLocalStore) -> None:
    workspace = isolated_video_store.delete_template("tpl-a")
    assert workspace.template_id == "tpl-b"
    assert len(workspace.templates) == 1


def test_set_mp3_directory_loads_tracks_in_python_app_order(
    isolated_video_store: VideoLocalStore, tmp_path: Path
) -> None:
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    for name in ("10. Last.mp3", "2. Second.mp3", "1. First.mp3", "Bonus.mp3"):
        (music_dir / name).write_bytes(b"mp3")

    workspace = isolated_video_store.set_mp3_directory(str(music_dir))
    names = [item.name for item in workspace.mp3_list]
    # Numeric prefixes sort numerically first, non-numbered names last.
    assert names == ["1. First.mp3", "2. Second.mp3", "10. Last.mp3", "Bonus.mp3"]
    assert workspace.selected_mp3_path == str(music_dir / "1. First.mp3")
    assert workspace.mp3_directory == str(music_dir)

    # The folder and selection survive a fresh workspace read (app restart).
    reread = isolated_video_store.read_workspace_state({"outputResolution": "1920x1080"})
    assert [item.name for item in reread.mp3_list] == names
    assert reread.selected_mp3_path == str(music_dir / "1. First.mp3")
