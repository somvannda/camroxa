"""Deep-merge helper for template patches."""

from __future__ import annotations

from typing import Any


def is_record(value: Any) -> bool:
    return isinstance(value, dict)


def merge_records(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    next_value: dict[str, Any] = dict(base)
    for key, value in patch.items():
        existing = next_value.get(key)
        if is_record(existing) and is_record(value):
            next_value[key] = merge_records(existing, value)
        else:
            next_value[key] = value
    return next_value
