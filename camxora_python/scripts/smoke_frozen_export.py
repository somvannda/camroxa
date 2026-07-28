#!/usr/bin/env python3
"""Smoke-test frozen Camxora.exe GPU export without installing.

Usage (from camxora_python):
  python scripts/smoke_frozen_export.py
  python scripts/smoke_frozen_export.py --mp3 "C:\\path\\track.mp3" --full-track-analysis
  python scripts/smoke_frozen_export.py --parallel 2

Exit 0 only when required milestones appear (spectrum/onset/beats + encode done
for short clips; analysis-complete for optional long-track gate).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = ROOT / "dist" / "Camxora"
DEFAULT_TEMPLATE = ROOT / "tests" / "fixtures" / "golden_frames" / "minimal" / "template.json"
DEFAULT_BG = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Camxora"
    / "Media"
    / "Suno"
    / "bass-vortex"
    / "2026-07-29_Neon-Drift"
    / "background-16x9.png"
)
DEFAULT_LONG_MP3 = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Camxora"
    / "Media"
    / "Suno"
    / "bass-vortex"
    / "2026-07-29_Neon-Drift"
    / "2. Echoes in Empty Rooms_Alt.mp3"
)
DEFAULT_LONG_MP3_B = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Camxora"
    / "Media"
    / "Suno"
    / "bass-vortex"
    / "2026-07-29_Neon-Drift"
    / "3. I Stand Whole_Alt.mp3"
)
DIAG_LOG = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Camxora" / "logs" / "audio-load-diag.log"
)


REQUIRED_DIAG = (
    "soundfile.read ok",
    "resample ok",
    "spectrum ok",
    "onset ok",
    "beats ok",
    "AudioAnalyzer done",
)


def _ffprobe_duration_sec(ffprobe: Path, media: Path) -> float:
    cmd = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media),
    ]
    out = subprocess.check_output(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).strip()
    return float(out)


def _resolve_ffprobe(ffmpeg: Path) -> Path:
    sibling = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe")
    if sibling.is_file():
        return sibling
    # Bundled tree may only ship ffmpeg; fall back to ffmpeg -i parse is worse,
    # so require ffprobe next to ffmpeg or on PATH.
    which = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if which:
        return Path(which)
    raise FileNotFoundError(f"ffprobe not found next to {ffmpeg}")


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _diag_offset() -> int:
    try:
        return DIAG_LOG.stat().st_size if DIAG_LOG.is_file() else 0
    except OSError:
        return 0


def _diag_tail(from_offset: int) -> str:
    try:
        if not DIAG_LOG.is_file():
            return ""
        with DIAG_LOG.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(max(0, int(from_offset)))
            return handle.read()
    except OSError:
        return ""


def _missing_milestones(text: str, required: tuple[str, ...]) -> list[str]:
    return [item for item in required if item not in text]


def _make_short_clip(*, ffmpeg: Path, src: Path, out: Path, seconds: float) -> None:
    cmd = [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-t",
        f"{float(seconds):.2f}",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(out),
    ]
    subprocess.run(cmd, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _template_b64(path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return base64.b64encode(json.dumps(raw, separators=(",", ":")).encode("utf-8")).decode("ascii")


def _popen_kwargs() -> dict:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
        except Exception:
            pass
    return kwargs


def run_one_export(
    *,
    exe: Path,
    mp3: Path,
    background: Path,
    template_b64: str,
    ffmpeg: Path,
    out_dir: Path,
    label: str,
    timeout_s: float,
    stop_after_analysis: bool = False,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(exe),
        "--visualizer",
        str(mp3),
        "unused_template.json",
        "--templateB64",
        template_b64,
        "--background",
        str(background),
        "--logo",
        "",
        "--outputDir",
        str(out_dir),
        "--ffmpeg",
        str(ffmpeg),
        "--renderer",
        "gpu",
        "--speedMode",
        "very_fast",
        "--fps",
        str(int(fps)),
        "--width",
        str(int(width)),
        "--height",
        str(int(height)),
    ]
    diag0 = _diag_offset()
    _log(f"{label}: start timeout={timeout_s:.0f}s stop_after_analysis={stop_after_analysis}")
    _log(f"{label}: mp3={mp3.name} ({mp3.stat().st_size} bytes)")
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=str(exe.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **_popen_kwargs(),
    )
    events: list[str] = []
    saw_analysis_done = False
    saw_encode = False
    saw_done = False
    last_msg = ""
    assert proc.stdout is not None
    try:
        while True:
            if time.monotonic() - started > timeout_s:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise TimeoutError(f"{label}: timed out after {timeout_s:.0f}s last={last_msg!r}")

            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("MG_EVENT "):
                payload = stripped[len("MG_EVENT ") :].strip()
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    event = {"status": "log", "message": payload}
                msg = str(event.get("message") or event.get("status") or "")
                status = str(event.get("status") or "").lower()
                last_msg = msg
                events.append(f"{status}:{msg}")
                if status == "running" and msg:
                    _log(f"{label}: {msg}")
                if "Audio analysis complete" in msg or "preparing encoder" in msg:
                    saw_analysis_done = True
                if "Encod" in msg or "Writing" in msg or "frame" in msg.lower():
                    saw_encode = True
                if status == "done":
                    saw_done = True
                if stop_after_analysis and saw_analysis_done:
                    # Wait briefly for the final "AudioAnalyzer done" diag flush
                    # (emitted after the progress callback returns).
                    deadline = time.monotonic() + 5.0
                    while time.monotonic() < deadline:
                        if "AudioAnalyzer done" in _diag_tail(diag0):
                            break
                        time.sleep(0.1)
                    _log(f"{label}: analysis milestone hit — stopping worker")
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break
            else:
                if "[audio-diag]" in stripped or "ERROR" in stripped or "Traceback" in stripped:
                    _log(f"{label}: {stripped[:240]}")
                events.append(stripped[:300])
        code = int(proc.poll() if proc.poll() is not None else proc.wait())
    finally:
        if proc.poll() is None:
            proc.kill()

    diag_text = _diag_tail(diag0)
    elapsed = time.monotonic() - started
    missing = _missing_milestones(diag_text, REQUIRED_DIAG)
    mp4s = sorted(out_dir.glob("*.mp4"))
    result = {
        "label": label,
        "exit_code": code,
        "elapsed_s": round(elapsed, 2),
        "missing_diag": missing,
        "saw_analysis_done": saw_analysis_done,
        "saw_encode": saw_encode,
        "saw_done": saw_done,
        "mp4_count": len(mp4s),
        "mp4_bytes": int(mp4s[-1].stat().st_size) if mp4s else 0,
        "last_msg": last_msg,
        "diag_snippet": "\n".join(diag_text.strip().splitlines()[-12:]),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST)
    parser.add_argument("--mp3", type=Path, default=DEFAULT_LONG_MP3)
    parser.add_argument("--mp3-b", type=Path, default=DEFAULT_LONG_MP3_B)
    parser.add_argument("--background", type=Path, default=DEFAULT_BG)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--clip-seconds", type=float, default=20.0)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument(
        "--parallel-long",
        type=int,
        default=2,
        help="How many full-length tracks to encode at once (repro installer hang).",
    )
    parser.add_argument("--full-track-analysis", action="store_true", default=False)
    parser.add_argument("--skip-full-track-analysis", action="store_true")
    parser.add_argument(
        "--full-track-encode",
        action="store_true",
        default=True,
        help="Encode full source MP3(s) to MP4 (default). Required for installer handoff.",
    )
    parser.add_argument("--skip-full-track-encode", action="store_true")
    parser.add_argument("--short-timeout", type=float, default=300.0)
    parser.add_argument("--analysis-timeout", type=float, default=600.0)
    parser.add_argument("--full-encode-timeout", type=float, default=1800.0)
    args = parser.parse_args()
    do_analysis_only = bool(args.full_track_analysis) and not bool(args.skip_full_track_analysis)
    do_full_encode = bool(args.full_track_encode) and not bool(args.skip_full_track_encode)

    exe = args.dist / "Camxora.exe"
    ffmpeg = args.dist / "ffmpeg" / "ffmpeg.exe"
    if not exe.is_file():
        _log(f"FAIL: missing exe {exe}")
        return 2
    if not ffmpeg.is_file():
        _log(f"FAIL: missing ffmpeg {ffmpeg}")
        return 2
    if not args.mp3.is_file():
        _log(f"FAIL: missing mp3 {args.mp3}")
        return 2
    if not args.background.is_file():
        _log(f"FAIL: missing background {args.background}")
        return 2
    if not args.template.is_file():
        _log(f"FAIL: missing template {args.template}")
        return 2

    tpl_b64 = _template_b64(args.template)
    work = Path(tempfile.mkdtemp(prefix="camxora_frozen_smoke_"))
    _log(f"work dir: {work}")
    clip = work / "clip20.mp3"
    _make_short_clip(ffmpeg=ffmpeg, src=args.mp3, out=clip, seconds=float(args.clip_seconds))

    failures: list[str] = []

    # 1) Short full encode (and optional parallel)
    parallel = max(1, min(10, int(args.parallel)))
    short_results: list[dict] = []
    if parallel == 1:
        out = work / "short1"
        short_results.append(
            run_one_export(
                exe=exe,
                mp3=clip,
                background=args.background,
                template_b64=tpl_b64,
                ffmpeg=ffmpeg,
                out_dir=out,
                label="short-encode",
                timeout_s=float(args.short_timeout),
            )
        )
    else:
        # Launch N workers nearly together (reproduces dual-worker hang).
        import concurrent.futures

        clips = []
        for i in range(parallel):
            c = work / f"clip20_{i+1}.mp3"
            if i == 0:
                c.write_bytes(clip.read_bytes())
            else:
                # Slightly different length so caches do not collide.
                _make_short_clip(
                    ffmpeg=ffmpeg,
                    src=args.mp3,
                    out=c,
                    seconds=float(args.clip_seconds) + float(i),
                )
            clips.append(c)

        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
            futs = []
            for i, c in enumerate(clips):
                futs.append(
                    pool.submit(
                        run_one_export,
                        exe=exe,
                        mp3=c,
                        background=args.background,
                        template_b64=tpl_b64,
                        ffmpeg=ffmpeg,
                        out_dir=work / f"short_p{i+1}",
                        label=f"parallel-{i+1}",
                        timeout_s=float(args.short_timeout),
                    )
                )
            for fut in concurrent.futures.as_completed(futs):
                short_results.append(fut.result())

    for res in short_results:
        ok = (
            not res["missing_diag"]
            and res["saw_done"]
            and res["mp4_bytes"] > 10_000
            and res["exit_code"] == 0
        )
        _log(
            f"{res['label']}: exit={res['exit_code']} elapsed={res['elapsed_s']}s "
            f"mp4={res['mp4_bytes']} missing={res['missing_diag']} done={res['saw_done']}"
        )
        if res["diag_snippet"]:
            print(res["diag_snippet"], flush=True)
        if not ok:
            failures.append(
                f"{res['label']} failed exit={res['exit_code']} missing={res['missing_diag']} "
                f"done={res['saw_done']} mp4={res['mp4_bytes']} last={res['last_msg']!r}"
            )

    # 2) Optional analysis-only gate (fast)
    if do_analysis_only:
        long_res = run_one_export(
            exe=exe,
            mp3=args.mp3,
            background=args.background,
            template_b64=tpl_b64,
            ffmpeg=ffmpeg,
            out_dir=work / "long_analysis",
            label="long-analysis",
            timeout_s=float(args.analysis_timeout),
            stop_after_analysis=True,
        )
        ok = long_res["saw_analysis_done"] and not long_res["missing_diag"]
        _log(
            f"long-analysis: exit={long_res['exit_code']} elapsed={long_res['elapsed_s']}s "
            f"missing={long_res['missing_diag']} analysis_done={long_res['saw_analysis_done']}"
        )
        if long_res["diag_snippet"]:
            print(long_res["diag_snippet"], flush=True)
        if not ok:
            failures.append(
                f"long-analysis failed missing={long_res['missing_diag']} "
                f"analysis_done={long_res['saw_analysis_done']} last={long_res['last_msg']!r}"
            )

    # 3) Full-track complete MP4(s) — parallel long encodes match Progress multi-worker
    if do_full_encode:
        import concurrent.futures

        src_tracks: list[Path] = [args.mp3]
        parallel_long = max(1, min(10, int(args.parallel_long)))
        if parallel_long >= 2:
            # Prefer real sibling tracks in the same album folder (matches Progress).
            siblings = sorted(
                p for p in args.mp3.parent.glob("*.mp3") if p.is_file()
            )
            if args.mp3_b.is_file() and args.mp3_b not in siblings:
                siblings.append(args.mp3_b)
            # Stable unique order with primary first.
            ordered: list[Path] = []
            for candidate in [args.mp3, *siblings]:
                if candidate.is_file() and candidate not in ordered:
                    ordered.append(candidate)
            src_tracks = ordered[:parallel_long]
            # Pad with offset clips if Preferences asks for more workers than tracks.
            while len(src_tracks) < parallel_long:
                pad_i = len(src_tracks)
                pad = work / f"long_pad_{pad_i+1}.mp3"
                _make_short_clip(
                    ffmpeg=ffmpeg,
                    src=args.mp3,
                    out=pad,
                    seconds=min(90.0, float(args.clip_seconds) * 4.0),
                )
                # unique-ish by rewriting with ffmpeg -ss
                pad2 = work / f"long_pad_{pad_i+1}_ss.mp3"
                subprocess.run(
                    [
                        str(ffmpeg),
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-ss",
                        str(10 * (pad_i + 1)),
                        "-i",
                        str(args.mp3),
                        "-t",
                        "90",
                        "-ac",
                        "2",
                        "-ar",
                        "48000",
                        "-c:a",
                        "libmp3lame",
                        "-b:a",
                        "192k",
                        str(pad2),
                    ],
                    check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                src_tracks.append(pad2)
            _log(f"parallel-long tracks ({len(src_tracks)}): " + ", ".join(p.name for p in src_tracks))

        ffprobe: Path | None = None
        try:
            ffprobe = _resolve_ffprobe(ffmpeg)
        except Exception as exc:
            _log(f"WARN: ffprobe unavailable ({exc}); will only check MP4 size/exit")

        def _run_long(idx: int, track: Path) -> dict:
            src_dur = 0.0
            if ffprobe is not None:
                try:
                    src_dur = _ffprobe_duration_sec(ffprobe, track)
                except Exception:
                    src_dur = 0.0
            out_dir = work / f"long_encode_{idx+1}"
            enc = run_one_export(
                exe=exe,
                mp3=track,
                background=args.background,
                template_b64=tpl_b64,
                ffmpeg=ffmpeg,
                out_dir=out_dir,
                label=f"long-encode-{idx+1}",
                timeout_s=float(args.full_encode_timeout),
                stop_after_analysis=False,
                width=1280,
                height=720,
                fps=30,
            )
            out_mp4s = sorted(out_dir.glob("*.mp4"))
            out_mp4 = out_mp4s[-1] if out_mp4s else None
            out_dur = 0.0
            dur_ok = True
            if ffprobe is not None and out_mp4 is not None and src_dur > 1.0:
                try:
                    out_dur = _ffprobe_duration_sec(ffprobe, out_mp4)
                    dur_ok = abs(out_dur - src_dur) <= max(2.0, src_dur * 0.05)
                except Exception as exc:
                    dur_ok = False
                    enc["ffprobe_error"] = str(exc)
            enc["src_dur"] = src_dur
            enc["out_dur"] = out_dur
            enc["dur_ok"] = dur_ok
            enc["out_mp4"] = str(out_mp4) if out_mp4 else ""
            return enc

        long_results: list[dict] = []
        if len(src_tracks) == 1:
            long_results.append(_run_long(0, src_tracks[0]))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(src_tracks)) as pool:
                futs = [pool.submit(_run_long, i, t) for i, t in enumerate(src_tracks)]
                for fut in concurrent.futures.as_completed(futs):
                    long_results.append(fut.result())

        for long_enc in long_results:
            # Complete MP4 is the handoff gate. Diag milestones may be absent on
            # disk cache hits (analysis skipped in this process).
            ok = (
                long_enc["saw_done"]
                and long_enc["exit_code"] == 0
                and long_enc["mp4_bytes"] > 100_000
                and bool(long_enc.get("dur_ok", True))
            )
            _log(
                f"{long_enc['label']}: exit={long_enc['exit_code']} elapsed={long_enc['elapsed_s']}s "
                f"mp4={long_enc['mp4_bytes']} src_dur={long_enc.get('src_dur', 0):.1f}s "
                f"out_dur={long_enc.get('out_dur', 0):.1f}s missing={long_enc['missing_diag']} "
                f"done={long_enc['saw_done']}"
            )
            if long_enc.get("diag_snippet"):
                print(long_enc["diag_snippet"], flush=True)
            if long_enc.get("out_mp4"):
                _log(f"{long_enc['label']} output: {long_enc['out_mp4']}")
            if not ok:
                failures.append(
                    f"{long_enc['label']} failed exit={long_enc['exit_code']} "
                    f"missing={long_enc['missing_diag']} done={long_enc['saw_done']} "
                    f"mp4={long_enc['mp4_bytes']} src_dur={long_enc.get('src_dur', 0):.1f} "
                    f"out_dur={long_enc.get('out_dur', 0):.1f} last={long_enc['last_msg']!r}"
                )

    if failures:
        _log("SMOKE FAIL")
        for item in failures:
            _log(f"  - {item}")
        return 1
    _log("SMOKE PASS — complete frozen video generation OK (safe to build installer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
