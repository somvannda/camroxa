"""Merge worker for combining multiple MP4 files into a single video.

Handles:
- FFprobe duration validation
- File stability checks (ensures MP4 is fully written)
- Random shuffle with order preservation log
- FFmpeg concat demuxer merge with re-encode fallback
- Temp file cleanup
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ...utils.subprocess_utils import no_window_kwargs


class MergeWorker:
    """Merges multiple MP4 files into a single concatenated video."""

    def __init__(self, on_status: callable | None = None) -> None:
        """
        Args:
            on_status: Optional callback(msg: str) for status updates during merge.
        """
        self.on_status = on_status

    def merge(self, ffmpeg_path: str, mp4_paths: list[str], target_path: str) -> None:
        """Merge MP4 files into target_path using FFmpeg concat demuxer.

        Raises RuntimeError if merge fails or not enough valid files.
        """
        files = [str(p).strip() for p in (mp4_paths or []) if str(p).strip()]
        if len(files) < 2:
            raise RuntimeError("Not enough MP4 files to merge")

        ffprobe_path = self._resolve_ffprobe(ffmpeg_path)
        list_file = None
        tmp_dir = None
        tmp_inputs: list[str] = []
        try:
            valid_files = self._validate_files(files, ffprobe_path)
            if len(valid_files) < 2:
                raise RuntimeError("Not enough valid MP4 files to merge")

            orig_order = [Path(p).name for p in valid_files]
            random.shuffle(valid_files)
            shuffled_order = [Path(p).name for p in valid_files]
            self._write_order_log(target_path, orig_order, shuffled_order)

            parent = Path(str(target_path)).parent
            tmp_dir = Path(tempfile.mkdtemp(prefix="mg_merge_", dir=str(parent)))
            tmp_inputs = self._prepare_temp_inputs(valid_files, tmp_dir)

            list_file = self._write_concat_list(tmp_inputs)
            self._run_merge(ffmpeg_path, list_file, target_path)
        finally:
            if list_file:
                try:
                    Path(list_file).unlink(missing_ok=True)
                except Exception:
                    pass
            if tmp_dir:
                try:
                    shutil.rmtree(str(tmp_dir), ignore_errors=True)
                except Exception:
                    pass

    @staticmethod
    def _resolve_ffprobe(ffmpeg_path: str) -> str:
        try:
            ffmpeg_dir = str(Path(str(ffmpeg_path)).parent) if ffmpeg_path else ""
            candidate = Path(ffmpeg_dir) / "ffprobe.exe" if ffmpeg_dir else Path("ffprobe.exe")
            if candidate.exists():
                return str(candidate)
            candidate2 = Path(str(ffmpeg_path)).with_name("ffprobe.exe")
            if candidate2.exists():
                return str(candidate2)
        except Exception:
            pass
        return ""

    def _validate_files(self, files: list[str], ffprobe_path: str) -> list[str]:
        valid: list[str] = []
        skipped: list[str] = []
        for src in files:
            src_p = Path(src)
            try:
                if not src_p.exists() or not src_p.is_file():
                    skipped.append(str(src_p.name or src))
                    continue
                if int(src_p.stat().st_size) < 50_000:
                    skipped.append(str(src_p.name))
                    continue
                if not self._is_file_stable(src_p):
                    skipped.append(str(src_p.name))
                    continue
                if ffprobe_path:
                    d = self._probe_duration(str(src_p), ffprobe_path)
                    if d <= 0.1:
                        skipped.append(str(src_p.name))
                        continue
            except Exception:
                skipped.append(str(src_p.name or src))
                continue
            valid.append(str(src_p))

        if skipped and self.on_status:
            shown = ", ".join(skipped[:8])
            extra = f" (+{len(skipped) - 8} more)" if len(skipped) > 8 else ""
            self.on_status(f"Auto-Video: skipped {len(skipped)} invalid MP4(s): {shown}{extra}")

        return valid

    @staticmethod
    def _probe_duration(path_text: str, ffprobe_path: str) -> float:
        try:
            out = subprocess.check_output(
                [
                    ffprobe_path,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1",
                    str(path_text),
                ],
                text=True,
                timeout=12,
                **no_window_kwargs(),
            )
            return max(0.0, float(str(out or "").strip() or "0"))
        except Exception:
            return 0.0

    @staticmethod
    def _is_file_stable(p: Path) -> bool:
        try:
            a = p.stat()
        except Exception:
            return False
        try:
            with open(str(p), "rb") as f:
                f.read(1)
        except Exception:
            return False
        for _ in range(10):
            time.sleep(0.4)
            try:
                b = p.stat()
            except Exception:
                return False
            if int(a.st_size) == int(b.st_size) and int(a.st_mtime_ns) == int(b.st_mtime_ns):
                return True
            a = b
        return False

    @staticmethod
    def _write_order_log(target_path: str, orig_order: list[str], shuffled_order: list[str]) -> None:
        try:
            stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}"
            order_path = Path(str(target_path)).parent / f"MERGE_ORDER_{stamp}.txt"
            order_path.write_text(
                "ORIGINAL:\n"
                + "\n".join(orig_order)
                + "\n\nSHUFFLED:\n"
                + "\n".join(shuffled_order)
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    @staticmethod
    def _prepare_temp_inputs(valid_files: list[str], tmp_dir: Path) -> list[str]:
        tmp_inputs: list[str] = []
        for idx, src in enumerate(valid_files):
            src_p = Path(src)
            dst_p = tmp_dir / f"{idx + 1:04d}.mp4"
            try:
                os.link(str(src_p), str(dst_p))
            except Exception:
                shutil.copy2(str(src_p), str(dst_p))
            tmp_inputs.append(str(dst_p).replace("\\", "/"))
        return tmp_inputs

    @staticmethod
    def _write_concat_list(tmp_inputs: list[str]) -> str:
        lines = ["ffconcat version 1.0"]
        for p in tmp_inputs:
            if "\n" in p or "\r" in p:
                raise RuntimeError("Invalid MP4 path for ffconcat list")
            lines.append(f"file '{p}'")
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
            list_file = f.name
            f.write("\n".join(lines) + "\n")
        return list_file

    @staticmethod
    def _run_merge(ffmpeg_path: str, list_file: str, target_path: str) -> None:
        cmd = [str(ffmpeg_path), "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(target_path)]
        code = int(subprocess.call(cmd, **no_window_kwargs()))
        if code == 0 and Path(target_path).exists():
            return
        # Fallback: re-encode
        cmd2 = [
            str(ffmpeg_path), "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart",
            str(target_path),
        ]
        code2 = int(subprocess.call(cmd2, **no_window_kwargs()))
        if code2 != 0 or not Path(target_path).exists():
            raise RuntimeError("FFmpeg merge failed")

    # ── Advanced merge with progress, cancellation, and two-phase fallback ──

    def merge_with_progress(
        self,
        ffmpeg_path: str,
        mp4_paths: list[str],
        target_path: str,
        *,
        on_progress: callable | None = None,
        is_cancelled: callable | None = None,
    ) -> dict:
        """Merge MP4 files with progress reporting and cancellation support.

        Args:
            ffmpeg_path: Path to ffmpeg executable.
            mp4_paths: List of MP4 file paths to merge.
            target_path: Output file path.
            on_progress: Callback(progress: float 0-1) for progress updates.
            is_cancelled: Callback() -> bool to check for cancellation.

        Returns:
            dict with keys:
            - 'ok': bool – whether merge succeeded
            - 'output_path': str – path to merged file (if ok)
            - 'error': str – error message (if not ok)
            - 'cancelled': bool – whether merge was cancelled
            - 'skipped': list[str] – skipped input files
            - 'valid_count': int – number of valid input files
        """
        from collections import deque

        files = [str(p).strip() for p in (mp4_paths or []) if str(p).strip()]
        if len(files) < 2:
            return {"ok": False, "error": "Not enough MP4 files to merge", "cancelled": False, "skipped": [], "valid_count": 0}

        ffprobe_path = self._resolve_ffprobe(ffmpeg_path)

        def _cancelled() -> bool:
            return bool(is_cancelled()) if is_cancelled else False

        def _probe_duration(path_text: str) -> float:
            if not ffprobe_path or not Path(ffprobe_path).exists():
                return 0.0
            try:
                out = subprocess.check_output(
                    [ffprobe_path, "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", str(path_text)],
                    text=True,
                    **no_window_kwargs(),
                )
                return max(0.0, float(str(out or "").strip() or "0"))
            except Exception:
                return 0.0

        # Validate files
        valid_mp4s: list[str] = []
        skipped: list[str] = []
        durations: dict[str, float] = {}
        ffprobe_ok = bool(ffprobe_path) and Path(ffprobe_path).exists()

        for mp4 in files:
            pth = str(mp4).strip()
            p = Path(pth)
            try:
                if not p.exists() or not p.is_file():
                    skipped.append(pth)
                    continue
                if int(p.stat().st_size) < 50_000:
                    skipped.append(pth)
                    continue
                if not self._is_file_stable(p):
                    skipped.append(f"{p.name} (still writing)")
                    continue
            except Exception:
                skipped.append(pth)
                continue
            if ffprobe_ok:
                d = _probe_duration(pth)
                if d <= 0.05:
                    skipped.append(pth)
                    continue
                durations[pth] = d
            valid_mp4s.append(pth)

        if _cancelled():
            return {"ok": False, "error": "Merge cancelled", "cancelled": True, "skipped": skipped, "valid_count": len(valid_mp4s)}

        if len(valid_mp4s) < 2:
            return {"ok": False, "error": "Not enough valid MP4 files", "cancelled": False, "skipped": skipped, "valid_count": len(valid_mp4s)}

        # Report skipped files via on_status
        if skipped and self.on_status:
            shown = ", ".join([Path(x).name for x in skipped[:8]])
            extra = f" (+{len(skipped) - 8} more)" if len(skipped) > 8 else ""
            self.on_status(f"Auto-Video: skipped {len(skipped)} incomplete MP4(s): {shown}{extra}")

        # Shuffle and build concat list
        random.shuffle(valid_mp4s)
        lines = []
        total_duration_sec = 0.0
        for mp4 in valid_mp4s:
            p = str(mp4).replace("\\", "/")
            p = p.replace("'", "\\'")
            lines.append(f"file '{p}'")
            if ffprobe_ok:
                total_duration_sec += float(durations.get(mp4, 0.0) or 0.0)

        list_file = None
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
                list_file = f.name
                f.write("\n".join(lines) + "\n")

            def _run_ffmpeg(cmd: list[str]) -> tuple[int, str]:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **no_window_kwargs())
                last_sent = -1
                log_tail: deque[str] = deque(maxlen=160)
                if proc.stdout:
                    for line in proc.stdout:
                        if _cancelled():
                            try:
                                proc.terminate()
                            except Exception:
                                try:
                                    proc.kill()
                                except Exception:
                                    pass
                            break
                        s = str(line).strip()
                        if s:
                            log_tail.append(s)
                        if "=" in s and total_duration_sec > 0.0:
                            k, v = s.split("=", 1)
                            k = k.strip().lower()
                            v = v.strip()
                            if k == "out_time_ms":
                                try:
                                    out_time_ms = int(v)
                                except Exception:
                                    out_time_ms = 0
                                ratio = float(out_time_ms) / float(max(1, int(total_duration_sec * 1000000.0)))
                                ratio = max(0.0, min(1.0, ratio))
                                pct = int(ratio * 100.0)
                                if pct != last_sent:
                                    last_sent = pct
                                    if on_progress:
                                        on_progress(ratio)
                code = int(proc.wait())
                if _cancelled():
                    code = -2
                return (code, "\n".join(list(log_tail)[-40:]))

            def _merged_duration_ok() -> bool:
                if total_duration_sec <= 0.0:
                    return True
                merged = _probe_duration(str(target_path))
                return merged >= float(total_duration_sec) * 0.97

            # Phase 1: copy merge
            copy_cmd = [
                ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                "-c", "copy", "-progress", "pipe:1", "-nostats", str(target_path),
            ]
            code, tail = _run_ffmpeg(copy_cmd)
            if _cancelled():
                return {"ok": False, "error": "Merge cancelled", "cancelled": True, "skipped": skipped, "valid_count": len(valid_mp4s)}

            ok = code == 0 and _merged_duration_ok()
            if not ok:
                try:
                    Path(str(target_path)).unlink(missing_ok=True)
                except Exception:
                    pass
                # Phase 2A: concat demuxer + re-encode (much faster than filter_complex)
                # Uses the same concat list file but re-encodes instead of copying
                reencode_cmd = [
                    ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                    "-fflags", "+genpts",
                    "-af", "aresample=async=1000",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    "-progress", "pipe:1", "-nostats",
                    str(target_path),
                ]
                code2, tail2 = _run_ffmpeg(reencode_cmd)
                if _cancelled():
                    return {"ok": False, "error": "Merge cancelled", "cancelled": True, "skipped": skipped, "valid_count": len(valid_mp4s)}
                ok = code2 == 0 and _merged_duration_ok()
                if not ok:
                    # Phase 2B: last resort — filter_complex concat (handles incompatible inputs)
                    try:
                        Path(str(target_path)).unlink(missing_ok=True)
                    except Exception:
                        pass
                    n = len(valid_mp4s)
                    if n >= 2:
                        inputs: list[str] = []
                        parts: list[str] = []
                        for i, mp4 in enumerate(valid_mp4s):
                            inputs.extend(["-i", str(mp4)])
                            parts.append(f"[{i}:v:0][{i}:a:0]")
                        filter_text = "".join(parts) + f"concat=n={n}:v=1:a=1[v][a]"
                        filter_cmd = [
                            ffmpeg_path, "-y", *inputs, "-filter_complex", filter_text,
                            "-fflags", "+genpts",
                            "-map", "[v]", "-map", "[a]",
                            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart",
                            "-progress", "pipe:1", "-nostats",
                            str(target_path),
                        ]
                        code3, tail3 = _run_ffmpeg(filter_cmd)
                        if _cancelled():
                            return {"ok": False, "error": "Merge cancelled", "cancelled": True, "skipped": skipped, "valid_count": len(valid_mp4s)}
                        ok = code3 == 0 and _merged_duration_ok()
                        code = code3 if not ok else 0
                        tail = tail3 if not ok else ""
                else:
                    code = 0

            if ok:
                return {"ok": True, "output_path": str(target_path), "cancelled": False, "skipped": skipped, "valid_count": len(valid_mp4s)}
            else:
                detail = f"ffmpeg merge failed (code {code})"
                if tail:
                    flat = str(tail).replace("\r", "").replace("\n", " | ").strip()
                    detail = f"{detail} | {flat}"
                return {"ok": False, "error": detail, "cancelled": False, "skipped": skipped, "valid_count": len(valid_mp4s)}
        finally:
            try:
                if list_file and Path(list_file).exists():
                    Path(list_file).unlink(missing_ok=True)
            except Exception:
                pass
