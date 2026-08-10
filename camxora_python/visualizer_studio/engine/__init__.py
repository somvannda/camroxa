"""Composition Engine V1 — engine package (pass order)."""

from __future__ import annotations

# Frame pass order for E1 (P7+ post/lighting expand later).
PASS_ORDER: tuple[str, ...] = (
    "background",
    "particles",
    "spectrum",
    "logo",
    "overlay",
    "text",
    "lighting",  # stub
    "camera",  # stub
    "post",  # stub
)

__all__ = ("PASS_ORDER",)
