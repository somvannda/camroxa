"""Warm visualizer subprocess — reads JSON jobs from stdin."""

from __future__ import annotations

import json
import os
import sys
import traceback


def _send(payload: dict) -> None:
    print("MG_EVENT " + json.dumps(payload, ensure_ascii=False), flush=True)


def run_daemon_loop() -> int:
    _send({"status": "daemon_ready", "message": "Visualizer daemon ready"})
    for raw in sys.stdin:
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            _send({"status": "failed", "message": f"Invalid daemon job JSON: {line[:120]}"})
            continue
        msg_type = str(message.get("type") or "").strip().lower()
        if msg_type == "shutdown":
            break
        if msg_type != "job":
            continue
        job_id = str(message.get("jobId") or "")
        argv = message.get("argv")
        if not isinstance(argv, list) or not argv:
            _send({"status": "job_done", "jobId": job_id, "exitCode": 1})
            continue
        code = 1
        prior_daemon_flag = os.environ.get("CAMXORA_DAEMON_JOB")
        prior_cancel_path = os.environ.get("CAMXORA_EXPORT_CANCEL_PATH")
        os.environ["CAMXORA_DAEMON_JOB"] = "1"
        cancel_path = str(message.get("cancelPath") or "").strip()
        if cancel_path:
            os.environ["CAMXORA_EXPORT_CANCEL_PATH"] = cancel_path
        else:
            os.environ.pop("CAMXORA_EXPORT_CANCEL_PATH", None)
        try:
            from visualizer_video.main import normalize_visualizer_job_argv, run_visualizer_argv

            code = int(run_visualizer_argv(normalize_visualizer_job_argv([str(part) for part in argv])))
        except Exception as exc:
            _send(
                {
                    "status": "failed",
                    "message": f"{exc}\n{traceback.format_exc()}",
                    "progress": 0.0,
                }
            )
            code = 1
        finally:
            if prior_daemon_flag is None:
                os.environ.pop("CAMXORA_DAEMON_JOB", None)
            else:
                os.environ["CAMXORA_DAEMON_JOB"] = prior_daemon_flag
            if prior_cancel_path is None:
                os.environ.pop("CAMXORA_EXPORT_CANCEL_PATH", None)
            else:
                os.environ["CAMXORA_EXPORT_CANCEL_PATH"] = prior_cancel_path
        _send({"status": "job_done", "jobId": job_id, "exitCode": code})
    return 0


def main() -> int:
    return run_daemon_loop()


if __name__ == "__main__":
    raise SystemExit(main())
