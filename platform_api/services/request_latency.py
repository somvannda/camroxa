"""In-process latency samples for basic ops metrics (per uvicorn worker)."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import Any

_LOCK = threading.Lock()
_MAX_SAMPLES = 512
_SAMPLES: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_MAX_SAMPLES))


def record_latency_ms(path_key: str, elapsed_ms: float) -> None:
    key = (path_key or "").strip() or "unknown"
    with _LOCK:
        _SAMPLES[key].append(float(elapsed_ms))


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def latency_summary(path_key: str) -> dict[str, Any]:
    key = (path_key or "").strip() or "unknown"
    with _LOCK:
        values = list(_SAMPLES.get(key) or ())
    if not values:
        return {
            "path": key,
            "samples": 0,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    ordered = sorted(values)
    return {
        "path": key,
        "samples": len(ordered),
        "p50_ms": round(float(_percentile(ordered, 50) or 0.0), 1),
        "p95_ms": round(float(_percentile(ordered, 95) or 0.0), 1),
        "max_ms": round(ordered[-1], 1),
    }
