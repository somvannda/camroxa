"""Tests for local video workspace draft persistence."""

from __future__ import annotations

from features.video.services import video_draft_store
from features.video.services.video_draft_store import (
    clear_video_workspace_draft_snapshot,
    read_video_workspace_draft_snapshot,
    write_video_workspace_draft_snapshot,
)


def test_video_draft_store_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.services.video_draft_store.get_video_draft_store_dir",
        lambda: tmp_path,
    )
    video_draft_store.reset_video_draft_memory_for_tests()
    persisted = {"style": "classic-vertical", "spectrumEnabled": True}
    write_video_workspace_draft_snapshot(
        "template-1",
        template_name="My Draft",
        draft={**persisted, "audioInputGain": 6.0},
        layers=[{"id": "layer-1", "barWidth": 4.0}],
    )
    snapshot = read_video_workspace_draft_snapshot("template-1", persisted, "Saved Name")
    assert snapshot is not None
    assert snapshot["templateName"] == "My Draft"
    assert snapshot["draft"]["audioInputGain"] == 6.0
    assert snapshot["layers"][0]["barWidth"] == 4.0
    assert not (tmp_path / "template-1.json").is_file()


def test_video_draft_store_clear(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.services.video_draft_store.get_video_draft_store_dir",
        lambda: tmp_path,
    )
    video_draft_store.reset_video_draft_memory_for_tests()
    write_video_workspace_draft_snapshot(
        "template-2",
        template_name="Draft",
        draft={"style": "neon-pulse"},
        layers=[],
    )
    clear_video_workspace_draft_snapshot("template-2")
    assert read_video_workspace_draft_snapshot("template-2", {}, "Draft") is None


def test_video_draft_store_resets_across_process_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.services.video_draft_store.get_video_draft_store_dir",
        lambda: tmp_path,
    )
    video_draft_store.reset_video_draft_memory_for_tests()
    write_video_workspace_draft_snapshot(
        "template-3",
        template_name="Draft",
        draft={"style": "orbit-spikes"},
        layers=[],
    )
    assert read_video_workspace_draft_snapshot("template-3", {}, "Draft") is not None
    video_draft_store.reset_video_draft_memory_for_tests()
    assert read_video_workspace_draft_snapshot("template-3", {}, "Draft") is None
