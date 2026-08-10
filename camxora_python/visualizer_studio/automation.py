from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Automation:
    source: str
    target: str
    multiplier: float = 1.0
    offset: float = 0.0
    smoothing: float = 0.0
    clamp_min: float | None = None
    clamp_max: float | None = None


def apply_automations(state: dict, audio: dict, autos: list[Automation]) -> dict:
    out = dict(state)
    for a in autos:
        v = float(audio.get(a.source, 0.0)) * float(a.multiplier) + float(a.offset)
        if a.clamp_min is not None:
            v = max(float(a.clamp_min), v)
        if a.clamp_max is not None:
            v = min(float(a.clamp_max), v)

        key = a.target
        prev = out.get(key)
        if prev is None:
            out[key] = v
        else:
            s = float(a.smoothing)
            s = max(0.0, min(0.99, s))
            out[key] = float(prev) * s + v * (1.0 - s)
    return out

