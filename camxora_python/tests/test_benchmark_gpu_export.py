"""Unit tests for GPU export benchmark parsing (no GPU required)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_benchmark_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_gpu_export.py"
    spec = importlib.util.spec_from_file_location("benchmark_gpu_export", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["benchmark_gpu_export"] = module
    spec.loader.exec_module(module)
    return module


bench = _load_benchmark_module()


def test_parse_mg_event_line_valid_json() -> None:
    line = 'MG_EVENT {"status":"running","message":"Rendering 1/72","frame":1,"totalFrames":72}'
    event = bench.parse_mg_event_line(line)
    assert event is not None
    assert event["frame"] == 1
    assert event["totalFrames"] == 72


def test_parse_mg_event_line_ignores_non_events() -> None:
    assert bench.parse_mg_event_line("INFO starting") is None
    assert bench.parse_mg_event_line("") is None


def test_build_benchmark_metrics_from_mock_events() -> None:
    timed_events = [
        (0.0, {"status": "running", "message": "Initializing GPU renderer..."}),
        (
            4.5,
            {
                "status": "running",
                "message": "Encoder started (NVENC, YUV420P pipe)",
                "videoCodec": "h264_nvenc",
                "pipePixFmt": "yuv420p",
            },
        ),
        (
            12.0,
            {
                "status": "running",
                "message": "Rendering 1/72",
                "frame": 1,
                "totalFrames": 72,
                "videoCodec": "h264_nvenc",
            },
        ),
        (
            90.0,
            {
                "status": "done",
                "message": "Exported MP4",
                "outputPath": "C:/tmp/out.mp4",
            },
        ),
    ]

    metrics = bench.build_benchmark_metrics(
        timed_events=timed_events,
        video_duration_sec=180.0,
        wall_clock_sec=90.0,
        exit_code=0,
        backend="subprocess",
    )

    assert metrics.init_to_first_frame_sec == 12.0
    assert metrics.wall_clock_sec == 90.0
    assert metrics.video_duration_sec == 180.0
    assert metrics.realtime_factor == 2.0
    assert metrics.video_codec == "h264_nvenc"
    assert metrics.video_codec_label == "NVENC"
    assert metrics.pipe_pix_fmt == "yuv420p"
    assert metrics.total_frames == 72
    assert metrics.output_path.endswith("out.mp4")
    assert metrics.exit_code == 0


def test_is_first_frame_event_message_fallback() -> None:
    assert bench.is_first_frame_event({"message": "Rendering 1/100"}) is True
    assert bench.is_first_frame_event({"message": "Rendering 2/100", "frame": 2}) is False


def test_detect_gpu_info_handles_missing_nvidia_smi(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(bench.subprocess, "run", _raise)
    info = bench.detect_gpu_info()
    assert info.detected is False
    assert "nvidia-smi" in info.error


def test_collect_env_flags_reads_traced_vars(monkeypatch) -> None:
    monkeypatch.setenv("CAMXORA_GPU_SPECTRUM", "1")
    monkeypatch.setenv("CAMXORA_ENCODE_METRICS", "1")
    flags = bench.collect_env_flags()
    assert flags["CAMXORA_GPU_SPECTRUM"] == "1"
    assert flags["CAMXORA_ENCODE_METRICS"] == "1"


def test_extract_diagnostic_metrics_from_events() -> None:
    events = [
        {"status": "running", "exportFrameProfile": {"audioStepAvgMs": 1.2, "glRenderAvgMs": 30.0}},
        {
            "status": "running",
            "encodePipeMetrics": {"submitBlockP95Ms": 0.5, "stdinBlockP95Ms": 2.0},
        },
    ]
    pipe, profile = bench.extract_diagnostic_metrics(events)
    assert pipe == {"submitBlockP95Ms": 0.5, "stdinBlockP95Ms": 2.0}
    assert profile == {"audioStepAvgMs": 1.2, "glRenderAvgMs": 30.0}
