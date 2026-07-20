"""ExportJob daemon vs parallel-subprocess routing."""

from __future__ import annotations

from features.video.services.export_job import ExportJob, ExportSettings


def test_export_job_skips_daemon_when_disallowed(monkeypatch) -> None:
    calls: list[str] = []

    class _Daemon:
        def run_command(self, *args, **kwargs):  # noqa: ANN002, ANN003
            calls.append("daemon")
            return 0

    monkeypatch.setattr(
        "features.video.services.visualizer_daemon.get_visualizer_daemon",
        lambda: _Daemon(),
    )

    launched: list[list[str]] = []

    class _Proc:
        def __init__(self) -> None:
            self.stdout = iter([])

        def wait(self) -> int:
            return 0

    def _popen(cmd, **kwargs):  # noqa: ANN001, ANN003
        launched.append(list(cmd))
        calls.append("subprocess")
        return _Proc()

    monkeypatch.setattr(
        "features.video.services.export_job.popen_hidden",
        _popen,
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
    code = job.run_blocking(allow_daemon=False)
    assert code == 0
    assert calls == ["subprocess"]
    assert job.backend_used == "subprocess"
    assert launched


def test_export_job_uses_daemon_when_allowed(monkeypatch) -> None:
    calls: list[str] = []

    class _Daemon:
        def run_command(self, *args, **kwargs):  # noqa: ANN002, ANN003
            calls.append("daemon")
            return 0

    monkeypatch.setattr(
        "features.video.services.visualizer_daemon.get_visualizer_daemon",
        lambda: _Daemon(),
    )

    def _popen(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append("subprocess")
        raise AssertionError("subprocess should not run when daemon succeeds")

    monkeypatch.setattr(
        "features.video.services.export_job.popen_hidden",
        _popen,
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
    code = job.run_blocking(allow_daemon=True)
    assert code == 0
    assert calls == ["daemon"]
    assert job.backend_used == "daemon"
