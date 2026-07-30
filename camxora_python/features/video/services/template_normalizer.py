"""Electron template → GPU renderer dict bridge — Phase 9d."""

from __future__ import annotations

from typing import Any

from features.video.lib.merge_records import merge_records
from features.video.lib.text_domain_runtime import inject_text_domains_into_template
from features.video.lib.video_template_save import build_video_workspace_template_save_patch


def _apply_renderer_audio_aliases(merged: dict[str, Any]) -> None:
    audio = merged.get("audioSettings")
    if not isinstance(audio, dict):
        return
    input_gain = audio.get("inputGain")
    sensitivity = audio.get("sensitivity")
    if input_gain is not None:
        audio["sensitivity"] = input_gain
    elif sensitivity is not None:
        audio["inputGain"] = sensitivity
    if audio.get("motionSmoothing") is not None:
        try:
            audio["smoothing"] = float(max(0.0, min(0.99, float(audio.get("motionSmoothing")))))
        except (TypeError, ValueError):
            audio["smoothing"] = float(audio.get("smoothing", 0.8) or 0.8)


class TemplateNormalizer:
    def to_renderer_dict(
        self,
        *,
        base: dict[str, Any],
        draft: dict[str, Any],
        layers: list[dict[str, Any]],
        workspace: dict[str, Any],
        track_paths: list[str] | None = None,
        pipeline_album: str = "",
        active_track_path: str | None = None,
        lightning_layers: list[dict[str, Any]] | None = None,
        spectrum_instances: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        template_name = str(base.get("templateName") or "").strip()
        patch = build_video_workspace_template_save_patch(
            template=base,
            draft=draft,
            template_name=template_name,
            layers=layers,
            lightning_layers=lightning_layers,
            spectrum_instances=spectrum_instances,
        )
        merged = merge_records(base, patch)
        if merged.get("templateName") == "":
            merged.pop("templateName", None)

        logo_path = str(workspace.get("logoPath") or "").strip()
        if logo_path:
            merged["logoPath"] = logo_path
            merged["previewLogo"] = logo_path

        _apply_renderer_audio_aliases(merged)
        paths = track_paths
        if paths is None:
            raw = workspace.get("trackPaths")
            paths = [str(item) for item in raw] if isinstance(raw, list) else []
        album = str(pipeline_album or workspace.get("pipelineAlbum") or "").strip()
        active = str(
            active_track_path
            or workspace.get("selectedMp3Path")
            or workspace.get("activeTrackPath")
            or ""
        ).strip()
        return inject_text_domains_into_template(
            merged,
            track_paths=paths,
            pipeline_album=album,
            active_track_path=active or None,
        )
