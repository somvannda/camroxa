"""Collect and report desktop video export telemetry."""

from __future__ import annotations

import platform
import threading
from typing import Any


def collect_hardware_hints(*, codec: str | None = None) -> dict[str, str]:
    cpu = platform.processor() or platform.machine() or "unknown"
    encoder = ""
    gpu = ""
    codec_l = str(codec or "").lower()
    if "nvenc" in codec_l:
        encoder = "nvenc"
        gpu = "NVIDIA (NVENC)"
    elif "qsv" in codec_l:
        encoder = "qsv"
        gpu = "Intel (QSV)"
    elif "amf" in codec_l:
        encoder = "amf"
        gpu = "AMD (AMF)"
    elif codec_l:
        encoder = "cpu"
        gpu = "CPU encode"
    return {
        "hw_cpu": cpu[:255],
        "hw_gpu": gpu[:255],
        "hw_encoder": encoder[:64],
    }


def report_video_telemetry_async(api: Any, payload: dict[str, Any]) -> None:
    """Fire-and-forget POST so export UI never blocks on telemetry."""

    def _run() -> None:
        try:
            api.report_local_video_telemetry(payload)
        except Exception:
            pass

    threading.Thread(target=_run, name="video-export-telemetry", daemon=True).start()
