"""Local video template + workspace persistence — mirrors Electron main process."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from features.video.lib.merge_records import merge_records
from features.video.lib.render_scene_request import normalize_export_fps
from shared.lib.app_paths import (
    get_user_video_templates_path,
    get_video_draft_store_dir,
    get_video_workspace_prefs_path,
)
from shared.models.desktop import (
    Mp3ListItem,
    PreviewAspectRatio,
    VideoExportState,
    VideoPlaybackState,
    VideoTemplateSummary,
    VideoWorkspaceState,
    VideoWorkspaceUiState,
)
from shared.services.file_service import list_directory_entries
from shared.services.video_workspace_service import get_video_workspace_service


def _asset_paths_from_template(template_payload: dict[str, Any]) -> tuple[str, str]:
    logo_path = str(
        template_payload.get("logoPath") or template_payload.get("previewLogo") or ""
    ).strip()
    background_path = str(template_payload.get("previewBackground") or "").strip()
    return logo_path, background_path


def _apply_template_asset_prefs(prefs: dict[str, Any], template_payload: dict[str, Any]) -> None:
    """Keep workspace asset prefs aligned with the active template's saved paths."""
    logo_path, background_path = _asset_paths_from_template(template_payload)
    if logo_path:
        prefs["logoPath"] = logo_path
    else:
        prefs.pop("logoPath", None)
    if background_path:
        prefs["backgroundPath"] = background_path
    else:
        prefs.pop("backgroundPath", None)


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _export_fps_from_settings(settings: dict[str, Any]) -> int:
    return normalize_export_fps(settings.get("videoExportFps", 24))


def _parse_resolution(resolution: str) -> PreviewAspectRatio:
    match = re.match(r"^(\d+)\s*x\s*(\d+)$", str(resolution or "").strip(), re.IGNORECASE)
    if not match:
        return PreviewAspectRatio(width=1920, height=1080)
    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        return PreviewAspectRatio(width=1920, height=1080)
    return PreviewAspectRatio(width=width, height=height)


def _mp3_track_key(name: str) -> tuple[int, int, str] | tuple[int, str]:
    """python_app track ordering: numeric prefix first, then case-insensitive name."""
    match = re.match(r"\s*(\d+)", name)
    if match:
        return (0, int(match.group(1)), name.lower())
    return (1, name.lower())


def _apply_saved_track_order(items: list[Mp3ListItem], order: list[str]) -> list[Mp3ListItem]:
    """User drag order first; tracks not in the saved order keep default sort."""
    by_path = {item.path: item for item in items}
    ordered = [by_path.pop(path) for path in order if path in by_path]
    return ordered + list(by_path.values())


class VideoLocalStore:
    """Read/write local video templates and workspace preferences."""

    def read_templates(self) -> list[dict[str, Any]]:
        """Return templates the user created or installed (marketplace).

        Factory/sample catalogs are intentionally not loaded — a fresh install
        starts empty until the user clicks New or installs from Marketplace.
        """
        user_raw = _read_json(get_user_video_templates_path())
        if not isinstance(user_raw, list):
            return []
        return [item for item in user_raw if isinstance(item, dict) and str(item.get("id") or "").strip()]

    def write_templates(self, templates: list[dict[str, Any]]) -> None:
        _write_json(get_user_video_templates_path(), templates)

    def _read_user_templates(self) -> list[dict[str, Any]]:
        user_raw = _read_json(get_user_video_templates_path())
        if not isinstance(user_raw, list):
            return []
        return [item for item in user_raw if isinstance(item, dict)]

    def get_by_marketplace_item_id(self, marketplace_item_id: str) -> dict[str, Any] | None:
        """Return the user-catalog record installed from a marketplace item, if any."""
        item_id = str(marketplace_item_id or "").strip()
        if not item_id:
            return None
        for item in self._read_user_templates():
            if str(item.get("marketplace_item_id") or "").strip() != item_id:
                continue
            if str(item.get("source") or "").strip().lower() != "marketplace":
                continue
            return item
        return None

    def insert_marketplace_template(
        self,
        *,
        template_id: str,
        name: str,
        template_json: dict[str, Any],
        kind: str,
        marketplace_item_id: str,
        user_id: str = "",
    ) -> dict[str, Any]:
        """Append a marketplace-installed template to the user catalog."""
        uid = str(template_id or "").strip()
        if not uid:
            raise ValueError("template_id is required")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        payload = dict(template_json) if isinstance(template_json, dict) else {}
        if name and not str(payload.get("templateName") or "").strip():
            payload["templateName"] = name
        record = {
            "id": uid,
            "name": name or "Untitled",
            "source": "marketplace",
            "template": payload,
            "originalTemplate": copy.deepcopy(payload),
            "kind": kind or "video",
            "user_id": user_id,
            "marketplace_item_id": str(marketplace_item_id or "").strip(),
            "updated_at": now,
        }
        templates = self._read_user_templates()
        templates.append(record)
        self.write_templates(templates)
        return record

    def create_blank_template(
        self,
        *,
        name: str = "Untitled Template",
        settings: dict[str, Any] | None = None,
    ) -> VideoWorkspaceState:
        """Create a user composition from scratch and select it."""
        from uuid import uuid4

        from features.video.lib.composition_draft import new_blank_composition_template

        display_name = str(name or "").strip() or "New Composition"
        uid = str(uuid4())
        payload = new_blank_composition_template(name=display_name)
        payload["backgroundEnabled"] = True
        payload["logoEnabled"] = True
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        record = {
            "id": uid,
            "name": display_name,
            "source": "user",
            "template": payload,
            "originalTemplate": copy.deepcopy(payload),
            "updated_at": now,
        }
        templates = self._read_user_templates()
        templates.append(record)
        self.write_templates(templates)
        prefs = self.read_prefs()
        prefs["templateId"] = uid
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def update_marketplace_template(
        self,
        *,
        template_id: str,
        name: str,
        template_json: dict[str, Any],
        kind: str,
    ) -> dict[str, Any] | None:
        """Update an existing marketplace-installed template by local id."""
        uid = str(template_id or "").strip()
        if not uid:
            return None
        templates = self._read_user_templates()
        index = next(
            (idx for idx, item in enumerate(templates) if str(item.get("id") or "").strip() == uid),
            -1,
        )
        if index < 0:
            return None
        existing = templates[index]
        payload = dict(template_json) if isinstance(template_json, dict) else {}
        if name and not str(payload.get("templateName") or "").strip():
            payload["templateName"] = name
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        original = existing.get("originalTemplate")
        if not isinstance(original, dict):
            original = copy.deepcopy(payload)
        record = {
            **existing,
            "name": name or str(existing.get("name") or "Untitled"),
            "source": "marketplace",
            "template": payload,
            "originalTemplate": copy.deepcopy(original),
            "kind": kind or str(existing.get("kind") or "video"),
            "updated_at": now,
        }
        templates[index] = record
        self.write_templates(templates)
        return record

    def read_prefs(self) -> dict[str, Any]:
        raw = _read_json(get_video_workspace_prefs_path())
        return dict(raw) if isinstance(raw, dict) else {}

    def write_prefs(self, prefs: dict[str, Any]) -> None:
        _write_json(get_video_workspace_prefs_path(), prefs)
        from shared.services.workspace_prefs_push import schedule_workspace_prefs_push

        schedule_workspace_prefs_push()

    def read_workspace_state(self, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        settings = settings or {}
        templates = self.read_templates()
        prefs = self.read_prefs()
        export_registry = get_video_workspace_service().get_workspace_state()
        export_state = export_registry.export if export_registry else VideoExportState()

        output_resolution = (
            str(prefs.get("outputResolution") or settings.get("outputResolution") or "1920x1080").strip()
            or "1920x1080"
        )
        aspect = _parse_resolution(output_resolution)
        workers_raw = settings.get("videoExportWorkers", settings.get("perfExportWorkers", 1))
        try:
            workers = max(1, int(workers_raw))
        except (TypeError, ValueError):
            workers = 1

        if not templates:
            return VideoWorkspaceState(
                template={},
                template_id=None,
                template_name="No template loaded",
                templates=[],
                output_resolution=output_resolution,
                preview_aspect_ratio=aspect,
                export=VideoExportState(
                    workers=workers,
                    fps=_export_fps_from_settings(settings),
                    auto_merge=bool(settings.get("autoMergeAfterVideo", False)),
                    shuffle_merge=bool(settings.get("videoShuffleMerge", False)),
                    current_status="No local templates available yet.",
                ),
                ui=VideoWorkspaceUiState(
                    preview_title="Preview",
                    notes=[
                        "No video templates yet.",
                        "Click New to create a blank template, then pick Background, Logo, and an MP3.",
                    ],
                ),
            )

        template_id = str(prefs.get("templateId") or settings.get("videoRenderTemplatePath") or "").strip() or None
        selected = next((item for item in templates if item.get("id") == template_id), None)
        if selected is None:
            selected = templates[0]
            template_id = str(selected.get("id") or "").strip() or None

        template_payload = selected.get("template") if isinstance(selected.get("template"), dict) else {}
        template_name = (
            str(template_payload.get("templateName") or selected.get("name") or "Untitled Template").strip()
            or "Untitled Template"
        )
        background_path = str(
            prefs.get("backgroundPath")
            or settings.get("videoRenderBackgroundPath")
            or template_payload.get("previewBackground")
            or ""
        ).strip()
        logo_path = str(
            prefs.get("logoPath") or settings.get("videoRenderLogoPath") or template_payload.get("logoPath") or ""
        ).strip()
        preferred_mp3 = str(prefs.get("selectedMp3Path") or "").strip()
        mp3_directory = str(prefs.get("mp3Directory") or "").strip()
        if not mp3_directory and preferred_mp3:
            mp3_directory = str(Path(preferred_mp3).parent)
        mp3_list = self.list_mp3_files(mp3_directory) if mp3_directory else []
        saved_order = prefs.get("mp3Order")
        if isinstance(saved_order, list) and saved_order:
            mp3_list = _apply_saved_track_order(mp3_list, [str(path) for path in saved_order])
        list_paths = [item.path for item in mp3_list]
        selected_mp3 = preferred_mp3 if preferred_mp3 in list_paths else (list_paths[0] if list_paths else preferred_mp3)

        summaries = [
            VideoTemplateSummary(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or "Untitled Template"),
                kind=str(item.get("source")) if item.get("source") else None,
                updated_at=str(item.get("updated_at") or "") or None,
            )
            for item in templates
            if item.get("id")
        ]

        return VideoWorkspaceState(
            template=dict(template_payload),
            template_id=template_id,
            template_name=template_name,
            templates=summaries,
            output_resolution=output_resolution,
            preview_aspect_ratio=aspect,
            background_path=background_path,
            logo_path=logo_path,
            selected_mp3_path=selected_mp3,
            mp3_directory=mp3_directory,
            mp3_list=mp3_list,
            playback=VideoPlaybackState(),
            export=export_state if export_state.running else VideoExportState(
                workers=workers,
                fps=_export_fps_from_settings(settings),
                auto_merge=bool(settings.get("autoMergeAfterVideo", False)),
                shuffle_merge=bool(settings.get("videoShuffleMerge", False)),
                current_status=export_state.current_status or "Ready",
                output_dir=str(settings.get("videoRenderOutputDir") or "").strip() or None,
            ),
            ui=VideoWorkspaceUiState(
                preview_title=f"Preview: {template_name}",
                notes=[
                    "Local template editor with GPU preview and manual export.",
                ],
            ),
        )

    def set_template(self, template_id: str) -> VideoWorkspaceState:
        normalized = str(template_id or "").strip()
        templates = self.read_templates()
        selected = next((item for item in templates if str(item.get("id") or "") == normalized), None)
        if selected is None:
            return self.read_workspace_state()
        template_payload = selected.get("template") if isinstance(selected.get("template"), dict) else {}
        prefs = self.read_prefs()
        prefs["templateId"] = normalized
        _apply_template_asset_prefs(prefs, template_payload)
        self.write_prefs(prefs)
        return self.read_workspace_state()

    def set_logo_path(self, logo_path: str, *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        prefs = self.read_prefs()
        prefs["logoPath"] = str(logo_path or "").strip()
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def set_background_path(self, background_path: str, *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        prefs = self.read_prefs()
        prefs["backgroundPath"] = str(background_path or "").strip()
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def set_output_resolution(self, resolution: str, *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        normalized = str(resolution or "").strip() or "1920x1080"
        prefs = self.read_prefs()
        prefs["outputResolution"] = normalized
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def set_mp3_path(self, mp3_path: str, *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        prefs = self.read_prefs()
        normalized = str(mp3_path or "").strip()
        prefs["selectedMp3Path"] = normalized
        if normalized and Path(normalized).is_file():
            prefs["mp3Directory"] = str(Path(normalized).parent)
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def set_mp3_directory(self, directory: str, *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        """python_app 'Select MP3 Folder': load every track and select the first."""
        normalized = str(directory or "").strip()
        items = self.list_mp3_files(normalized)
        paths = [item.path for item in items]
        prefs = self.read_prefs()
        selected = str(prefs.get("selectedMp3Path") or "").strip()
        if selected not in paths:
            selected = paths[0] if paths else ""
        if str(prefs.get("mp3Directory") or "").strip() != normalized:
            prefs.pop("mp3Order", None)  # Custom order belongs to one folder.
        prefs["mp3Directory"] = normalized
        prefs["selectedMp3Path"] = selected
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def set_mp3_order(self, paths: list[str], *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        """Persist the drag-and-drop track order; export and merge follow it."""
        prefs = self.read_prefs()
        prefs["mp3Order"] = [str(path).strip() for path in paths if str(path).strip()]
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def patch_template(self, patch: dict[str, Any], *, settings: dict[str, Any] | None = None) -> VideoWorkspaceState:
        templates = self.read_templates()
        if not templates:
            return self.read_workspace_state(settings)

        workspace = self.read_workspace_state(settings)
        selected_id = workspace.template_id or (workspace.templates[0].id if workspace.templates else None)
        if not selected_id:
            return workspace

        index = next(
            (idx for idx, item in enumerate(templates) if str(item.get("id") or "") == selected_id),
            -1,
        )
        if index < 0:
            return workspace

        record = templates[index]
        current_template = record.get("template") if isinstance(record.get("template"), dict) else {}
        # Keep the first known snapshot forever so Save/overwrite stays restorable.
        original = record.get("originalTemplate")
        if not isinstance(original, dict):
            original = copy.deepcopy(current_template)
        next_template = merge_records(current_template, patch if isinstance(patch, dict) else {})
        next_name = str(next_template.get("templateName") or record.get("name") or "Untitled Template").strip()
        templates[index] = {
            **record,
            "name": next_name or "Untitled Template",
            "template": next_template,
            "originalTemplate": copy.deepcopy(original),
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        }
        self.write_templates(templates)
        prefs = self.read_prefs()
        if str(prefs.get("templateId") or "").strip() == selected_id:
            _apply_template_asset_prefs(prefs, next_template)
            self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def restore_template_to_original(
        self,
        template_id: str | None = None,
        *,
        settings: dict[str, Any] | None = None,
    ) -> VideoWorkspaceState | None:
        """Replace the saved template payload with the preserved original snapshot."""
        templates = self.read_templates()
        if not templates:
            return None

        workspace = self.read_workspace_state(settings)
        selected_id = str(template_id or workspace.template_id or "").strip()
        if not selected_id and workspace.templates:
            selected_id = workspace.templates[0].id
        if not selected_id:
            return None

        index = next(
            (idx for idx, item in enumerate(templates) if str(item.get("id") or "") == selected_id),
            -1,
        )
        if index < 0:
            return None

        record = templates[index]
        original = record.get("originalTemplate")
        if not isinstance(original, dict):
            current = record.get("template") if isinstance(record.get("template"), dict) else {}
            original = copy.deepcopy(current)
        restored = copy.deepcopy(original)
        next_name = str(restored.get("templateName") or record.get("name") or "Untitled Template").strip()
        templates[index] = {
            **record,
            "name": next_name or "Untitled Template",
            "template": restored,
            "originalTemplate": copy.deepcopy(original),
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        }
        self.write_templates(templates)
        prefs = self.read_prefs()
        prefs["templateId"] = selected_id
        _apply_template_asset_prefs(prefs, restored)
        self.write_prefs(prefs)
        return self.read_workspace_state(settings)

    def delete_template(self, template_id: str) -> VideoWorkspaceState:
        normalized = str(template_id or "").strip()
        templates = self.read_templates()
        if not normalized or not templates:
            return self.read_workspace_state()

        workspace = self.read_workspace_state()
        delete_index = next(
            (idx for idx, item in enumerate(templates) if str(item.get("id") or "") == normalized),
            -1,
        )
        if delete_index < 0:
            return workspace

        user_raw = _read_json(get_user_video_templates_path())
        user_items = [item for item in user_raw if isinstance(item, dict)] if isinstance(user_raw, list) else []
        self.write_templates([item for item in user_items if str(item.get("id") or "").strip() != normalized])

        remaining = self.read_templates()
        prefs = self.read_prefs()
        if workspace.template_id == normalized:
            fallback = remaining[min(delete_index, len(remaining) - 1)] if remaining else None
            if fallback:
                prefs["templateId"] = str(fallback.get("id") or "")
                fallback_template = (
                    fallback.get("template") if isinstance(fallback.get("template"), dict) else {}
                )
                _apply_template_asset_prefs(prefs, fallback_template)
            else:
                prefs.pop("templateId", None)
                prefs.pop("logoPath", None)
                prefs.pop("backgroundPath", None)
            self.write_prefs(prefs)

        draft_path = get_video_draft_store_dir() / f"{normalized}.json"
        if draft_path.is_file():
            draft_path.unlink(missing_ok=True)
        return self.read_workspace_state()

    def list_mp3_files(self, directory: str) -> list[Mp3ListItem]:
        entries = list_directory_entries(directory)
        items: list[Mp3ListItem] = []
        for entry in entries:
            if entry.is_directory:
                continue
            if not entry.name.lower().endswith(".mp3"):
                continue
            path = str(Path(directory) / entry.name)
            items.append(Mp3ListItem(name=entry.name, path=path))
        return sorted(items, key=lambda item: _mp3_track_key(item.name))
