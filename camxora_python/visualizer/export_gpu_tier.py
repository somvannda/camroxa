"""Classify the local NVIDIA GPU for export quality/throughput tradeoffs.

Target reference GPU is GTX 1050 Ti (4 GB Pascal NVENC). High-end cards
(e.g. RTX 3060) stay on normal caps; ``low`` tier tightens Draft/Fast/Balanced
export work without changing Master/quality visuals.
"""

from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from typing import Literal

GpuTier = Literal["low", "mid", "high"]

_LOW_NAME_HINTS = (
    "1050",
    "1030",
    "1010",
    "940",
    "930",
    "920",
    "910",
    "mx150",
    "mx250",
    "mx350",
    "mx450",
    "quadro p600",
    "quadro p620",
    "quadro p1000",
)

_HIGH_NAME_HINTS = (
    "4090",
    "4080",
    "4070",
    "4060",
    "3090",
    "3080",
    "3070",
    "3060",
    "a6000",
    "a5000",
    "a4000",
    "titan",
)


def clear_export_gpu_tier_cache() -> None:
    """Reset cached detection (tests / forced re-probe)."""
    detect_export_gpu_tier.cache_clear()


@lru_cache(maxsize=1)
def detect_export_gpu_tier() -> GpuTier:
    """Return ``low`` | ``mid`` | ``high``.

    Override with ``CAMXORA_GPU_TIER=low|mid|high``. Detection uses
    ``nvidia-smi`` name + total VRAM when available; unknown → ``mid``.
    """
    override = str(os.environ.get("CAMXORA_GPU_TIER") or "").strip().lower()
    if override in {"low", "mid", "high"}:
        return override  # type: ignore[return-value]

    name, memory_mib = _probe_nvidia_smi()
    return classify_export_gpu_tier(name=name, memory_mib=memory_mib)


def classify_export_gpu_tier(*, name: str | None = None, memory_mib: float | None = None) -> GpuTier:
    """Pure classification from GPU name and optional VRAM MiB."""
    label = str(name or "").strip().lower()
    mem = float(memory_mib) if memory_mib is not None else None

    if any(hint in label for hint in _LOW_NAME_HINTS):
        return "low"
    if mem is not None and mem > 0 and mem < 6144:
        return "low"

    if any(hint in label for hint in _HIGH_NAME_HINTS):
        return "high"
    if mem is not None and mem >= 10240:
        return "high"

    return "mid"


# Quality / Best Quality are GPU-heavy (RGBA + glow). Cap parallel exporters by
# detected tier; the UI still asks before going above 1 worker.
_QUALITY_WORKER_CAPS: dict[GpuTier, int] = {
    "low": 1,
    "mid": 3,
    "high": 5,
}


def normalize_export_gpu_speed_mode(speed_mode: object = None) -> str:
    mode = str(speed_mode or "").strip().lower()
    if mode in {"master", "best"}:
        return "best_quality"
    return mode


def is_quality_export_speed(speed_mode: object = None) -> bool:
    return normalize_export_gpu_speed_mode(speed_mode) in {"best_quality", "quality"}


def quality_export_worker_cap(*, tier: GpuTier | None = None) -> int:
    """Max parallel workers allowed for Quality / Best Quality on this GPU."""
    resolved: GpuTier = tier or "mid"
    if tier is None:
        try:
            resolved = detect_export_gpu_tier()
        except Exception:
            resolved = "mid"
    return int(_QUALITY_WORKER_CAPS.get(resolved, 3))


def resolve_pipeline_export_workers(
    requested: object,
    *,
    default: int = 1,
    speed_mode: object = None,
    width: int | None = None,
    height: int | None = None,
) -> int:
    """Clamp Preferences workers for GPU safety.

    - Low-VRAM GPUs: force 1
    - Quality / Best Quality: tier cap (low=1, mid=3, high=5)
    - QHD/4K with non-quality speeds: max 2
    """
    try:
        limit = max(1, min(10, int(requested)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        limit = max(1, min(10, int(default)))
    try:
        if detect_export_gpu_tier() == "low":
            return 1
    except Exception:
        pass

    mode = normalize_export_gpu_speed_mode(speed_mode)
    if is_quality_export_speed(mode):
        return min(limit, quality_export_worker_cap())

    pixels = 0
    if width is not None and height is not None:
        try:
            pixels = max(0, int(width)) * max(0, int(height))
        except (TypeError, ValueError):
            pixels = 0
    if pixels >= 2560 * 1440:
        return min(limit, 2)
    return limit

def _probe_nvidia_smi() -> tuple[str | None, float | None]:
    try:
        from shared.lib.subprocess_utils import run_hidden

        completed = run_hidden(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None, None

    if completed.returncode != 0:
        return None, None
    raw = (completed.stdout or "").strip().splitlines()
    if not raw:
        return None, None

    first = raw[0]
    parts = [part.strip() for part in first.split(",")]
    name = parts[0] if parts else first
    memory_mib: float | None = None
    if len(parts) > 1:
        match = re.search(r"[\d.]+", parts[1])
        if match:
            try:
                memory_mib = float(match.group(0))
            except ValueError:
                memory_mib = None
    return name or None, memory_mib
