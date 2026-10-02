"""Canonical preview vs export renderer-template parity (JSON gate)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

PARITY_FOCUS_KEYS: tuple[str, ...] = (
    "spectrumEnabled",
    "spectrumInstances",
    "layers",
    "style",
    "position",
    "audioSettings",
    "previewBindings",
    "lightningEnabled",
    "lightningLayers",
    "particlesSettings",
    "logoSettings",
    "backgroundSettings",
    "effects",
    "albumText",
    "titleText",
)


@dataclass(frozen=True)
class PreviewExportParityReport:
    equal: bool
    missing_in_export: list[str] = field(default_factory=list)
    missing_in_preview: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def summary(self, *, limit: int = 8) -> str:
        if self.equal:
            return "Preview and export templates match."
        parts: list[str] = []
        if self.missing_in_export:
            sample = ", ".join(self.missing_in_export[:limit])
            more = len(self.missing_in_export) - limit
            parts.append(f"missing in export: {sample}" + (f" (+{more})" if more > 0 else ""))
        if self.missing_in_preview:
            sample = ", ".join(self.missing_in_preview[:limit])
            more = len(self.missing_in_preview) - limit
            parts.append(f"missing in preview: {sample}" + (f" (+{more})" if more > 0 else ""))
        if self.changed:
            sample = ", ".join(self.changed[:limit])
            more = len(self.changed) - limit
            parts.append(f"changed: {sample}" + (f" (+{more})" if more > 0 else ""))
        return "; ".join(parts) or "Preview and export templates differ."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonicalize_renderer_template(template: dict | None) -> dict[str, Any]:
    """Normalize a renderer template the same way preview + export load paths do."""
    try:
        from visualizer_video.template_runtime import normalize_renderer_template

        return normalize_renderer_template(template if isinstance(template, dict) else {})
    except Exception:
        return dict(template) if isinstance(template, dict) else {}


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _focus_slice(template: dict[str, Any]) -> dict[str, Any]:
    return {key: template.get(key) for key in PARITY_FOCUS_KEYS}


def _walk_diff(
    preview: Any,
    export: Any,
    *,
    path: str,
    missing_in_export: list[str],
    missing_in_preview: list[str],
    changed: list[str],
) -> None:
    if type(preview) is not type(export) and not (
        isinstance(preview, (int, float)) and isinstance(export, (int, float))
    ):
        if preview is None and export is not None:
            missing_in_preview.append(path or "<root>")
            return
        if export is None and preview is not None:
            missing_in_export.append(path or "<root>")
            return
        changed.append(path or "<root>")
        return

    if isinstance(preview, dict) and isinstance(export, dict):
        preview_keys = set(preview.keys())
        export_keys = set(export.keys())
        for key in sorted(preview_keys - export_keys):
            missing_in_export.append(f"{path}.{key}" if path else str(key))
        for key in sorted(export_keys - preview_keys):
            missing_in_preview.append(f"{path}.{key}" if path else str(key))
        for key in sorted(preview_keys & export_keys):
            child = f"{path}.{key}" if path else str(key)
            _walk_diff(
                preview.get(key),
                export.get(key),
                path=child,
                missing_in_export=missing_in_export,
                missing_in_preview=missing_in_preview,
                changed=changed,
            )
        return

    if isinstance(preview, list) and isinstance(export, list):
        if len(preview) != len(export):
            changed.append(f"{path}.length" if path else "length")
        for index, (left, right) in enumerate(zip(preview, export)):
            child = f"{path}[{index}]" if path else f"[{index}]"
            _walk_diff(
                left,
                right,
                path=child,
                missing_in_export=missing_in_export,
                missing_in_preview=missing_in_preview,
                changed=changed,
            )
        if len(preview) > len(export):
            for index in range(len(export), len(preview)):
                missing_in_export.append(f"{path}[{index}]" if path else f"[{index}]")
        elif len(export) > len(preview):
            for index in range(len(preview), len(export)):
                missing_in_preview.append(f"{path}[{index}]" if path else f"[{index}]")
        return

    if isinstance(preview, float) and isinstance(export, float):
        if abs(preview - export) > 1e-6:
            changed.append(path or "<root>")
        return
    if isinstance(preview, (int, float)) and isinstance(export, (int, float)):
        if float(preview) != float(export):
            changed.append(path or "<root>")
        return

    if preview != export:
        changed.append(path or "<root>")


def diff_renderer_templates(
    preview: dict | None,
    export: dict | None,
    *,
    focus_only: bool = True,
) -> PreviewExportParityReport:
    """Compare canonical preview vs export templates; optionally focus on visual keys."""
    preview_canon = canonicalize_renderer_template(preview)
    export_canon = canonicalize_renderer_template(export)
    left = _focus_slice(preview_canon) if focus_only else preview_canon
    right = _focus_slice(export_canon) if focus_only else export_canon

    if _json_dump(left) == _json_dump(right):
        return PreviewExportParityReport(equal=True)

    missing_in_export: list[str] = []
    missing_in_preview: list[str] = []
    changed: list[str] = []
    _walk_diff(
        left,
        right,
        path="",
        missing_in_export=missing_in_export,
        missing_in_preview=missing_in_preview,
        changed=changed,
    )
    return PreviewExportParityReport(
        equal=False,
        missing_in_export=missing_in_export,
        missing_in_preview=missing_in_preview,
        changed=changed,
    )


def templates_match(preview: dict | None, export: dict | None) -> bool:
    return diff_renderer_templates(preview, export).equal
