"""Tests for export readback helpers."""

from __future__ import annotations

import numpy as np

from visualizer.readback import (
    PipeFramePacker,
    flip_rgba_bytes_vertical,
    nv12_color_range,
    pipe_frame_byte_size,
    pipe_needs_cpu_pack,
    prepare_pipe_payload,
    resolve_pipe_pix_fmt,
    rgba_bytes_to_nv12,
    rgba_bytes_to_yuv420p,
)


def test_resolve_pipe_pix_fmt_fast_uses_yuv420p(monkeypatch) -> None:
    from visualizer.export_gpu_tier import clear_export_gpu_tier_cache

    monkeypatch.setenv("CAMXORA_GPU_TIER", "high")
    clear_export_gpu_tier_cache()
    monkeypatch.delenv("CAMXORA_EXPORT_PIPE", raising=False)
    assert resolve_pipe_pix_fmt("fast") == "yuv420p"
    assert resolve_pipe_pix_fmt("very_fast") == "yuv420p"
    assert resolve_pipe_pix_fmt("balanced") == "yuv420p"
    assert resolve_pipe_pix_fmt("quality") == "rgba"


def test_pipe_needs_cpu_pack() -> None:
    assert pipe_needs_cpu_pack("yuv420p")
    assert pipe_needs_cpu_pack("nv12")
    assert not pipe_needs_cpu_pack("rgba")


def test_pipe_frame_byte_size() -> None:
    assert pipe_frame_byte_size(1920, 1080, "rgba") == 1920 * 1080 * 4
    assert pipe_frame_byte_size(1920, 1080, "nv12") == (1920 * 1080 * 3) // 2
    assert pipe_frame_byte_size(1920, 1080, "yuv420p") == (1920 * 1080 * 3) // 2


def test_rgba_bytes_to_nv12_size() -> None:
    w, h = 1280, 720
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = 127
    raw = rgba.tobytes()
    nv12 = rgba_bytes_to_nv12(raw, w, h)
    assert len(nv12) == (w * h * 3) // 2


def test_rgba_bytes_to_yuv420p_size_and_range() -> None:
    w, h = 64, 64
    for rgb, y_tv, y_pc in (((0, 0, 0), 16, 0), ((255, 255, 255), 235, 255)):
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = rgb[0]
        rgba[..., 1] = rgb[1]
        rgba[..., 2] = rgb[2]
        rgba[..., 3] = 255
        y0 = rgba_bytes_to_yuv420p(rgba.tobytes(), w, h)[0]
        expected = y_tv if nv12_color_range() == "tv" else y_pc
        assert abs(int(y0) - expected) <= 1
    assert len(rgba_bytes_to_yuv420p(rgba.tobytes(), w, h)) == (w * h * 3) // 2


def test_rgba_bytes_to_nv12_black_white_range() -> None:
    """OpenCV path is limited/TV range; numpy fallback is full/PC range."""
    w, h = 64, 64
    for rgb, y_tv, y_pc in (((0, 0, 0), 16, 0), ((255, 255, 255), 235, 255)):
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = rgb[0]
        rgba[..., 1] = rgb[1]
        rgba[..., 2] = rgb[2]
        rgba[..., 3] = 255
        y0 = rgba_bytes_to_nv12(rgba.tobytes(), w, h)[0]
        expected = y_tv if nv12_color_range() == "tv" else y_pc
        assert abs(int(y0) - expected) <= 1


def test_flip_rgba_bytes_vertical_matches_preview_png() -> None:
    h, w = 2, 2
    gl = np.zeros((h, w, 4), dtype=np.uint8)
    gl[0, 0, 0] = 255  # OpenGL bottom row (readback row 0)
    gl[1, 0, 0] = 128  # OpenGL top row (readback row 1)
    flipped = flip_rgba_bytes_vertical(gl.tobytes(), w, h)
    out = np.frombuffer(flipped, dtype=np.uint8).reshape(h, w, 4)
    assert out[0, 0, 0] == 128
    assert out[1, 0, 0] == 255


def test_prepare_pipe_payload_passthrough_rgba() -> None:
    raw = b"\x01" * 16
    assert prepare_pipe_payload(raw, 2, 2, "rgba") == raw


def test_prepare_pipe_payload_does_not_flip_rgba() -> None:
    """Y-flip runs in the GPU readback blit pass, not in Python."""
    h, w = 2, 2
    gl = np.zeros((h, w, 4), dtype=np.uint8)
    gl[0, 0, 0] = 255
    gl[1, 0, 0] = 128
    payload = prepare_pipe_payload(gl.tobytes(), w, h, "rgba")
    out = np.frombuffer(payload, dtype=np.uint8).reshape(h, w, 4)
    assert out[0, 0, 0] == 255
    assert out[1, 0, 0] == 128


def test_prepare_pipe_payload_yuv420p() -> None:
    w, h = 4, 4
    rgba = np.arange(w * h * 4, dtype=np.uint8).reshape(h, w, 4)
    payload = prepare_pipe_payload(rgba.tobytes(), w, h, "yuv420p")
    assert len(payload) == (w * h * 3) // 2
    assert isinstance(payload, (bytes, np.ndarray))


def test_prepare_pipe_payload_nv12() -> None:
    w, h = 4, 4
    rgba = np.arange(w * h * 4, dtype=np.uint8).reshape(h, w, 4)
    payload = prepare_pipe_payload(rgba.tobytes(), w, h, "nv12")
    assert len(payload) == (w * h * 3) // 2
    # OpenCV path returns ndarray (buffer-protocol); numpy fallback returns bytes.
    assert isinstance(payload, (bytes, np.ndarray))


def test_pipe_frame_packer_reuses_dst_and_matches_prepare() -> None:
    w, h = 64, 48
    rgba = np.random.randint(0, 255, (h, w, 4), dtype=np.uint8)
    raw = rgba.tobytes()
    packer = PipeFramePacker(w, h, "yuv420p")
    a = np.asarray(packer(raw))
    b = np.asarray(prepare_pipe_payload(raw, w, h, "yuv420p"))
    assert a.shape == b.shape
    assert np.array_equal(a, b)
    # Second call must not corrupt prior semantics (same input → same output).
    c = np.asarray(packer(raw))
    assert np.array_equal(a, c)
