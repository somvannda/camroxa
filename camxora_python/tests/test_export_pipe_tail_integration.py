"""End-to-end ffmpeg check for the export pipe tail (real binary, no GPU).

Guards the regression behind "FFmpeg pipe closed unexpectedly: (OS Error:
[Errno 22] Invalid argument)": ffmpeg used to stop at the audio tail (because of
``-shortest``) while the encode writer still had frames queued, so the next
stdin write hit a dead pipe. This test drives the *production* pipe command and
the production writer against a real ffmpeg, pushing more frames than the audio
is long, and asserts the pipe stays open and the MP4 keeps the rendered length.

Skipped when ffmpeg/ffprobe are not installed (CI without the bundled tools).
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import pytest

from shared.lib.subprocess_utils import popen_hidden, run_hidden
from visualizer.encode_pipeline import PipelinedEncodeWriter
from visualizer.gpu_render import build_pipe_encode_command

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(
    not FFMPEG or not FFPROBE,
    reason="ffmpeg/ffprobe not installed",
)

W, H, FPS = 320, 180, 30
AUDIO_SEC = 2.0


def _make_audio(path: Path, seconds: float) -> None:
    run_hidden(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:a",
            "libmp3lame",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _probe_duration(path: Path) -> float:
    completed = run_hidden(
        [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(str(completed.stdout or "0").strip() or 0.0)


def test_pipe_accepts_frames_past_the_audio_tail(tmp_path: Path) -> None:
    audio = tmp_path / "track.mp3"
    out = tmp_path / "out.mp4"
    _make_audio(audio, AUDIO_SEC)

    cmd, codec, pipe_fmt = build_pipe_encode_command(
        ffmpeg_path=FFMPEG,
        mp3_path=str(audio),
        out_path=str(out),
        width=W,
        height=H,
        fps=FPS,
        speed_mode="fast",
        pipe_pix_fmt="yuv420p",
        use_nvenc=False,  # software encode keeps this test GPU-free
    )
    assert "-shortest" not in cmd
    assert codec == "libx264"
    assert pipe_fmt == "yuv420p"

    frame_bytes = (W * H * 3) // 2
    frame = bytes(frame_bytes)
    # ceil(audio*fps) is what the renderer writes. Push 50% extra: with the old
    # ``-shortest`` the MP4 came out at exactly the audio length (2.00s for 3.00s
    # of rendered frames) and, depending on timing, ffmpeg exited mid-render and
    # the next write failed with EPIPE / EINVAL.
    rendered_frames = int(math.ceil(AUDIO_SEC * FPS))
    extra_frames = rendered_frames // 2
    total_frames = rendered_frames + extra_frames

    err_path = tmp_path / "ffmpeg_error.log"
    with err_path.open("w+", encoding="utf-8") as err_file:
        proc = popen_hidden(
            cmd,
            stdin=subprocess.PIPE,
            stderr=err_file,
            bufsize=max(1024 * 1024, frame_bytes),
        )
        writer = PipelinedEncodeWriter(
            proc,
            queue_size=2,
            err_file=err_file,
            err_path=str(err_path),
        )
        try:
            for _ in range(total_frames):
                writer.submit(frame)
            writer.finish()  # must not raise: ffmpeg stays alive to the end
            returncode = proc.wait(timeout=180)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=30)

    err_file_text = err_path.read_text(encoding="utf-8").strip()
    assert returncode == 0, err_file_text
    stats = writer.stats()
    assert stats["framesWritten"] == total_frames
    assert stats["framesDropped"] == 0
    assert stats["encoderExitedEarly"] is False

    # The MP4 keeps the rendered length instead of being cut back to the audio.
    duration = _probe_duration(out)
    assert duration == pytest.approx(total_frames / FPS, abs=0.25)
    assert duration > AUDIO_SEC + 0.5
