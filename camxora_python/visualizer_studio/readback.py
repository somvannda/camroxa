"""Framebuffer readback helpers — async PBO overlap and YUV pipe conversion."""

from __future__ import annotations

import os

import moderngl
import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - opencv is a declared dependency
    cv2 = None  # type: ignore[assignment]

_YUV_PIPE_FMTS = frozenset({"yuv420p", "nv12"})


def resolve_pipe_pix_fmt(speed_mode: str) -> str:
    override = str(os.environ.get("CAMXORA_EXPORT_PIPE") or "").strip().lower()
    if override in {"rgba", "nv12", "yuv420p"}:
        return override
    mode = str(speed_mode or "balanced").strip().lower()
    # Balanced/Standard share CQ with fast; keep Master-quality (`quality`) on RGBA/pc
    # so the expensive software scale stays available when explicitly requested.
    if mode in {"fast", "very_fast", "balanced", "draft"}:
        # Planar I420 matches OpenCV COLOR_*2YUV_I420 and is NVENC-native (no UV interleave).
        return "yuv420p"
    # Low-VRAM Pascal (1050 Ti-class): prefer yuv420p even on explicit quality speed
    # unless Master — Master stays RGBA/pc for visual parity on high-end cards.
    if mode == "quality":
        try:
            from visualizer_studio.export_gpu_tier import detect_export_gpu_tier

            if detect_export_gpu_tier() == "low":
                return "yuv420p"
        except Exception:
            pass
    return "rgba"


def pipe_needs_cpu_pack(pipe_pix_fmt: str) -> bool:
    return str(pipe_pix_fmt or "").strip().lower() in _YUV_PIPE_FMTS


def pipe_frame_byte_size(width: int, height: int, pipe_pix_fmt: str) -> int:
    w = int(max(1, width))
    h = int(max(1, height))
    fmt = str(pipe_pix_fmt or "rgba").strip().lower()
    if fmt in _YUV_PIPE_FMTS:
        return (w * h * 3) // 2
    return w * h * 4


def flip_rgba_bytes_vertical(raw_rgba: bytes, width: int, height: int) -> bytes:
    """OpenGL FBO readback is bottom-up; video pipes expect top-down rows."""
    w = int(width)
    h = int(height)
    expected = w * h * 4
    rgba = np.frombuffer(raw_rgba, dtype=np.uint8)
    if rgba.size < expected:
        raise ValueError(f"RGBA buffer too small: {rgba.size} < {expected}")
    rgba = rgba[:expected].reshape(h, w, 4)
    return np.flipud(rgba).tobytes()


def _rgba_bytes_to_nv12_numpy(raw_rgba: bytes, width: int, height: int) -> bytes:
    """Integer BT.601 full-range NV12 (fallback when OpenCV is unavailable)."""
    w = int(width)
    h = int(height)
    expected = w * h * 4
    rgba = np.frombuffer(raw_rgba, dtype=np.uint8)
    if rgba.size < expected:
        raise ValueError(f"RGBA buffer too small: {rgba.size} < {expected}")
    rgba = rgba[:expected].reshape(h, w, 4)
    r16 = rgba[:, :, 0].astype(np.uint16)
    g16 = rgba[:, :, 1].astype(np.uint16)
    b16 = rgba[:, :, 2].astype(np.uint16)
    y = ((77 * r16 + 150 * g16 + 29 * b16 + 128) >> 8).astype(np.uint8)
    ra = (r16[0::2, 0::2] + r16[0::2, 1::2] + r16[1::2, 0::2] + r16[1::2, 1::2]) >> 2
    ga = (g16[0::2, 0::2] + g16[0::2, 1::2] + g16[1::2, 0::2] + g16[1::2, 1::2]) >> 2
    ba = (b16[0::2, 0::2] + b16[0::2, 1::2] + b16[1::2, 0::2] + b16[1::2, 1::2]) >> 2
    rs = ra.astype(np.int16)
    gs = ga.astype(np.int16)
    bs = ba.astype(np.int16)
    u = np.clip((((-43 * rs - 85 * gs + 128 * bs + 128) >> 8) + 128), 0, 255).astype(np.uint8)
    v = np.clip((((128 * rs - 107 * gs - 21 * bs + 128) >> 8) + 128), 0, 255).astype(np.uint8)
    out = np.empty((w * h * 3) // 2, dtype=np.uint8)
    out[: w * h] = y.reshape(-1)
    uv = out[w * h :].reshape(h // 2, w)
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    return out.tobytes()


def _rgba_bytes_to_yuv420p_numpy(raw_rgba: bytes, width: int, height: int) -> bytes:
    """Integer BT.601 full-range planar I420 (fallback when OpenCV is unavailable)."""
    w = int(width)
    h = int(height)
    expected = w * h * 4
    rgba = np.frombuffer(raw_rgba, dtype=np.uint8)
    if rgba.size < expected:
        raise ValueError(f"RGBA buffer too small: {rgba.size} < {expected}")
    rgba = rgba[:expected].reshape(h, w, 4)
    r16 = rgba[:, :, 0].astype(np.uint16)
    g16 = rgba[:, :, 1].astype(np.uint16)
    b16 = rgba[:, :, 2].astype(np.uint16)
    y = ((77 * r16 + 150 * g16 + 29 * b16 + 128) >> 8).astype(np.uint8)
    ra = (r16[0::2, 0::2] + r16[0::2, 1::2] + r16[1::2, 0::2] + r16[1::2, 1::2]) >> 2
    ga = (g16[0::2, 0::2] + g16[0::2, 1::2] + g16[1::2, 0::2] + g16[1::2, 1::2]) >> 2
    ba = (b16[0::2, 0::2] + b16[0::2, 1::2] + b16[1::2, 0::2] + b16[1::2, 1::2]) >> 2
    rs = ra.astype(np.int16)
    gs = ga.astype(np.int16)
    bs = ba.astype(np.int16)
    u = np.clip((((-43 * rs - 85 * gs + 128 * bs + 128) >> 8) + 128), 0, 255).astype(np.uint8)
    v = np.clip((((128 * rs - 107 * gs - 21 * bs + 128) >> 8) + 128), 0, 255).astype(np.uint8)
    out = np.empty((w * h * 3) // 2, dtype=np.uint8)
    y_size = w * h
    chroma = y_size // 4
    out[:y_size] = y.reshape(-1)
    out[y_size : y_size + chroma] = u.reshape(-1)
    out[y_size + chroma :] = v.reshape(-1)
    return out.tobytes()


def _rgba_view(raw_rgba: bytes | bytearray | memoryview, width: int, height: int) -> np.ndarray:
    w = int(width)
    h = int(height)
    expected = w * h * 4
    rgba = np.frombuffer(raw_rgba, dtype=np.uint8, count=expected)
    if rgba.size < expected:
        raise ValueError(f"RGBA buffer too small: {rgba.size} < {expected}")
    return rgba.reshape(h, w, 4)


def _rgba_to_nv12_cv2_array(raw_rgba: bytes | bytearray | memoryview, width: int, height: int) -> np.ndarray:
    w = int(width)
    h = int(height)
    rgba = _rgba_view(raw_rgba, w, h)
    # OpenCV returns planar I420 packed as (h * 3/2, w).
    i420 = cv2.cvtColor(rgba, cv2.COLOR_RGBA2YUV_I420)
    flat = i420.reshape(-1)
    y_size = w * h
    chroma = y_size // 4
    out = np.empty(y_size + y_size // 2, dtype=np.uint8)
    out[:y_size] = flat[:y_size]
    uv = out[y_size:].reshape(-1, 2)
    uv[:, 0] = flat[y_size : y_size + chroma]
    uv[:, 1] = flat[y_size + chroma :]
    return out


def _rgba_bytes_to_nv12_cv2(raw_rgba: bytes, width: int, height: int) -> bytes:
    """OpenCV BT.601 limited-range I420 → NV12."""
    return _rgba_to_nv12_cv2_array(raw_rgba, width, height).tobytes()


def rgba_bytes_to_nv12(raw_rgba: bytes, width: int, height: int) -> bytes:
    """Convert RGBA8888 readback bytes to NV12 (BT.601).

    Prefers OpenCV (limited/TV range). Callers must tag ffmpeg ``-color_range tv``
    for the OpenCV path.
    """
    w = int(width)
    h = int(height)
    if w % 2 != 0 or h % 2 != 0:
        raise ValueError("NV12 requires even width and height")
    if cv2 is not None:
        return _rgba_bytes_to_nv12_cv2(raw_rgba, w, h)
    return _rgba_bytes_to_nv12_numpy(raw_rgba, w, h)


def rgba_bytes_to_yuv420p(raw_rgba: bytes, width: int, height: int) -> bytes:
    """Convert RGBA8888 to planar I420 / ffmpeg ``yuv420p`` (BT.601)."""
    w = int(width)
    h = int(height)
    if w % 2 != 0 or h % 2 != 0:
        raise ValueError("yuv420p requires even width and height")
    if cv2 is not None:
        rgba = _rgba_view(raw_rgba, w, h)
        return cv2.cvtColor(rgba, cv2.COLOR_RGBA2YUV_I420).reshape(-1).tobytes()
    return _rgba_bytes_to_yuv420p_numpy(raw_rgba, w, h)


def nv12_color_range() -> str:
    """ffmpeg ``-color_range`` value matching OpenCV YUV converters (tv) or NumPy (pc)."""
    return "tv" if cv2 is not None else "pc"


yuv_pipe_color_range = nv12_color_range


class PipeFramePacker:
    """Reusable RGBA→YUV packer for the encode writer thread.

    Preallocates the OpenCV destination so pack stays ~sub-ms idle (vs ~6–14 ms
    with per-frame alloc + NV12 UV interleave).
    """

    def __init__(self, width: int, height: int, pipe_pix_fmt: str) -> None:
        self._w = int(width)
        self._h = int(height)
        self._fmt = str(pipe_pix_fmt or "rgba").strip().lower()
        if self._w % 2 != 0 or self._h % 2 != 0:
            raise ValueError(f"{self._fmt} requires even width and height")
        self._i420: np.ndarray | None = None
        self._nv12: np.ndarray | None = None
        if cv2 is not None and self._fmt in _YUV_PIPE_FMTS:
            self._i420 = np.empty((self._h * 3 // 2, self._w), dtype=np.uint8)
            if self._fmt == "nv12":
                self._nv12 = np.empty((self._w * self._h * 3) // 2, dtype=np.uint8)

    def __call__(self, raw_rgba: bytes | bytearray | memoryview) -> bytes | np.ndarray:
        if self._fmt == "yuv420p":
            if self._i420 is not None:
                rgba = _rgba_view(raw_rgba, self._w, self._h)
                cv2.cvtColor(rgba, cv2.COLOR_RGBA2YUV_I420, dst=self._i420)
                return self._i420.reshape(-1)
            return rgba_bytes_to_yuv420p(bytes(raw_rgba), self._w, self._h)
        if self._fmt == "nv12":
            if self._i420 is not None and self._nv12 is not None:
                rgba = _rgba_view(raw_rgba, self._w, self._h)
                cv2.cvtColor(rgba, cv2.COLOR_RGBA2YUV_I420, dst=self._i420)
                flat = self._i420.reshape(-1)
                y_size = self._w * self._h
                chroma = y_size // 4
                out = self._nv12
                out[:y_size] = flat[:y_size]
                uv = out[y_size:].reshape(-1, 2)
                uv[:, 0] = flat[y_size : y_size + chroma]
                uv[:, 1] = flat[y_size + chroma :]
                return out
            return _rgba_to_nv12_cv2_array(raw_rgba, self._w, self._h) if cv2 is not None else rgba_bytes_to_nv12(
                bytes(raw_rgba), self._w, self._h
            )
        return bytes(raw_rgba)


def prepare_pipe_payload(
    raw_rgba: bytes | bytearray | memoryview,
    width: int,
    height: int,
    pipe_pix_fmt: str,
) -> bytes | np.ndarray:
    """Pack GL readback for ffmpeg. Y-flip is done in the GPU readback blit pass.

    Returns ``bytes`` for RGBA passthrough, or a contiguous ``uint8`` ndarray for YUV
    (stdin.write accepts the buffer protocol — avoids an extra ``tobytes()`` copy).
    """
    fmt = str(pipe_pix_fmt or "rgba").strip().lower()
    if fmt == "yuv420p":
        w = int(width)
        h = int(height)
        if w % 2 != 0 or h % 2 != 0:
            raise ValueError("yuv420p requires even width and height")
        if cv2 is not None:
            rgba = _rgba_view(raw_rgba, w, h)
            return cv2.cvtColor(rgba, cv2.COLOR_RGBA2YUV_I420).reshape(-1)
        return rgba_bytes_to_yuv420p(bytes(raw_rgba), w, h)
    if fmt == "nv12":
        w = int(width)
        h = int(height)
        if w % 2 != 0 or h % 2 != 0:
            raise ValueError("NV12 requires even width and height")
        if cv2 is not None:
            return _rgba_to_nv12_cv2_array(raw_rgba, w, h)
        return rgba_bytes_to_nv12(bytes(raw_rgba), w, h)
    return bytes(raw_rgba) if not isinstance(raw_rgba, bytes) else raw_rgba


class AsyncFramebufferReader:
    """Double-buffered framebuffer readback to overlap GPU transfer with rendering.

    Optional ``cpu_pool_size`` rotates preallocated CPU bytearrays via Buffer.read_into
    so the render thread avoids allocating a fresh 8 MiB ``bytes`` every frame.
    Pool must be >= encode queue depth + 2 when payloads are queued for pack-on-writer.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        *,
        width: int,
        height: int,
        components: int = 4,
        cpu_pool_size: int | None = None,
    ) -> None:
        self._width = int(width)
        self._height = int(height)
        self._components = int(components)
        self._byte_size = self._width * self._height * self._components
        self._buffers = [ctx.buffer(reserve=self._byte_size) for _ in range(2)]
        self._write_idx = 0
        self._ready_idx: int | None = None
        self._cpu_pool: list[bytearray] | None = None
        self._cpu_pool_idx = 0
        if cpu_pool_size is not None and int(cpu_pool_size) > 0:
            n = int(max(2, cpu_pool_size))
            self._cpu_pool = [bytearray(self._byte_size) for _ in range(n)]

    def queue_frame(self, fbo: moderngl.Framebuffer) -> bytes | bytearray | None:
        """Queue readback for the current frame; returns previous frame bytes if ready."""
        fbo.read_into(
            self._buffers[self._write_idx],
            components=self._components,
            dtype="f1",
            alignment=1,
        )
        previous_idx = self._ready_idx
        self._ready_idx = self._write_idx
        self._write_idx ^= 1
        if previous_idx is None:
            return None
        if self._cpu_pool is not None:
            dest = self._cpu_pool[self._cpu_pool_idx]
            self._cpu_pool_idx = (self._cpu_pool_idx + 1) % len(self._cpu_pool)
            self._buffers[previous_idx].read_into(dest)
            return dest
        # Buffer.read() already returns bytes — avoid a redundant copy.
        return self._buffers[previous_idx].read()

    def flush(self) -> bytes | bytearray | None:
        if self._ready_idx is None:
            return None
        if self._cpu_pool is not None:
            dest = self._cpu_pool[self._cpu_pool_idx]
            self._cpu_pool_idx = (self._cpu_pool_idx + 1) % len(self._cpu_pool)
            self._buffers[self._ready_idx].read_into(dest)
            self._ready_idx = None
            return dest
        data = self._buffers[self._ready_idx].read()
        self._ready_idx = None
        return data
