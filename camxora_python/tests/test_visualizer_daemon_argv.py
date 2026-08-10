"""Tests for visualizer daemon argv normalization."""

from __future__ import annotations

import os

from features.video.services.visualizer_daemon import VisualizerDaemonClient, _visualizer_daemon_enabled
from visualizer_video.main import normalize_visualizer_job_argv


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
        "visualizer_video.main",
        r"C:\music\song.mp3",
        r"C:\templates\viz.json",
    ]
    normalized = normalize_visualizer_job_argv(argv)
    assert normalized[0] == "visualizer_video.main"
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
            ["python.exe", "-m", "visualizer_video.main", "song.mp3", "tpl.json"],
            cwd=os.getcwd(),
            env=os.environ.copy(),
            on_event=None,
            on_exit=None,
        )
        is None
    )


def test_cancel_active_kills_process_tree(monkeypatch) -> None:
    from features.video.services import visualizer_daemon as vd

    killed: list[object] = []

    class _FakeProc:
        def __init__(self) -> None:
            self.pid = 4242

        def poll(self) -> int | None:
            return None

    def _fake_kill(proc: object) -> None:
        killed.append(proc)

    monkeypatch.setattr(vd, "_terminate_process_tree", _fake_kill)
    client = VisualizerDaemonClient()
    fake = _FakeProc()
    client._proc = fake  # type: ignore[assignment]
    client.cancel_active()
    assert killed == [fake]
    assert client._proc is None
    assert client._cancel_requested is True


def test_export_job_cancel_calls_daemon_when_no_proc(monkeypatch) -> None:
    from features.video.services.export_job import ExportJob, ExportSettings

    calls: list[str] = []

    class _Daemon:
        def cancel_active(self, **kwargs) -> None:  # noqa: ANN003
            calls.append("cancel_active")
            assert "cancel_path" in kwargs

    monkeypatch.setattr(
        "features.video.services.visualizer_daemon.get_visualizer_daemon",
        lambda: _Daemon(),
    )
    monkeypatch.setattr(
        "features.video.lib.export_cancel.request_export_cancel",
        lambda path: None,
    )
    job = ExportJob(
        mp3_path="a.mp3",
        template={},
        background_path="bg.png",
        logo_path="logo.png",
        settings=ExportSettings(
            ffmpeg_path="ffmpeg",
            output_dir=".",
            output_path="out.mp4",
            fps=24,
            width=1280,
            height=720,
        ),
    )
    job.cancel()
    assert job._cancel_requested is True
    assert calls == ["cancel_active"]
