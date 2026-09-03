"""Render the full timeline to an MP4 file — frame-accurate offline export.

Reuses the exact same `render_frame()` the live preview uses (guaranteeing
preview/export parity), pipes raw RGB frames into ffmpeg's stdin, and mixes
the full audio timeline deterministically (via `AudioMixer.mix_block`, the
same pure mixing logic the live preview mixer uses) to a temp WAV that
ffmpeg muxes in as the second input — a single ffmpeg process, one pass.

This is an improvement over the reference app (which screen-records the live
canvas in real time): export here is frame-accurate and runs faster than
real-time.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from studio.audio.mixer import AudioMixer
from studio.core.project_state import ProjectState
from studio.media.audio_source import AudioSourceCache
from studio.media.ffmpeg_utils import get_ffmpeg_exe
from studio.media.video_source import VideoSourceCache
from studio.render.compositor import render_frame

logger = logging.getLogger(__name__)

DEFAULT_FPS = 30.0
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_AUDIO_SAMPLE_RATE = 44100
AUDIO_WRITE_BLOCK = 4096

ProgressCallback = Callable[[float], None]
CancelCheck = Callable[[], bool]


class ExportCancelled(Exception):
    pass


class ExportError(Exception):
    pass


def _drain_stderr(stream, chunks: list[bytes]) -> None:
    """Continuously read ffmpeg's stderr in a background thread.

    ffmpeg writes progress/stats to stderr as it encodes. If nothing reads
    that pipe while we're also writing frames to stdin, the OS pipe buffer
    fills up, ffmpeg blocks on its own stderr write, and — since it can't
    make progress — stops reading stdin too, deadlocking the whole export.
    """
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            chunks.append(chunk)
    except (ValueError, OSError):
        pass


def _write_mixed_audio(
    project_state: ProjectState,
    mixer: AudioMixer,
    out_path: Path,
    duration: float,
    sample_rate: int,
) -> None:
    total_samples = max(1, int(round(duration * sample_rate)))
    with sf.SoundFile(str(out_path), mode="w", samplerate=sample_rate, channels=2, subtype="PCM_16") as f:
        written = 0
        while written < total_samples:
            n = min(AUDIO_WRITE_BLOCK, total_samples - written)
            t0 = written / sample_rate
            block = mixer.mix_block(t0, n)
            f.write(block)
            written += n


def export_project(
    project_state: ProjectState,
    output_path: str | Path,
    fps: float = DEFAULT_FPS,
    width: int | None = None,
    height: int | None = None,
    audio_sample_rate: int = DEFAULT_AUDIO_SAMPLE_RATE,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> Path:
    """Render `project_state`'s timeline to `output_path` (.mp4). Returns the
    output path on success; raises `ExportCancelled` / `ExportError` /
    `ValueError` otherwise. Safe to call from a worker thread — does not
    touch any Qt widgets."""
    duration = project_state.project.duration
    if duration <= 0:
        raise ValueError("Nothing to export — the timeline is empty.")

    canvas_w, canvas_h = project_state.canvas_size()
    width = width if width is not None else canvas_w
    height = height if height is not None else canvas_h

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_exe()

    video_cache = VideoSourceCache()
    audio_cache = AudioSourceCache()
    mixer = AudioMixer(project_state, audio_cache, sample_rate=audio_sample_rate, channels=2)

    try:
        with tempfile.TemporaryDirectory(prefix="camxora_export_") as tmp_dir:
            audio_wav_path = Path(tmp_dir) / "mixed_audio.wav"
            _write_mixed_audio(project_state, mixer, audio_wav_path, duration, audio_sample_rate)

            n_frames = max(1, int(round(duration * fps)))
            cmd = [
                ffmpeg_exe, "-y",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
                "-i", str(audio_wav_path),
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(output_path),
            ]
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            assert process.stdin is not None
            assert process.stderr is not None

            stderr_chunks: list[bytes] = []
            stderr_thread = threading.Thread(
                target=_drain_stderr, args=(process.stderr, stderr_chunks), daemon=True
            )
            stderr_thread.start()

            def _stderr_tail() -> str:
                return b"".join(stderr_chunks).decode(errors="ignore")[-2000:]

            try:
                for i in range(n_frames):
                    if cancel_check is not None and cancel_check():
                        process.stdin.close()
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        stderr_thread.join(timeout=5)
                        raise ExportCancelled("Export cancelled by user")

                    t = i / fps
                    frame = render_frame(
                        project_state, t, video_cache, audio_cache=audio_cache, width=width, height=height
                    )
                    process.stdin.write(np.ascontiguousarray(frame).tobytes())

                    if progress_callback is not None:
                        progress_callback((i + 1) / n_frames)

                process.stdin.close()
            except BrokenPipeError as exc:
                process.wait(timeout=10)
                stderr_thread.join(timeout=5)
                raise ExportError(f"ffmpeg exited early: {_stderr_tail()}") from exc

            return_code = process.wait(timeout=600)
            stderr_thread.join(timeout=5)
            if return_code != 0:
                raise ExportError(f"ffmpeg export failed (exit {return_code}): {_stderr_tail()}")

        return output_path
    finally:
        video_cache.release_all()
