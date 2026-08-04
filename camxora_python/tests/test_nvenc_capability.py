"""Tests for NVENC capability probe and x264 rewrite helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from visualizer.nvenc_capability import (
    clear_nvenc_probe_cache,
    mark_nvenc_unavailable,
    nvenc_error_indicates_unavailable,
    probe_h264_nvenc,
    rewrite_nvenc_cmd_to_x264,
)


@pytest.fixture(autouse=True)
def _reset_nvenc_cache() -> None:
    clear_nvenc_probe_cache()
    yield
    clear_nvenc_probe_cache()


def test_nvenc_error_detects_driver_api_mismatch() -> None:
    err = (
        "[h264_nvenc @ 0x1] Driver does not support the required nvenc API version. "
        "Required: 13.0 Found: 12.2\n"
        "The minimum required Nvidia driver for nvenc is 570.0 or newer\n"
        "Error while opening encoder - maybe incorrect parameters\n"
    )
    assert nvenc_error_indicates_unavailable(err) is True


def test_nvenc_error_ignores_unrelated_pipe_noise() -> None:
    assert nvenc_error_indicates_unavailable("Conversion failed!") is False
    assert nvenc_error_indicates_unavailable("") is False


def test_rewrite_nvenc_cmd_to_x264_swaps_flags() -> None:
    cmd = [
        "ffmpeg",
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p3",
        "-rc",
        "constqp",
        "-cq",
        "23",
        "-color_range",
        "tv",
        "-pix_fmt",
        "yuv420p",
        "out.mp4",
    ]
    out = rewrite_nvenc_cmd_to_x264(cmd, x264_preset="superfast", x264_crf="23")
    assert out[out.index("-c:v") + 1] == "libx264"
    assert out[out.index("-preset") + 1] == "superfast"
    assert out[out.index("-crf") + 1] == "23"
    assert "-cq" not in out
    assert "-rc" not in out
    assert "h264_nvenc" not in out


def test_force_x264_skips_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_FORCE_X264", "1")
    called = {"n": 0}

    def _boom(*_a, **_k):  # pragma: no cover - must not run
        called["n"] += 1
        raise AssertionError("probe should not spawn ffmpeg")

    monkeypatch.setattr("visualizer.nvenc_capability.run_hidden", _boom)
    assert probe_h264_nvenc("ffmpeg") is False
    assert called["n"] == 0


def test_probe_caches_false_on_driver_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_FORCE_X264", raising=False)

    def _fake_run(*_a, **_k):
        return SimpleNamespace(
            returncode=1,
            stderr=(
                "Driver does not support the required nvenc API version. "
                "Required: 13.0 Found: 12.2"
            ),
        )

    monkeypatch.setattr("visualizer.nvenc_capability.run_hidden", _fake_run)
    assert probe_h264_nvenc("C:/fake/ffmpeg.exe") is False
    # Cached — second call must not re-invoke run_hidden.
    monkeypatch.setattr(
        "visualizer.nvenc_capability.run_hidden",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use cache")),
    )
    assert probe_h264_nvenc("C:/fake/ffmpeg.exe") is False


def test_mark_nvenc_unavailable_blocks_later_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_FORCE_X264", raising=False)
    monkeypatch.setattr(
        "visualizer.nvenc_capability.run_hidden",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stderr=""),
    )
    assert probe_h264_nvenc("ffmpeg") is True
    mark_nvenc_unavailable()
    assert probe_h264_nvenc("ffmpeg") is False
