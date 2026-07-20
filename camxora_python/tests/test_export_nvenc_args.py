"""Tests for NVENC export flag construction."""



from __future__ import annotations



from visualizer.gpu_render import build_nvenc_export_args

from visualizer.readback import nv12_color_range





def test_build_nvenc_fast_matches_baseline_cq(monkeypatch) -> None:

    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)

    args = build_nvenc_export_args("fast", pipe_pix_fmt="yuv420p", color_range="tv")

    assert args[args.index("-c:v") + 1] == "h264_nvenc"

    assert args[args.index("-preset") + 1] == "p3"

    assert args[args.index("-cq") + 1] == "23"

    assert "-tune" not in args

    assert "-zerolatency" not in args

    assert "-bf" not in args

    assert args[args.index("-color_range") + 1] == "tv"





def test_build_nvenc_ll_opt_in(monkeypatch) -> None:

    monkeypatch.setenv("CAMXORA_NVENC_LL", "1")

    args = build_nvenc_export_args("fast", pipe_pix_fmt="yuv420p", color_range="tv")

    assert args[args.index("-tune") + 1] == "ll"

    assert args[args.index("-zerolatency") + 1] == "1"

    assert args[args.index("-bf") + 1] == "0"





def test_build_nvenc_very_fast_uses_p1(monkeypatch) -> None:

    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)

    args = build_nvenc_export_args("very_fast", pipe_pix_fmt="yuv420p", color_range="tv")

    assert args[args.index("-preset") + 1] == "p1"

    assert args[args.index("-cq") + 1] == "27"

    assert "-tune" not in args





def test_build_nvenc_balanced_matches_baseline_cq(monkeypatch) -> None:

    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)

    args = build_nvenc_export_args("balanced", pipe_pix_fmt="yuv420p", color_range="tv")

    assert args[args.index("-preset") + 1] == "p3"

    assert args[args.index("-cq") + 1] == "23"

    assert "-tune" not in args

    assert "-zerolatency" not in args

    assert "-bf" not in args

    assert args[args.index("-color_range") + 1] == "tv"





def test_build_nvenc_quality_is_higher_cq(monkeypatch) -> None:

    monkeypatch.delenv("CAMXORA_NVENC_LL", raising=False)

    args = build_nvenc_export_args("quality", pipe_pix_fmt="rgba", color_range="pc")

    assert args[args.index("-preset") + 1] == "p5"

    assert args[args.index("-cq") + 1] == "19"





def test_nv12_color_range_matches_converter() -> None:

    assert nv12_color_range() in {"tv", "pc"}


