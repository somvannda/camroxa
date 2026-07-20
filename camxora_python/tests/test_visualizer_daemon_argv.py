"""Tests for visualizer daemon argv normalization."""

from __future__ import annotations

import os

from features.video.services.visualizer_daemon import VisualizerDaemonClient, _visualizer_daemon_enabled
from visualizer.main import normalize_visualizer_job_argv


def test_normalize_strips_frozen_visualizer_flag() -> None:
    argv = [
        r"C:\Program Files\Camxora\Camxora.exe",
        "--visualizer",
        r"C:\music\song.mp3",
        r"C:\templates\viz.json",
        "--outputDir",
        r"C:\out",
    ]
    normalized = normalize_visualizer_job_argv(argv)
    assert normalized[1] == r"C:\music\song.mp3"
    assert "--visualizer" not in normalized


def test_normalize_strips_dev_module_invocation() -> None:
    argv = [
        r"C:\Python\python.exe",
        "-m",
        "visualizer.main",
        r"C:\music\song.mp3",
        r"C:\templates\viz.json",
    ]
    normalized = normalize_visualizer_job_argv(argv)
    assert normalized[0] == "visualizer.main"
    assert normalized[1] == r"C:\music\song.mp3"


def test_normalize_preserves_empty_logo_flag() -> None:
    argv = [
        r"C:\Program Files\Camxora\Camxora.exe",
        "--visualizer",
        r"C:\music\song.mp3",
        r"C:\templates\viz.json",
        "--logo",
        "",
        "--outputDir",
        r"C:\out",
    ]
    normalized = normalize_visualizer_job_argv(argv)
    logo_idx = normalized.index("--logo")
    assert normalized[logo_idx + 1] == ""


def test_normalize_passthrough_already_clean() -> None:
    argv = ["Camxora.exe", r"C:\music\song.mp3", r"C:\templates\viz.json"]
    assert normalize_visualizer_job_argv(argv) == argv


def test_daemon_disabled_by_env_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("CAMXORA_USE_VISUALIZER_DAEMON", "0")
    assert _visualizer_daemon_enabled() is False
    client = VisualizerDaemonClient()
    assert (
        client.run_command(
            ["python.exe", "-m", "visualizer.main", "song.mp3", "tpl.json"],
            cwd=os.getcwd(),
            env=os.environ.copy(),
            on_event=None,
            on_exit=None,
        )
        is None
    )
