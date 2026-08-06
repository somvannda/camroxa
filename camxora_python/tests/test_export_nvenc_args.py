"""Tests for NVENC export flag construction."""

from __future__ import annotations

from visualizer.gpu_render import build_nvenc_export_args
from visualizer.readback import nv12_color_range


def test_build_nvenc_fast_uses_vbr_bitrate(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)
    args = build_nvenc_export_args(
        "fast",
        width=1920,
        height=1080,
        fps=30,
        pipe_pix_fmt="yuv420p",
        color_range="tv",
    )
    assert args[args.index("-c:v") + 1] == "h264_nvenc"
    assert args[args.index("-preset") + 1] == "p3"
    assert args[args.index("-rc") + 1] == "vbr"
    assert args[args.index("-b:v") + 1] == "5600k"  # 8 Mbps * 0.70
    assert args[args.index("-maxrate") + 1] == "8400k"
    assert args[args.index("-bufsize") + 1] == "11200k"
    assert "-cq" not in args
    assert "-tune" not in args
    assert "-zerolatency" not in args
    assert "-bf" not in args
    assert args[args.index("-color_range") + 1] == "tv"


def test_build_nvenc_ll_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("CAMXORA_NVENC_LL", "1")
    args = build_nvenc_export_args(
        "fast",
        width=1920,
        height=1080,
        fps=30,
        pipe_pix_fmt="yuv420p",
        color_range="tv",
    )
    assert args[args.index("-tune") + 1] == "ll"
    assert args[args.index("-zerolatency") + 1] == "1"
    assert args[args.index("-bf") + 1] == "0"


def test_build_nvenc_very_fast_uses_p1(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)
    args = build_nvenc_export_args(
        "very_fast",
        width=1920,
        height=1080,
        fps=30,
        pipe_pix_fmt="yuv420p",
        color_range="tv",
    )
    assert args[args.index("-preset") + 1] == "p1"
    assert args[args.index("-b:v") + 1] == "4400k"  # 8 * 0.55
    assert "-cq" not in args


def test_build_nvenc_balanced_vbr(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)
    args = build_nvenc_export_args(
        "balanced",
        width=1920,
        height=1080,
        fps=30,
        pipe_pix_fmt="yuv420p",
        color_range="tv",
    )
    assert args[args.index("-preset") + 1] == "p3"
    assert args[args.index("-b:v") + 1] == "6800k"  # 8 * 0.85
    assert "-tune" not in args
    assert args[args.index("-color_range") + 1] == "tv"


def test_build_nvenc_quality_1440p_matches_capcut_anchor(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)
    args = build_nvenc_export_args(
        "quality",
        width=2560,
        height=1440,
        fps=30,
        pipe_pix_fmt="rgba",
        color_range="pc",
    )
    assert args[args.index("-preset") + 1] == "p5"
    assert args[args.index("-b:v") + 1] == "12000k"
    assert args[args.index("-rc") + 1] == "vbr"


def test_build_nvenc_best_quality_higher_bitrate(monkeypatch) -> None:
    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)
    args = build_nvenc_export_args(
        "best_quality",
        width=2560,
        height=1440,
        fps=30,
        pipe_pix_fmt="rgba",
        color_range="pc",
    )
    assert args[args.index("-preset") + 1] == "p7"
    assert args[args.index("-b:v") + 1] == "15000k"  # 12 * 1.25


def test_nv12_color_range_matches_converter() -> None:
    assert nv12_color_range() in {"tv", "pc"}
