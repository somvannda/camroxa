"""Regression tests for the "ffmpeg closed our pipe" export failure.

Windows reports a dead child pipe as ``EINVAL (22)`` instead of ``EPIPE (32)``,
which is why exports died with ``FFmpeg pipe closed unexpectedly: (OS Error:
[Errno 22] Invalid argument)`` when ffmpeg had actually exited 0 at the audio
tail.
"""

from __future__ import annotations

import errno
from pathlib import Path

from shared.lib.pipe_errors import is_pipe_closed_error, os_error_suffix
from studio.export.ffmpeg_export import build_export_command


def test_pipe_closed_error_covers_windows_einval() -> None:
    assert is_pipe_closed_error(BrokenPipeError("closed")) is True
    assert is_pipe_closed_error(OSError(errno.EPIPE, "Broken pipe")) is True
    assert is_pipe_closed_error(OSError(errno.EINVAL, "Invalid argument")) is True
    assert is_pipe_closed_error(OSError(errno.ENOSPC, "No space left on device")) is False
    assert is_pipe_closed_error(ValueError("I/O operation on closed file")) is False


def test_os_error_suffix_reports_winerror() -> None:
    exc = OSError(22, "Invalid argument")
    exc.winerror = 232  # type: ignore[attr-defined]
    assert os_error_suffix(exc) == ", winerror 232"
    assert os_error_suffix(OSError(22, "Invalid argument")) == ""


def test_studio_export_command_does_not_use_shortest(tmp_path: Path) -> None:
    """``-shortest`` lets the mixed audio decide when the output ends."""
    cmd = build_export_command(
        ffmpeg_exe="ffmpeg",
        width=1280,
        height=720,
        fps=30.0,
        audio_wav_path=tmp_path / "mixed.wav",
        output_path=tmp_path / "out.mp4",
    )
    assert "-shortest" not in cmd
    assert cmd[cmd.index("-i") + 1] == "-"  # rawvideo stdin
    assert cmd[-1] == str(tmp_path / "out.mp4")
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
