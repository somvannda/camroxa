"""Unit tests for GPU spectrum FFT texture packing (REQ-2.3 slice 1)."""

from __future__ import annotations

import numpy as np
import pytest

from visualizer._spectrum_fast import _BINS
from visualizer.spectrum_gpu import (
    SPECIAL_BAR_STYLES_GPU_READY,
    SPECIAL_BAR_STYLES_SLICE2,
    WAVEFORM_SPECTRUM_STYLES,
    gpu_bar_half_width_scale,
    gpu_bar_style_mode,
    gpu_spectrum_enabled,
    is_gpu_bar_style_slice1,
    is_waveform_spectrum_style,
    pack_color_rgba_texture,
    pack_fft_r32_texture,
    quantize_fft_for_gpu_bar_style,
    unpack_fft_r32_texture,
)


def test_pack_fft_r32_texture_round_trip() -> None:
    src = np.linspace(0.01, 1.0, _BINS, dtype=np.float32)
    blob = pack_fft_r32_texture(src)
    assert len(blob) == _BINS * 4
    out = unpack_fft_r32_texture(blob)
    np.testing.assert_allclose(out, src, rtol=0.0, atol=1e-6)


def test_pack_fft_r32_texture_zero_pads_short_input() -> None:
    src = np.array([0.5, 0.25], dtype=np.float32)
    out = unpack_fft_r32_texture(pack_fft_r32_texture(src))
    assert out.shape[0] == _BINS
    np.testing.assert_allclose(out[:2], src)
    np.testing.assert_allclose(out[2:], 0.0)


def test_pack_fft_r32_texture_truncates_long_input() -> None:
    src = np.arange(128, dtype=np.float32) * 0.01
    out = unpack_fft_r32_texture(pack_fft_r32_texture(src))
    np.testing.assert_allclose(out, src[:_BINS])


def test_pack_color_rgba_texture_layout() -> None:
    colors = np.array(
        [
            [1.0, 0.0, 0.0, 0.9],
            [0.0, 1.0, 0.0, 0.8],
        ],
        dtype=np.float32,
    )
    blob = pack_color_rgba_texture(colors, count=4)
    assert len(blob) == 4 * 4 * 4
    arr = np.frombuffer(blob, dtype=np.float32).reshape(4, 4)
    np.testing.assert_allclose(arr[:2], colors)
    np.testing.assert_allclose(arr[2:], 0.0)


def test_style_classification_slice1() -> None:
    assert is_waveform_spectrum_style("aurora-ribbon")
    assert is_waveform_spectrum_style("magma-ridge")
    assert not is_waveform_spectrum_style("orbit-spikes")

    assert is_gpu_bar_style_slice1("orbit-spikes")
    assert is_gpu_bar_style_slice1("classic-vertical")
    assert not is_gpu_bar_style_slice1("pulse-beads")
    assert not is_gpu_bar_style_slice1("dot-matrix")
    assert not is_gpu_bar_style_slice1("aurora-ribbon")

    for style in SPECIAL_BAR_STYLES_GPU_READY:
        assert is_gpu_bar_style_slice1(style)
    for style in SPECIAL_BAR_STYLES_SLICE2 - SPECIAL_BAR_STYLES_GPU_READY:
        assert not is_gpu_bar_style_slice1(style)
    for style in WAVEFORM_SPECTRUM_STYLES:
        assert not is_gpu_bar_style_slice1(style)


def test_gpu_ready_slice2_half_width_and_quantize() -> None:
    assert gpu_bar_half_width_scale("thin-lines") == pytest.approx(0.55)
    assert gpu_bar_half_width_scale("signal-needles") == pytest.approx(0.55)
    assert gpu_bar_half_width_scale("ignition-flare") == pytest.approx(1.2)
    assert gpu_bar_half_width_scale("orbit-spikes") == pytest.approx(1.0)

    assert gpu_bar_style_mode("orbit-spikes") == 0
    assert gpu_bar_style_mode("mirror-blades") == 1
    assert gpu_bar_style_mode("symmetrical-bars") == 1
    assert gpu_bar_style_mode("drift-capsules") == 2
    assert gpu_bar_style_mode("floating-blocks") == 2

    fft = np.array([0.5, 1.0, 0.25], dtype=np.float32)
    plain = quantize_fft_for_gpu_bar_style("orbit-spikes", fft, thickness=30.0, sf=1.0)
    np.testing.assert_allclose(plain, fft)
    stepped = quantize_fft_for_gpu_bar_style("grid-steps", fft, thickness=30.0, sf=1.0)
    assert stepped.shape == fft.shape
    # Quantized heights should be multiples of the 20px step when scaled back.
    h_q = stepped * 30.0
    np.testing.assert_allclose(h_q, np.round(h_q / 20.0) * 20.0, atol=1e-4)


def test_pack_color_rgba_texture_non_default_count() -> None:
    colors = np.array([[1.0, 0.0, 0.0, 1.0]], dtype=np.float32)
    blob = pack_color_rgba_texture(colors, count=16)
    assert len(blob) == 16 * 4 * 4
    arr = np.frombuffer(blob, dtype=np.float32).reshape(16, 4)
    np.testing.assert_allclose(arr[0], colors[0])
    np.testing.assert_allclose(arr[1:], 0.0)


def test_register_layer_accepts_bar_count_below_bins() -> None:
    try:
        import glfw
        import moderngl
    except ImportError:
        pytest.skip("glfw/moderngl not installed")
    if not glfw.init():
        pytest.skip("GLFW init failed")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    window = glfw.create_window(64, 64, "spectrum_gpu_test", None, None)
    if window is None:
        glfw.terminate()
        pytest.skip("Could not create GLFW window")
    try:
        glfw.make_context_current(window)
        ctx = moderngl.create_context()
        from visualizer._spectrum_fast import generate_points_linear
        from visualizer.spectrum_gpu import SpectrumGpuRenderer

        bar_count = 16
        px, py, dx, dy = generate_points_linear(bar_count, 800.0, "normal")
        colors = np.tile(np.array([[0.2, 0.4, 0.8, 1.0]], dtype=np.float32), (bar_count, 1))
        renderer = SpectrumGpuRenderer(ctx)
        assert renderer.register_layer(
            0,
            px=px,
            py=py,
            dx=dx,
            dy=dy,
            pass_specs=[{"thickness": 30.0, "bar_half_width": 2.0, "alpha": 1.0}],
            pass_colors=[colors],
        )
        layer = renderer._layers[0]
        assert layer.bar_count == bar_count
        assert layer.passes[0].color_tex.size == (bar_count, 1)
        fft = np.linspace(0.1, 1.0, bar_count, dtype=np.float32)
        renderer.draw_pass(0, 0, fft, cx=320.0, cy=180.0, w=640, h=360)
        renderer.release()
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


def test_gpu_spectrum_enabled_default_off(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_GPU_SPECTRUM", raising=False)
    assert gpu_spectrum_enabled() is False


def test_gpu_spectrum_enabled_truthy_values(monkeypatch) -> None:
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CAMXORA_GPU_SPECTRUM", value)
        assert gpu_spectrum_enabled() is True
