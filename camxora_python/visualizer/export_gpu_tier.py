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


def resolve_pipeline_export_workers(requested: object, *, default: int = 1) -> int:
    """Clamp Preferences workers; force 1 on low-VRAM GPUs and frozen installers.

    Packaged builds re-exec ``Camxora.exe --visualizer`` per parallel job. Several
    cold PyInstaller + ``librosa.load`` processes at once commonly freeze on
    ``Loading audio…``. Keep installer exports serial (warm daemon allowed).
    """
    try:
        limit = max(1, min(10, int(requested)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        limit = max(1, min(10, int(default)))
    try:
        from shared.lib.runtime_paths import is_frozen_runtime

        if is_frozen_runtime():
            return 1
    except Exception:
        pass
    try:
        if detect_export_gpu_tier() == "low":
            return 1
    except Exception:
        pass
    return limit

def _probe_nvidia_smi() -> tuple[str | None, float | None]:
    try:
        completed = subprocess.run(
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
