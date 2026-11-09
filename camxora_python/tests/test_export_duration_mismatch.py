"""Export start diagnostic: container vs decoded audio duration."""

from __future__ import annotations

import pytest


@pytest.fixture()
def events(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []
    return captured


def test_duration_mismatch_is_logged(events: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    from visualizer import gpu_render

    # Real case from the field: MP3 header reads 211.6s, actual audio 208.6s.
    monkeypatch.setattr("visualizer.audio.probe_audio_duration_sec", lambda _p: 211.6)
    gpu_render._report_duration_mismatch("track.mp3", 208.6, events.append)

    assert len(events) == 1
    assert events[0]["status"] == "log"
    message = events[0]["message"]
    assert "211.60" in message and "208.60" in message and "+3.00" in message


def test_matching_duration_is_silent(events: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    from visualizer import gpu_render

    monkeypatch.setattr("visualizer.audio.probe_audio_duration_sec", lambda _p: 208.7)
    gpu_render._report_duration_mismatch("track.mp3", 208.6, events.append)

    assert events == []


def test_probe_failure_is_silent(events: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    from visualizer import gpu_render

    def _boom(_path: str) -> float:
        raise RuntimeError("ffprobe missing")

    monkeypatch.setattr("visualizer.audio.probe_audio_duration_sec", _boom)
    gpu_render._report_duration_mismatch("track.mp3", 208.6, events.append)

    assert events == []


def test_unknown_probe_duration_is_silent(events: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    from visualizer import gpu_render

    monkeypatch.setattr("visualizer.audio.probe_audio_duration_sec", lambda _p: 0.0)
    gpu_render._report_duration_mismatch("track.mp3", 208.6, events.append)

    assert events == []
