"""Single-track GPU export subprocess — adapted from python_app/services/video_export.py."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from features.video.lib.export_failure_log import append_export_event_line, tail_export_error_detail
from shared.lib.subprocess_utils import popen_hidden


def _b64_template(template: dict) -> str:
    raw = json.dumps(template, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def find_ffmpeg_from_path_hint(path_hint: str) -> str:
    from shared.lib.ffmpeg_paths import resolve_ffmpeg_path

    return resolve_ffmpeg_path(path_hint)


ExportEventHandler = Callable[[dict], None]
ExportExitHandler = Callable[[int], None]


@dataclass(frozen=True)
class ExportSettings:
    ffmpeg_path: str
    output_dir: str
    output_path: str
    fps: int
    width: int
    height: int
    speed_mode: str = "balanced"


class ExportJob:
    def __init__(
        self,
        *,
        mp3_path: str,
        template: dict,
        background_path: str,
        logo_path: str,
        settings: ExportSettings,
        on_event: ExportEventHandler | None = None,
        on_exit: ExportExitHandler | None = None,
    ) -> None:
        self.mp3_path = mp3_path
        self.template = template
        self.background_path = background_path
        self.logo_path = logo_path
        self.settings = settings
        self.on_event = on_event
        self.on_exit = on_exit
        self.proc: subprocess.Popen[str] | None = None
        self._cancel_requested = False
        self.backend_used: str = ""
        self.last_error_detail: str = ""
        self._error_lines: list[str] = []
        from features.video.lib.export_cancel import new_cancel_path

        self._cancel_path = new_cancel_path()

    def _note_event(self, event: dict) -> None:
        append_export_event_line(self._error_lines, event)

    def _publish_failure_detail(self, code: int) -> None:
        if int(code) == 0:
            return
        detail = tail_export_error_detail(self._error_lines)
        if detail:
            self.last_error_detail = detail
        if self.last_error_detail and self.on_event:
            self.on_event(
                {
                    "status": "failed",
                    "message": self.last_error_detail,
                    "progress": 0.0,
                }
            )

    def cancel(self) -> None:
        self._cancel_requested = True
        from features.video.lib.export_cancel import request_export_cancel

        # Soft-cancel first so the render loop can exit between frames / unblock
        # the encode queue without needing an immediate process kill.
        request_export_cancel(self._cancel_path)
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass
            return
        # Daemon path: ExportJob.proc is unset; ask the warm worker to stop, then
        # hard-kill the process tree if it does not exit promptly.
        try:
            from features.video.services.visualizer_daemon import get_visualizer_daemon

            get_visualizer_daemon().cancel_active(cancel_path=self._cancel_path)
        except Exception:
            pass

    def run_blocking(self, *, allow_daemon: bool = True) -> int:
        from features.video.lib.export_cancel import CANCEL_ENV, clear_export_cancel

        tpl_b64 = _b64_template(self.template)
        from shared.lib.resource_paths import get_package_root
        from shared.lib.runtime_paths import is_frozen_runtime

        project_dir = get_package_root() if is_frozen_runtime() else Path(__file__).resolve().parents[3]
        if is_frozen_runtime():
            cmd = [
                sys.executable,
                "--visualizer",
                str(self.mp3_path),
                "unused_template.json",
                "--templateB64",
                tpl_b64,
                "--background",
                str(self.background_path),
                "--logo",
                str(self.logo_path),
                "--outputDir",
                str(self.settings.output_dir),
                "--ffmpeg",
                str(self.settings.ffmpeg_path),
                "--renderer",
                "gpu",
                "--speedMode",
                str(self.settings.speed_mode or "balanced"),
                "--fps",
                str(int(self.settings.fps)),
                "--width",
                str(int(self.settings.width)),
                "--height",
                str(int(self.settings.height)),
            ]
        else:
            cmd = [
                sys.executable,
                "-m",
                "visualizer_video.main",
                str(self.mp3_path),
                "unused_template.json",
                "--templateB64",
                tpl_b64,
                "--background",
                str(self.background_path),
                "--logo",
                str(self.logo_path),
                "--outputDir",
                str(self.settings.output_dir),
                "--ffmpeg",
                str(self.settings.ffmpeg_path),
                "--renderer",
                "gpu",
                "--speedMode",
                str(self.settings.speed_mode or "balanced"),
                "--fps",
                str(int(self.settings.fps)),
                "--width",
                str(int(self.settings.width)),
                "--height",
                str(int(self.settings.height)),
            ]
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_dir}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(project_dir)
        )
        env[CANCEL_ENV] = self._cancel_path
        # Propagate GPU tier so each worker skips a visible nvidia-smi console probe.
        if not str(env.get("CAMXORA_GPU_TIER") or "").strip():
            try:
                from visualizer_video.export_gpu_tier import detect_export_gpu_tier

                env["CAMXORA_GPU_TIER"] = str(detect_export_gpu_tier())
            except Exception:
                pass
        clear_export_cancel(self._cancel_path)
        settings_msg = (
            f"Export settings · {int(self.settings.width)}x{int(self.settings.height)} "
            f"@ {int(self.settings.fps)}fps · speed={self.settings.speed_mode or 'balanced'}"
        )
        append_export_event_line(
            self._error_lines,
            {"status": "running", "message": settings_msg, "progress": 0.0},
        )
        if self.on_event:
            try:
                self.on_event({"status": "running", "message": settings_msg, "progress": 0.0})
            except Exception:
                pass
        try:
            return self._run_blocking_with_env(cmd, project_dir=project_dir, env=env, allow_daemon=allow_daemon)
        finally:
            clear_export_cancel(self._cancel_path)

    def _run_blocking_with_env(
        self,
        cmd: list[str],
        *,
        project_dir: Path,
        env: dict[str, str],
        allow_daemon: bool,
    ) -> int:
        # Warm daemon is single-job. Parallel export workers must use one-shot
        # subprocesses or they serialize (or race) on the shared daemon stdin.
        if allow_daemon:
            try:
                from features.video.services.visualizer_daemon import get_visualizer_daemon

                def _daemon_on_event(event: dict) -> None:
                    self._note_event(event)
                    if self.on_event:
                        self.on_event(event)

                daemon_code = get_visualizer_daemon().run_command(
                    cmd,
                    cwd=str(project_dir),
                    env=env,
                    on_event=_daemon_on_event,
                    on_exit=self.on_exit,
                )
                if self._cancel_requested:
                    self.backend_used = "daemon"
                    return 1
                if daemon_code is not None:
                    self.backend_used = "daemon"
                    code = int(daemon_code)
                    self._publish_failure_detail(code)
                    return code
            except Exception as exc:
                append_export_event_line(
                    self._error_lines,
                    {"status": "log", "message": f"visualizer daemon error: {exc}"},
                )
                if self._cancel_requested:
                    self.backend_used = "daemon"
                    return 1
        self.backend_used = "subprocess"
        self.proc = popen_hidden(
            cmd,
            cwd=str(project_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        assert self.proc.stdout is not None
        last_progress_emit = 0.0
        last_progress_message = ""
        try:
            for line in self.proc.stdout:
                if self._cancel_requested:
                    break
                stripped = line.strip()
                if stripped.startswith("MG_EVENT "):
                    payload = stripped[len("MG_EVENT ") :].strip()
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        event = {"status": "log", "message": payload}
                    self._note_event(event)
                    if self.on_event:
                        status = str(event.get("status") or "").strip().lower()
                        if status == "running":
                            now = time.monotonic()
                            message = str(event.get("message") or "")
                            if (now - last_progress_emit) < 0.5 and message == last_progress_message:
                                continue
                            last_progress_emit = now
                            last_progress_message = message
                        self.on_event(event)
                elif stripped:
                    log_event = {"status": "log", "message": stripped}
                    self._note_event(log_event)
                    if self.on_event:
                        self.on_event(log_event)
        finally:
            code = int(self.proc.wait())
            self._publish_failure_detail(code)
            if self.on_exit:
                self.on_exit(code)
            return code
