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
from typing import Callable, Optional, TYPE_CHECKING

from ..utils.subprocess_utils import no_window_kwargs

if TYPE_CHECKING:
    from ..visualizer.contracts import RenderRequest


def _b64_template(template: dict) -> str:
    raw = json.dumps(template, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


@dataclass(frozen=True)
class ExportSettings:
    ffmpeg_path: str
    output_dir: str
    fps: int
    width: int
    height: int
    speed_mode: str = "balanced"


ExportEventHandler = Callable[[dict], None]


class ExportJob:
    """Manages a single video export subprocess.

    Can be constructed directly with individual parameters or from a
    ``RenderRequest`` DTO via the :meth:`from_render_request` classmethod.
    """

    def __init__(
        self,
        mp3_path: str,
        template: dict,
        background_path: str,
        logo_path: str,
        template_path_fallback: str,
        settings: ExportSettings,
        on_event: Optional[ExportEventHandler] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> None:
        self.mp3_path = mp3_path
        self.template = template
        self.background_path = background_path
        self.logo_path = logo_path
        self.template_path_fallback = template_path_fallback
        self.settings = settings
        self.on_event = on_event
        self.on_exit = on_exit
        self.proc: subprocess.Popen | None = None

    @classmethod
    def from_render_request(
        cls,
        request: "RenderRequest",
        *,
        ffmpeg_path: str,
        speed_mode: str = "balanced",
        template_path_fallback: str = "unused_template.json",
        on_event: Optional[ExportEventHandler] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> "ExportJob":
        """Construct an ExportJob from a RenderRequest DTO.

        This is the preferred entry point for creating export jobs when the
        caller has already assembled the render parameters into a DTO.
        """
        settings = ExportSettings(
            ffmpeg_path=ffmpeg_path,
            output_dir=request.output_path,
            fps=request.fps,
            width=request.width,
            height=request.height,
            speed_mode=speed_mode,
        )
        return cls(
            mp3_path=request.audio_path,
            template=request.template,
            background_path=request.background_path,
            logo_path=request.logo_path,
            template_path_fallback=template_path_fallback,
            settings=settings,
            on_event=on_event,
            on_exit=on_exit,
        )

    def start(self) -> None:
        tpl_b64 = _b64_template(self.template)
        project_dir = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        cmd = [
            sys.executable,
            "-m",
            "python_app.visualizer.main",
            str(self.mp3_path),
            str(self.template_path_fallback),
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

        self.proc = subprocess.Popen(
            cmd,
            cwd=str(project_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            **no_window_kwargs(),
        )

        # Assign the visualizer subprocess to the app's kill-on-close Job
        # Object. Child processes it spawns (ffmpeg) automatically inherit job
        # membership, so when this app exits — even by crash — Windows
        # terminates the entire tree and no orphaned ffmpeg.exe survives.
        try:
            from ..utils.subprocess_utils import assign_to_job
            assign_to_job(self.proc)
        except Exception:
            pass

        t = threading.Thread(target=self._pump, daemon=True)
        t.start()

    def cancel(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                return None

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        last_progress_emit = 0.0
        try:
            for line in self.proc.stdout:
                s = line.strip()
                if s.startswith("MG_EVENT "):
                    payload = s[len("MG_EVENT ") :].strip()
                    try:
                        evt = json.loads(payload)
                    except Exception:
                        evt = {"status": "log", "message": payload}
                    if self.on_event:
                        # Throttle progress events to avoid flooding the UI thread
                        status = str(evt.get("status", "")).strip().lower()
                        if status == "running" and evt.get("progress") is not None:
                            now = time.monotonic()
                            if (now - last_progress_emit) < 0.5:
                                continue  # skip this progress event
                            last_progress_emit = now
                        self.on_event(evt)
                else:
                    if self.on_event and s:
                        self.on_event({"status": "log", "message": s})
        finally:
            code = int(self.proc.wait())
            if self.on_exit:
                self.on_exit(code)


def find_ffmpeg_from_path_hint(path_hint: str) -> str:
    p = str(path_hint or "").strip()
    if not p:
        return "ffmpeg"
    if Path(p).exists():
        return p
    if p.lower().endswith(".exe") and Path(p).exists():
        return p
    if not p.lower().endswith(".exe") and "\\" in p:
        pe = p + ".exe"
        if Path(pe).exists():
            return pe
    return p
