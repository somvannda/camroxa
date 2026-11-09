"""Manual QA: verify the export pipe tail on real hardware (GPU required).

Checks the four guarantees behind the "-shortest / [Errno 22]" fix:

1. the render exits 0 and the MP4 exists
2. the MP4 keeps the rendered length instead of being cut back to the audio tail
3. no ``ffmpeg_error_*.log`` is left in the output folder (deleted on success)
4. no ``ffmpeg.exe`` survives the export (no orphan holding the file)

Typical use on a GPU machine::

    python scripts/verify_export_tail.py --generate-fixtures
    python scripts/verify_export_tail.py --mp3 out/verify-tail/tone.mp3 \
        --background out/verify-tail/background.png --template my_template.json

Validate an existing export without rendering::

    python scripts/verify_export_tail.py --check-only out/track.mp4 --mp3 track.mp3
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.lib.subprocess_utils import popen_hidden, run_hidden  # noqa: E402

# Exports are cut at the audio tail when -shortest sneaks back in; a frame or two
# of container rounding is fine, a real truncation is not.
DURATION_TOLERANCE_SEC = 0.5


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(CheckResult(name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.results)

    def render(self) -> str:
        lines = ["", "Export tail verification"]
        lines.append("-" * 60)
        for item in self.results:
            mark = "PASS" if item.ok else "FAIL"
            line = f"[{mark}] {item.name}"
            if item.detail:
                line = f"{line}: {item.detail}"
            lines.append(line)
        lines.append("-" * 60)
        lines.append("RESULT: " + ("PASS" if self.ok else "FAIL"))
        return "\n".join(lines)


def _tool(name: str) -> str:
    try:
        from shared.lib.ffmpeg_paths import resolve_ffmpeg_path, resolve_ffprobe_path

        resolved = resolve_ffprobe_path() if name == "ffprobe" else resolve_ffmpeg_path()
        if resolved and Path(resolved).is_file():
            return resolved
    except Exception:
        pass
    return shutil.which(name) or name


def _duration_sec(path: Path) -> float:
    completed = run_hidden(
        [
            _tool("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return max(0.0, float(str(completed.stdout or "").strip() or 0))
    except ValueError:
        return 0.0


def _ffmpeg_pids() -> set[str]:
    """PIDs of running ffmpeg processes (empty when the platform has no tasklist)."""
    if sys.platform != "win32":
        completed = run_hidden(["pgrep", "-f", "ffmpeg"], capture_output=True, text=True, check=False)
        return {line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()}
    completed = run_hidden(
        ["tasklist", "/FI", "IMAGENAME eq ffmpeg.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[str] = set()
    for line in str(completed.stdout or "").splitlines():
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) >= 2 and parts[0].lower().startswith("ffmpeg"):
            pids.add(parts[1])
    return pids


def _generate_audio(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    run_hidden(
        [
            _tool("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _generate_background(path: Path, width: int, height: int) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        shade = int(24 + (y / max(1, height - 1)) * 60)
        for x in range(width):
            pixels[x, y] = (shade, int(shade * 0.6), int(140 + shade * 0.4))
    image.save(path)


def _template_b64(template_path: str) -> str:
    if template_path:
        raw = json.loads(Path(template_path).read_text(encoding="utf-8"))
    else:
        raw = {}
    return base64.b64encode(json.dumps(raw).encode("utf-8")).decode("ascii")


def _run_export(
    *,
    mp3: Path,
    background: Path,
    out_dir: Path,
    template_path: str,
    fps: int,
    width: int,
    height: int,
    speed_mode: str,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "visualizer.main",
        str(mp3),
        "unused_template.json",
        "--templateB64",
        _template_b64(template_path),
        "--background",
        str(background),
        "--outputDir",
        str(out_dir),
        "--ffmpeg",
        _tool("ffmpeg"),
        "--renderer",
        "gpu",
        "--fps",
        str(fps),
        "--width",
        str(width),
        "--height",
        str(height),
        "--speedMode",
        speed_mode,
    ]
    print("Running:", " ".join(cmd[:6]), "...", flush=True)
    proc = popen_hidden(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    last_message = ""
    for line in proc.stdout:
        stripped = line.strip()
        if stripped.startswith("MG_EVENT "):
            try:
                event = json.loads(stripped[len("MG_EVENT ") :])
            except json.JSONDecodeError:
                continue
            message = str(event.get("message") or "")
            if message and message != last_message:
                last_message = message
                print(f"  {event.get('status', '?'):>8} {message}", flush=True)
        elif stripped:
            print(f"  {stripped}", flush=True)
    return int(proc.wait())


def verify_output(*, mp4: Path, mp3: Path, out_dir: Path, report: Report) -> None:
    report.add("MP4 exists", mp4.is_file(), str(mp4))
    if not mp4.is_file():
        return
    video_sec = _duration_sec(mp4)
    audio_sec = _duration_sec(mp3)
    report.add("MP4 has a duration", video_sec > 0.1, f"{video_sec:.2f}s")
    if audio_sec > 0.1:
        report.add(
            "MP4 is not cut at the audio tail",
            video_sec + DURATION_TOLERANCE_SEC >= audio_sec,
            f"video {video_sec:.2f}s vs audio {audio_sec:.2f}s",
        )
    leftovers = sorted(p.name for p in out_dir.glob("ffmpeg_error_*.log"))
    report.add("no leftover ffmpeg stderr log", not leftovers, ", ".join(leftovers) or "clean")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mp3", default="", help="audio to render (omit with --generate-fixtures)")
    parser.add_argument("--background", default="", help="background image (omit with --generate-fixtures)")
    parser.add_argument("--template", default="", help="template JSON path (default: empty template)")
    parser.add_argument("--out", default=str(ROOT / "output" / "verify-tail"), help="output folder")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--speedMode", default="balanced")
    parser.add_argument("--seconds", type=float, default=20.0, help="generated fixture length")
    parser.add_argument("--generate-fixtures", action="store_true", help="create a tone + background, then exit")
    parser.add_argument("--check-only", default="", help="verify an existing MP4 instead of rendering")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    mp3 = Path(args.mp3) if args.mp3 else out_dir / "tone.mp3"
    background = Path(args.background) if args.background else out_dir / "background.png"

    if args.generate_fixtures:
        _generate_audio(mp3, float(args.seconds))
        _generate_background(background, int(args.width), int(args.height))
        print(f"fixtures: {mp3} ({_duration_sec(mp3):.2f}s), {background}")
        return 0

    report = Report()

    if args.check_only:
        verify_output(mp4=Path(args.check_only), mp3=mp3, out_dir=Path(args.check_only).parent, report=report)
        print(report.render())
        return 0 if report.ok else 1

    if not mp3.is_file():
        parser.error(f"audio not found: {mp3} (use --generate-fixtures or --mp3)")
    if not background.is_file():
        parser.error(f"background not found: {background} (use --generate-fixtures or --background)")

    before = _ffmpeg_pids()
    started = time.perf_counter()
    code = _run_export(
        mp3=mp3,
        background=background,
        out_dir=out_dir,
        template_path=args.template,
        fps=int(args.fps),
        width=int(args.width),
        height=int(args.height),
        speed_mode=str(args.speedMode),
    )
    elapsed = time.perf_counter() - started
    time.sleep(1.0)  # let the job object reap a terminated ffmpeg
    after = _ffmpeg_pids()

    report.add("render exited 0", code == 0, f"exit {code} after {elapsed:.1f}s")
    mp4 = out_dir / f"{mp3.stem}.mp4"
    verify_output(mp4=mp4, mp3=mp3, out_dir=out_dir, report=report)
    orphans = sorted(after - before)
    report.add("no orphan ffmpeg process", not orphans, ", ".join(orphans) or "none")

    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
