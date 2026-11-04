"""Native NVENC encode writer — pipelined RGBA→NV12→Annex-B H.264 (REQ-3.5).

When ``CAMXORA_NATIVE_ENCODE=1`` and the DLL loads, export can bypass the ffmpeg
rawvideo pipe for video. Packing runs on a writer thread (like PipelinedEncodeWriter);
``CAMXORA_NATIVE_ENCODE_EXPORT=1`` also enables the path. Audio is remuxed afterward
with ``ffmpeg -c:v copy``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from visualizer.encode_pipeline import BoundedFrameWriter

logger = logging.getLogger(__name__)

_SENTINEL = object()

# NVENC on some GPUs rejects very small surfaces (smoke: 144 failed, 256 ok).
_MIN_NATIVE_DIM = 256


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _env_truthy(name: str) -> bool:
    raw = str(os.environ.get(name, "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def native_encode_preferred() -> bool:
    """Return True when export should try the native NVENC bridge.

    Primary flag: ``CAMXORA_NATIVE_ENCODE=1``. Optional override
    ``CAMXORA_NATIVE_ENCODE_EXPORT=1`` also enables (same effect).
    """
    return _env_truthy("CAMXORA_NATIVE_ENCODE") or _env_truthy(
        "CAMXORA_NATIVE_ENCODE_EXPORT"
    )


def native_encode_dims_ok(width: int, height: int) -> bool:
    return int(width) >= _MIN_NATIVE_DIM and int(height) >= _MIN_NATIVE_DIM


def try_open_native_encode_writer(
    *,
    width: int,
    height: int,
    fps: int,
    h264_path: str,
    bitrate_kbps: int = 0,
) -> NativeEncodeWriter | None:
    """Return a live writer, or None to keep the ffmpeg pipe path."""
    if not native_encode_preferred():
        return None
    if not native_encode_dims_ok(width, height):
        logger.info(
            "native encode skipped: %sx%s below %s min",
            width,
            height,
            _MIN_NATIVE_DIM,
        )
        return None
    try:
        from features.video.services.native_encode_bridge import (
            NativeEncodeSession,
            is_available,
            probe,
        )
    except Exception as exc:
        logger.debug("native encode import failed: %s", exc)
        return None
    if not is_available():
        return None
    try:
        session = NativeEncodeSession(
            width=width,
            height=height,
            fps=fps,
            output_path=h264_path,
            bitrate_kbps=bitrate_kbps,
        )
        session.__enter__()
    except (NotImplementedError, RuntimeError, OSError) as exc:
        logger.info("native encode create failed, pipe fallback: %s", exc)
        return None
    gpu = ""
    try:
        gpu = probe()
    except Exception:
        pass
    logger.info("native NVENC encode active probe=%s out=%s", gpu or "?", h264_path)
    return NativeEncodeWriter(session, h264_path=h264_path, width=width, height=height)


class NativeEncodeWriter(BoundedFrameWriter):
    """Bounded queue + writer thread: pack RGBA→NV12, then native NVENC submit."""

    def __init__(
        self,
        session: Any,
        *,
        h264_path: str,
        width: int,
        height: int,
        queue_size: int | None = None,
    ) -> None:
        self._session = session
        self._h264_path = h264_path
        self._width = int(width)
        self._height = int(height)
        self._stride = self._width * 4
        self._use_nv12 = bool(getattr(session, "supports_nv12", lambda: False)())
        self._pack_times_ms: list[float] = []
        self._submit_encode_times_ms: list[float] = []
        self._frames_encoded = 0
        super().__init__(
            queue_size=queue_size,
            thread_name="camxora-native-encode",
            finish_join_timeout=60.0,
            # Copy so AsyncFramebufferReader / CPU pool can reclaim the buffer.
            copy_on_submit=True,
        )

    @property
    def h264_path(self) -> str:
        return self._h264_path

    def stats(self) -> dict[str, Any]:
        stats = super().stats()
        stats.pop("framesWritten", None)
        stats.update(
            {
                "framesEncoded": self._frames_encoded,
                "backend": "native_nvenc",
                "submitNv12": self._use_nv12,
                "packAvgMs": (
                    (sum(self._pack_times_ms) / len(self._pack_times_ms))
                    if self._pack_times_ms
                    else None
                ),
                "packP95Ms": _percentile(self._pack_times_ms, 95.0),
                "submitEncodeP95Ms": _percentile(self._submit_encode_times_ms, 95.0),
            }
        )
        return stats

    # ── writer hooks ─────────────────────────────────────────────────────────
    def _consume(self, item: Any) -> bool:
        if self._use_nv12:
            packer = self._nv12_packer()
            t_pack = time.perf_counter()
            nv12 = packer(item)
            self._pack_times_ms.append((time.perf_counter() - t_pack) * 1000.0)
            t_enc = time.perf_counter()
            self._session.submit_nv12(nv12, self._width)
        else:
            t_enc = time.perf_counter()
            self._session.submit_rgba(item, self._stride)
        self._submit_encode_times_ms.append((time.perf_counter() - t_enc) * 1000.0)
        self._frames_encoded += 1
        self._frames_written += 1
        return True

    def _on_error(self) -> None:
        # Stop consuming immediately; ``submit()`` re-raises on the render thread.
        self._stop.set()

    def _after_finish(self) -> None:
        self._session.finish()

    def _cleanup(self) -> None:
        try:
            self._session.__exit__(None, None, None)
        except Exception:
            pass

    # ── internals ────────────────────────────────────────────────────────────
    def _nv12_packer(self) -> Any:
        packer = getattr(self, "_packer", None)
        if packer is None:
            from visualizer.readback import PipeFramePacker

            packer = PipeFramePacker(self._width, self._height, "nv12")
            self._packer = packer
        return packer



def remux_native_h264_with_audio(
    *,
    ffmpeg_path: str,
    h264_path: str,
    mp3_path: str,
    out_path: str,
) -> None:
    """Mux Annex-B H.264 + audio into MP4 (video stream copy)."""
    cmd = [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-fflags",
        "+genpts",
        "-i",
        str(h264_path),
        "-i",
        str(mp3_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(out_path),
    ]
    from shared.lib.subprocess_utils import popen_hidden

    err_path = Path(out_path).parent / f"ffmpeg_native_remux_{os.getpid()}.log"
    with open(err_path, "w+", encoding="utf-8") as err_file:
        proc = popen_hidden(cmd, stdin=subprocess.DEVNULL, stderr=err_file)
        code = int(proc.wait())
        if code != 0:
            err_file.seek(0)
            detail = (err_file.read() or "").strip()
            raise RuntimeError(detail or f"native remux failed (exit {code})")
    try:
        err_path.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        Path(h264_path).unlink(missing_ok=True)
    except Exception:
        pass
