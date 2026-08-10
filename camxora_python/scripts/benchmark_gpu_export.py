#!/usr/bin/env python3
"""Local GPU export benchmark — docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md §3.

Runs a Standard-tier GPU export (1080p, 24 fps, speed ``fast``) against the
``.dbg/export_e2e_test`` fixture when present, parses ``MG_EVENT`` stdout lines,
and writes a human-readable summary plus optional JSON under ``.dbg/benchmark_results/``.

Reference GPU in the requirements doc is GTX 1050 Ti; RTX 3060 (or any NVIDIA
GPU with NVENC) is an acceptable substitute — note your GPU model in results.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Ensure camxora_python package root is importable when invoked as a script.
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from features.video.lib.render_scene_request import parse_render_resolution  # noqa: E402
from features.video.services.export_job import ExportJob, ExportSettings  # noqa: E402
from shared.lib.export_codec import export_video_codec_label  # noqa: E402
from shared.lib.export_tiers import resolve_export_tier_settings  # noqa: E402
from shared.lib.ffmpeg_paths import resolve_ffmpeg_path  # noqa: E402
from visualizer_video.audio import probe_audio_duration_sec  # noqa: E402

BENCHMARK_CONTRACT_VERSION = "1.0"
REFERENCE_GPU = "NVIDIA GTX 1050 Ti"
SUBSTITUTE_GPU_NOTE = "RTX 3060 (or similar NVENC GPU) is an acceptable substitute per section 3."

TRACED_ENV_FLAGS = (
    "CAMXORA_GPU_SPECTRUM",
    "CAMXORA_ENCODE_METRICS",
    "CAMXORA_PIPELINED_ENCODE",
    "CAMXORA_ENCODE_QUEUE",
    "CAMXORA_EXPORT_PIPE",
    "CAMXORA_USE_VISUALIZER_DAEMON",
    "CAMXORA_INPROCESS_EXPORT",
    "CAMXORA_EXPORT_PROFILE",
)

ENV_FLAG_HELP = (
    "Environment flags (set before running; recorded in JSON settings.envFlags):\n"
    "  CAMXORA_GPU_SPECTRUM=1       GPU spectrum path (default off)\n"
    "  CAMXORA_ENCODE_METRICS=1     Pipelined encode pipe block stats at end\n"
    "  CAMXORA_PIPELINED_ENCODE=1   Bounded queue writer (default on)\n"
    "  CAMXORA_ENCODE_QUEUE=6       Encode queue depth (2–8, default 6)\n"
    "  CAMXORA_EXPORT_PIPE=yuv420p  Override pipe pix_fmt (rgba|nv12|yuv420p)\n"
    "  CAMXORA_USE_VISUALIZER_DAEMON Warm daemon backend (--warm-daemon sets 1)\n"
    "  CAMXORA_EXPORT_PROFILE=1     Rolling per-frame phase timings in MG_EVENT\n"
    "  CAMXORA_INPROCESS_EXPORT=1   Warm preview GL export (UI only; see --in-process)\n"
)

INPROCESS_UI_NOTE = (
    "In-process export requires a warm preview OpenGL context (QApplication + matching "
    "preview session). The CLI benchmark always uses ExportJob subprocess/daemon; "
    "set CAMXORA_INPROCESS_EXPORT=1 in the desktop app environment to test there."
)

DEFAULT_FIXTURE_DIR = _PACKAGE_ROOT / ".dbg" / "export_e2e_test" / "assets"
DEFAULT_RESULTS_DIR = _PACKAGE_ROOT / ".dbg" / "benchmark_results"


@dataclass(frozen=True)
class FixturePaths:
    mp3_path: Path
    template_path: Path
    background_path: Path
    logo_path: str
    source: str


@dataclass(frozen=True)
class GpuInfo:
    detected: bool
    name: str = ""
    driver_version: str = ""
    memory_mib: str = ""
    raw_line: str = ""
    error: str = ""

    def summary(self) -> str:
        if not self.detected:
            detail = self.error or "not detected (nvidia-smi unavailable)"
            return f"{detail}. {SUBSTITUTE_GPU_NOTE}"
        parts = [self.name]
        if self.driver_version:
            parts.append(f"driver {self.driver_version}")
        if self.memory_mib:
            parts.append(f"{self.memory_mib} MiB VRAM")
        return f"{', '.join(parts)} [{SUBSTITUTE_GPU_NOTE}]"


@dataclass
class BenchmarkMetrics:
    init_to_first_frame_sec: float | None = None
    wall_clock_sec: float = 0.0
    video_duration_sec: float = 0.0
    realtime_factor: float = 0.0
    video_codec: str = ""
    video_codec_label: str = ""
    pipe_pix_fmt: str = ""
    total_frames: int | None = None
    output_path: str = ""
    exit_code: int = 1
    backend: str = "subprocess"
    events: list[dict[str, Any]] = field(default_factory=list)
    encode_pipe_metrics: dict[str, Any] | None = None
    export_frame_profile: dict[str, Any] | None = None


def collect_env_flags() -> dict[str, str]:
    """Snapshot traced export env vars for JSON results."""
    flags: dict[str, str] = {}
    for name in TRACED_ENV_FLAGS:
        raw = os.environ.get(name)
        if raw is not None:
            flags[name] = str(raw)
    return flags


def extract_diagnostic_metrics(events: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return latest encodePipeMetrics and exportFrameProfile payloads from MG_EVENT list."""
    encode_pipe_metrics: dict[str, Any] | None = None
    export_frame_profile: dict[str, Any] | None = None
    for event in events:
        pipe = event.get("encodePipeMetrics")
        if isinstance(pipe, dict):
            encode_pipe_metrics = dict(pipe)
        profile = event.get("exportFrameProfile")
        if isinstance(profile, dict):
            export_frame_profile = dict(profile)
    return encode_pipe_metrics, export_frame_profile


def parse_mg_event_line(line: str) -> dict[str, Any] | None:
    """Parse a single stdout line into an MG_EVENT payload dict, if present."""
    stripped = str(line or "").strip()
    if not stripped.startswith("MG_EVENT "):
        return None
    payload_raw = stripped[len("MG_EVENT ") :].strip()
    if not payload_raw:
        return None
    try:
        parsed = json.loads(payload_raw)
    except json.JSONDecodeError:
        return {"status": "log", "message": payload_raw}
    return parsed if isinstance(parsed, dict) else None


def is_first_frame_event(event: dict[str, Any]) -> bool:
    frame = event.get("frame")
    if isinstance(frame, int) and frame == 1:
        return True
    message = str(event.get("message") or "")
    return message.startswith("Rendering 1/")


def build_benchmark_metrics(
    *,
    timed_events: list[tuple[float, dict[str, Any]]],
    video_duration_sec: float,
    wall_clock_sec: float,
    exit_code: int,
    backend: str,
) -> BenchmarkMetrics:
    """Derive benchmark metrics from collected MG_EVENT payloads and wall clock."""
    metrics = BenchmarkMetrics(
        wall_clock_sec=float(wall_clock_sec),
        video_duration_sec=float(video_duration_sec),
        exit_code=int(exit_code),
        backend=str(backend or "subprocess"),
        events=[evt for _, evt in timed_events],
    )

    if metrics.wall_clock_sec > 0:
        metrics.realtime_factor = metrics.video_duration_sec / metrics.wall_clock_sec

    for offset_sec, event in timed_events:
        if metrics.init_to_first_frame_sec is None and is_first_frame_event(event):
            metrics.init_to_first_frame_sec = float(offset_sec)

        codec = str(event.get("videoCodec") or "").strip()
        if codec:
            metrics.video_codec = codec
            metrics.video_codec_label = export_video_codec_label(codec)

        pipe = str(event.get("pipePixFmt") or "").strip()
        if pipe:
            metrics.pipe_pix_fmt = pipe

        total_frames = event.get("totalFrames")
        if isinstance(total_frames, int):
            metrics.total_frames = total_frames

        if str(event.get("status") or "").strip().lower() == "done":
            output_path = str(event.get("outputPath") or "").strip()
            if output_path:
                metrics.output_path = output_path

    metrics.encode_pipe_metrics, metrics.export_frame_profile = extract_diagnostic_metrics(metrics.events)

    return metrics


def detect_gpu_info() -> GpuInfo:
    """Detect NVIDIA GPU via nvidia-smi when available."""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        return GpuInfo(detected=False, error="nvidia-smi not found on PATH")
    except subprocess.TimeoutExpired:
        return GpuInfo(detected=False, error="nvidia-smi timed out")
    except OSError as exc:
        return GpuInfo(detected=False, error=str(exc))

    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        return GpuInfo(detected=False, error=err or f"nvidia-smi exit {completed.returncode}")

    raw = (completed.stdout or "").strip().splitlines()
    if not raw:
        return GpuInfo(detected=False, error="nvidia-smi returned no GPU rows")

    first = raw[0]
    parts = [part.strip() for part in first.split(",")]
    name = parts[0] if parts else first
    driver = parts[1] if len(parts) > 1 else ""
    memory = parts[2] if len(parts) > 2 else ""
    return GpuInfo(
        detected=True,
        name=name,
        driver_version=driver,
        memory_mib=memory,
        raw_line=first,
    )


def _load_template_dict(template_path: Path) -> dict[str, Any]:
    raw = json.loads(template_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def generate_test_tone(path: Path, *, duration_sec: float = 180.0, sample_rate: int = 44100) -> Path:
    """Write a mono sine test tone (default 3 min @ 44.1 kHz) for benchmark fixtures."""
    import numpy as np
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    samples = int(max(1.0, float(duration_sec)) * sample_rate)
    t = np.linspace(0.0, duration_sec, samples, endpoint=False, dtype=np.float64)
    tone = (0.25 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
    sf.write(str(path), tone, sample_rate)
    return path


def resolve_fixture_paths(
    *,
    package_root: Path,
    mp3: str | None = None,
    template: str | None = None,
    background: str | None = None,
    generate_tone_sec: float | None = None,
) -> FixturePaths:
    """Resolve benchmark fixture paths, preferring ``.dbg/export_e2e_test`` assets."""
    fixture_dir = package_root / ".dbg" / "export_e2e_test" / "assets"

    if mp3:
        mp3_path = Path(mp3).expanduser().resolve()
        source = "cli"
    elif (fixture_dir / "test_export.mp3").is_file():
        mp3_path = fixture_dir / "test_export.mp3"
        source = "export_e2e_test"
    elif generate_tone_sec is not None:
        tone_path = package_root / ".dbg" / "benchmark_results" / "generated_tone.wav"
        mp3_path = generate_test_tone(tone_path, duration_sec=float(generate_tone_sec))
        source = "generated_tone"
    else:
        tone_path = package_root / ".dbg" / "benchmark_results" / "generated_tone.wav"
        mp3_path = generate_test_tone(tone_path, duration_sec=30.0)
        source = "generated_tone_default"

    if template:
        template_path = Path(template).expanduser().resolve()
    elif (fixture_dir / "template.json").is_file():
        template_path = fixture_dir / "template.json"
    else:
        raise FileNotFoundError(
            "No template.json found. Pass --template or add .dbg/export_e2e_test/assets/template.json"
        )

    template_dict = _load_template_dict(template_path)
    if background:
        background_path = Path(background).expanduser().resolve()
    else:
        bg_from_template = str(template_dict.get("background") or "").strip()
        if bg_from_template and Path(bg_from_template).is_file():
            background_path = Path(bg_from_template)
        elif (fixture_dir / "bg.png").is_file():
            background_path = fixture_dir / "bg.png"
        else:
            raise FileNotFoundError(
                "Background image missing. Pass --background or set template.background."
            )

    logo_settings = template_dict.get("logoSettings")
    logo_enabled = bool(logo_settings.get("enabled", True)) if isinstance(logo_settings, dict) else True
    logo_path = ""

    return FixturePaths(
        mp3_path=mp3_path,
        template_path=template_path,
        background_path=background_path,
        logo_path=logo_path,
        source=source,
    )


def format_human_summary(
    *,
    metrics: BenchmarkMetrics,
    fixture: FixturePaths,
    tier_label: str,
    width: int,
    height: int,
    fps: int,
    speed_mode: str,
    gpu: GpuInfo,
    results_json: Path | None,
    reference_gpu: str = REFERENCE_GPU,
) -> str:
    init_text = (
        f"{metrics.init_to_first_frame_sec:.2f} s"
        if metrics.init_to_first_frame_sec is not None
        else "n/a"
    )
    codec_text = metrics.video_codec_label or metrics.video_codec or "unknown"
    pipe_text = metrics.pipe_pix_fmt.upper() if metrics.pipe_pix_fmt else "unknown"

    lines = [
        "=== Camxora GPU Export Benchmark ===",
        f"Contract: docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md section 3 (ref GPU: {reference_gpu})",
        f"Fixture: {fixture.mp3_path} ({metrics.video_duration_sec:.1f} s, source={fixture.source})",
        f"Settings: {tier_label} - {width}x{height} @ {fps} fps, speed={speed_mode}, backend={metrics.backend}",
        f"GPU: {gpu.summary()}",
        f"Codec: {codec_text} ({metrics.video_codec or 'n/a'}) | Pipe: {pipe_text}",
        "",
        f"Init to first frame: {init_text}",
        f"Wall clock total:    {metrics.wall_clock_sec:.2f} s",
        f"Video duration:      {metrics.video_duration_sec:.2f} s",
        f"Realtime factor:     {metrics.realtime_factor:.2f}x (duration / wall)",
        "",
        f"Exit code: {metrics.exit_code}",
    ]
    if metrics.output_path:
        lines.append(f"Output: {metrics.output_path}")
    if metrics.encode_pipe_metrics:
        stats = metrics.encode_pipe_metrics
        lines.extend(
            [
                "",
                "Encode pipe metrics:",
                f"  submit block p95: {stats.get('submitBlockP95Ms')} ms",
                f"  stdin block p95:  {stats.get('stdinBlockP95Ms')} ms",
                f"  pack avg:         {stats.get('packAvgMs')} ms",
                f"  queue size:       {stats.get('queueSize')}",
                f"  frames submitted:   {stats.get('framesSubmitted')}",
            ]
        )
    if metrics.export_frame_profile:
        prof = metrics.export_frame_profile
        lines.extend(
            [
                "",
                "Export frame profile (last rolling sample):",
                f"  audio step:   {prof.get('audioStepAvgMs')} ms",
                f"  GL render:    {prof.get('glRenderAvgMs')} ms",
                f"  readback:     {prof.get('readbackAvgMs')} ms",
                f"  encode write: {prof.get('encodeWriteAvgMs')} ms",
            ]
        )
    if results_json is not None:
        lines.append(f"JSON: {results_json}")
    return "\n".join(lines)


def run_export_benchmark(
    *,
    fixture: FixturePaths,
    output_dir: Path,
    ffmpeg_path: str,
    width: int,
    height: int,
    fps: int,
    speed_mode: str,
    use_daemon: bool,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[BenchmarkMetrics, list[tuple[float, dict[str, Any]]]]:
    """Run one GPU export and collect MG_EVENT timing data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    template = _load_template_dict(fixture.template_path)
    stem = fixture.mp3_path.stem or "benchmark"
    output_path = output_dir / f"{stem}.mp4"

    settings = ExportSettings(
        ffmpeg_path=ffmpeg_path,
        output_dir=str(output_dir),
        output_path=str(output_path),
        fps=int(fps),
        width=int(width),
        height=int(height),
        speed_mode=str(speed_mode),
    )

    timed_events: list[tuple[float, dict[str, Any]]] = []
    start = time.monotonic()

    def _handle_event(event: dict[str, Any]) -> None:
        offset = time.monotonic() - start
        timed_events.append((offset, dict(event)))
        if on_event is not None:
            on_event(event)

    prior_daemon = os.environ.get("CAMXORA_USE_VISUALIZER_DAEMON")
    backend = "daemon" if use_daemon else "subprocess"
    os.environ["CAMXORA_USE_VISUALIZER_DAEMON"] = "1" if use_daemon else "0"
    try:
        job = ExportJob(
            mp3_path=str(fixture.mp3_path),
            template=template,
            background_path=str(fixture.background_path),
            logo_path=fixture.logo_path,
            settings=settings,
            on_event=_handle_event,
        )
        exit_code = job.run_blocking()
    finally:
        if prior_daemon is None:
            os.environ.pop("CAMXORA_USE_VISUALIZER_DAEMON", None)
        else:
            os.environ["CAMXORA_USE_VISUALIZER_DAEMON"] = prior_daemon

    wall_clock_sec = time.monotonic() - start
    video_duration_sec = probe_audio_duration_sec(str(fixture.mp3_path))
    metrics = build_benchmark_metrics(
        timed_events=timed_events,
        video_duration_sec=video_duration_sec,
        wall_clock_sec=wall_clock_sec,
        exit_code=exit_code,
        backend=backend,
    )
    return metrics, timed_events


def write_results_json(
    path: Path,
    *,
    metrics: BenchmarkMetrics,
    fixture: FixturePaths,
    gpu: GpuInfo,
    tier: str,
    width: int,
    height: int,
    fps: int,
    speed_mode: str,
    env_flags: dict[str, str] | None = None,
) -> None:
    env_flags = env_flags if env_flags is not None else collect_env_flags()
    payload = {
        "benchmarkContractVersion": BENCHMARK_CONTRACT_VERSION,
        "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "referenceGpu": REFERENCE_GPU,
        "substituteGpuNote": SUBSTITUTE_GPU_NOTE,
        "fixture": {
            "mp3": str(fixture.mp3_path),
            "template": str(fixture.template_path),
            "background": str(fixture.background_path),
            "source": fixture.source,
        },
        "settings": {
            "tier": tier,
            "width": width,
            "height": height,
            "fps": fps,
            "speedMode": speed_mode,
            "backend": metrics.backend,
            "envFlags": env_flags,
        },
        "gpu": asdict(gpu),
        "metrics": {
            "initToFirstFrameSec": metrics.init_to_first_frame_sec,
            "wallClockSec": metrics.wall_clock_sec,
            "videoDurationSec": metrics.video_duration_sec,
            "realtimeFactor": metrics.realtime_factor,
            "videoCodec": metrics.video_codec,
            "videoCodecLabel": metrics.video_codec_label,
            "pipePixFmt": metrics.pipe_pix_fmt,
            "totalFrames": metrics.total_frames,
            "outputPath": metrics.output_path,
            "exitCode": metrics.exit_code,
        },
        "diagnostics": {
            "encodePipeMetrics": metrics.encode_pipe_metrics,
            "exportFrameProfile": metrics.export_frame_profile,
        },
        "events": metrics.events,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark local GPU video export (Camxora Standard tier, §3 contract).",
        epilog=ENV_FLAG_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--mp3", help="Override benchmark audio path (default: export_e2e_test fixture).")
    parser.add_argument("--template", help="Override template JSON path.")
    parser.add_argument("--background", help="Override background image path.")
    parser.add_argument(
        "--generate-tone-sec",
        type=float,
        default=None,
        help="Generate a sine test tone of N seconds when no fixture MP3 exists.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Export output directory (default: .dbg/benchmark_results/run_<timestamp>).",
    )
    parser.add_argument("--ffmpeg", default="", help="FFmpeg binary path (default: bundled or PATH).")
    parser.add_argument(
        "--warm-daemon",
        action="store_true",
        help="Route export through the warm visualizer daemon (sets CAMXORA_USE_VISUALIZER_DAEMON=1).",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help=(
            "Set CAMXORA_INPROCESS_EXPORT=1 for parity with UI testing. "
            "CLI benchmark still uses subprocess/daemon — in-process needs warm preview in desktop UI."
        ),
    )
    parser.add_argument("--json", dest="json_path", default="", help="Write JSON results to this path.")
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip writing JSON results (human summary only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve fixture/settings and print the planned run without exporting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    tier_settings = resolve_export_tier_settings({}, pipeline=False)
    width, height = parse_render_resolution(tier_settings.resolution)
    fps = int(tier_settings.fps)
    speed_mode = str(tier_settings.speed_mode)

    fixture = resolve_fixture_paths(
        package_root=_PACKAGE_ROOT,
        mp3=args.mp3,
        template=args.template,
        background=args.background,
        generate_tone_sec=args.generate_tone_sec,
    )
    gpu = detect_gpu_info()
    ffmpeg_path = resolve_ffmpeg_path(args.ffmpeg or None)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if str(args.output_dir or "").strip()
        else DEFAULT_RESULTS_DIR / f"run_{timestamp}"
    )
    json_path: Path | None = None
    if not args.no_json:
        json_path = (
            Path(args.json_path).expanduser().resolve()
            if str(args.json_path or "").strip()
            else DEFAULT_RESULTS_DIR / f"gpu_export_benchmark_{timestamp}.json"
        )

    if args.dry_run:
        print(
            format_human_summary(
                metrics=BenchmarkMetrics(
                    video_duration_sec=probe_audio_duration_sec(str(fixture.mp3_path)),
                ),
                fixture=fixture,
                tier_label=tier_settings.label,
                width=width,
                height=height,
                fps=fps,
                speed_mode=speed_mode,
                gpu=gpu,
                results_json=json_path,
            )
        )
        print("\nActive env flags:", collect_env_flags() or "(none traced)")
        print("\n(dry-run - export not started)")
        return 0

    if args.in_process:
        os.environ["CAMXORA_INPROCESS_EXPORT"] = "1"
        print(f"Note: {INPROCESS_UI_NOTE}", flush=True)

    def _progress(event: dict[str, Any]) -> None:
        status = str(event.get("status") or "").strip().lower()
        if status in {"running", "done", "failed"}:
            message = str(event.get("message") or "").strip()
            if message:
                print(message, flush=True)

    metrics, _ = run_export_benchmark(
        fixture=fixture,
        output_dir=run_output_dir,
        ffmpeg_path=ffmpeg_path,
        width=width,
        height=height,
        fps=fps,
        speed_mode=speed_mode,
        use_daemon=bool(args.warm_daemon),
        on_event=_progress,
    )

    summary = format_human_summary(
        metrics=metrics,
        fixture=fixture,
        tier_label=tier_settings.label,
        width=width,
        height=height,
        fps=fps,
        speed_mode=speed_mode,
        gpu=gpu,
        results_json=json_path,
    )
    print("\n" + summary)

    if json_path is not None:
        write_results_json(
            json_path,
            metrics=metrics,
            fixture=fixture,
            gpu=gpu,
            tier=tier_settings.tier,
            width=width,
            height=height,
            fps=fps,
            speed_mode=speed_mode,
            env_flags=collect_env_flags(),
        )

    return 0 if metrics.exit_code == 0 else int(metrics.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
