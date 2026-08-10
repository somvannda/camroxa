"""Long-lived visualizer worker — amortizes Python/PyInstaller import cost."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from shared.lib.runtime_paths import is_frozen_runtime
from shared.lib.subprocess_utils import popen_hidden

log = logging.getLogger(__name__)

ExportEventHandler = Callable[[dict], None]
ExportExitHandler = Callable[[int], None]


def _visualizer_daemon_enabled() -> bool:
    return os.environ.get("CAMXORA_USE_VISUALIZER_DAEMON", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    """Kill daemon + child ffmpeg (Windows needs /T; terminate alone leaves orphans)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            from shared.lib.subprocess_utils import run_hidden

            run_hidden(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=15,
            )
            return
        except Exception as exc:
            log.debug("taskkill failed: %s", exc)
    try:
        proc.terminate()
    except OSError:
        pass
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


class VisualizerDaemonClient:
    """Process-global warm visualizer subprocess (one job at a time)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job_lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._project_dir = ""
        self._disabled = False
        self._cancel_requested = False

    def cancel_active(self, *, cancel_path: str | None = None) -> None:
        """Force-stop the in-flight daemon job (and ffmpeg children).

        Soft-cancel via flag file first (render loop checks it between frames),
        then hard-kill the process tree if the job does not exit quickly.
        """
        self._cancel_requested = True
        if cancel_path:
            from features.video.lib.export_cancel import request_export_cancel

            request_export_cancel(cancel_path)
            # Give the render loop a brief window to exit cleanly.
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                with self._lock:
                    proc = self._proc
                if proc is None or proc.poll() is not None:
                    with self._lock:
                        self._proc = None
                    return
                time.sleep(0.1)
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None:
            return
        _terminate_process_tree(proc)

    def shutdown(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.write(json.dumps({"type": "shutdown"}) + "\n")
                proc.stdin.flush()
        except OSError:
            pass
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(proc)

    def run_command(
        self,
        cmd: list[str],
        *,
        cwd: str,
        env: dict[str, str],
        on_event: ExportEventHandler | None,
        on_exit: ExportExitHandler | None,
    ) -> int | None:
        """Run via daemon when available. Returns None if caller should fall back.

        The warm daemon accepts only one job at a time — callers that need
        parallel exports must skip the daemon and use one-shot subprocesses.
        """
        if not _visualizer_daemon_enabled() or self._disabled:
            return None
        # Serialize the full job so concurrent callers cannot interleave stdin/stdout.
        with self._job_lock:
            return self._run_command_locked(
                cmd,
                cwd=cwd,
                env=env,
                on_event=on_event,
                on_exit=on_exit,
            )

    def _run_command_locked(
        self,
        cmd: list[str],
        *,
        cwd: str,
        env: dict[str, str],
        on_event: ExportEventHandler | None,
        on_exit: ExportExitHandler | None,
    ) -> int | None:
        self._cancel_requested = False
        job_id = uuid.uuid4().hex
        with self._lock:
            if not self._ensure_process(cmd, cwd, env):
                return None
            proc = self._proc
        assert proc is not None and proc.stdout is not None
        try:
            assert proc.stdin is not None
            proc.stdin.write(
                json.dumps(
                    {
                        "type": "job",
                        "jobId": job_id,
                        "argv": cmd,
                        "cancelPath": str(env.get("CAMXORA_EXPORT_CANCEL_PATH") or ""),
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
        except OSError as exc:
            log.warning("visualizer daemon write failed: %s", exc)
            self._reset_process()
            return None

        exit_code = 1
        job_done = False
        try:
            for line in proc.stdout:
                if self._cancel_requested:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("MG_EVENT "):
                    payload_raw = stripped[len("MG_EVENT ") :].strip()
                    try:
                        event = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        event = {"status": "log", "message": payload_raw}
                    status = str(event.get("status") or "").strip().lower()
                    if status == "job_done" and str(event.get("jobId") or "") == job_id:
                        try:
                            exit_code = int(event.get("exitCode", 1))
                        except (TypeError, ValueError):
                            exit_code = 1
                        job_done = True
                        break
                    if on_event:
                        on_event(event)
                elif on_event:
                    on_event({"status": "log", "message": stripped})
        except Exception as exc:
            if self._cancel_requested:
                log.info("visualizer daemon cancelled: %s", exc)
            else:
                log.warning("visualizer daemon read failed: %s", exc)
            self._reset_process()
            if self._cancel_requested:
                if on_exit:
                    on_exit(1)
                return 1
            return None

        if self._cancel_requested:
            self._reset_process()
            if on_exit:
                on_exit(1)
            return 1

        if proc.poll() is not None:
            self._reset_process()
        if on_exit:
            on_exit(exit_code)
        if not job_done:
            # Process died mid-job without job_done — do not silently re-run as subprocess.
            self._reset_process()
            return 1
        if exit_code != 0:
            self._reset_process()
            return None
        return exit_code

    def _ensure_process(self, cmd: list[str], cwd: str, env: dict[str, str]) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True
        self._proc = None
        project_dir = str(Path(cwd).resolve())
        self._project_dir = project_dir
        if is_frozen_runtime():
            daemon_cmd = [cmd[0], "--visualizer-daemon"]
        else:
            daemon_cmd = [sys.executable, "-m", "visualizer_video.daemon"]
        try:
            proc = popen_hidden(
                daemon_cmd,
                cwd=project_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
        except OSError as exc:
            log.warning("visualizer daemon start failed: %s", exc)
            self._disabled = True
            return False
        assert proc.stdout is not None
        deadline = time.monotonic() + 15.0
        ready = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            stripped = line.strip()
            if stripped.startswith("MG_EVENT "):
                try:
                    event = json.loads(stripped[len("MG_EVENT ") :].strip())
                except json.JSONDecodeError:
                    continue
                if str(event.get("status") or "").lower() == "daemon_ready":
                    ready = True
                    break
        if not ready:
            log.warning("visualizer daemon did not become ready")
            try:
                proc.terminate()
            except OSError:
                pass
            self._disabled = True
            return False
        self._proc = proc
        log.info("visualizer daemon ready")
        return True

    def _reset_process(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is not None and proc.poll() is None:
            _terminate_process_tree(proc)


_client: VisualizerDaemonClient | None = None
_client_lock = threading.Lock()


def get_visualizer_daemon() -> VisualizerDaemonClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = VisualizerDaemonClient()
        return _client


def shutdown_visualizer_daemon() -> None:
    global _client
    with _client_lock:
        client = _client
        _client = None
    if client is not None:
        client.shutdown()
