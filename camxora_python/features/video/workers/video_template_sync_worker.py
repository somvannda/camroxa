"""Background worker — sync saved video template to platform_api."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from shared.models.auth import ProfileResponse
from shared.models.desktop import VideoWorkspaceState
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError


def _profile_field(profile: Any, key: str) -> str:
    if isinstance(profile, ProfileResponse):
        return str(getattr(profile, key, "") or "").strip()
    if isinstance(profile, dict):
        return str(profile.get(key) or "").strip()
    return str(getattr(profile, key, "") or "").strip()


def _profile_id(profile: Any) -> str:
    return _profile_field(profile, "id")


class VideoTemplateSyncWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        workspace: VideoWorkspaceState,
        save_patch: dict[str, Any],
        profiles: list[Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("VideoTemplateSyncWorker")
        self._api = api
        self._workspace = workspace
        self._save_patch = save_patch
        self._profiles = profiles

    def run(self) -> None:
        try:
            template_id = str(self._workspace.template_id or "").strip()
            if not template_id:
                self.succeeded.emit("")
                return

            template_json = dict(self._workspace.template) if isinstance(self._workspace.template, dict) else {}
            name = str(
                self._save_patch.get("templateName")
                or template_json.get("templateName")
                or self._workspace.template_name
                or "Untitled Template"
            ).strip()
            if not name:
                name = "Untitled Template"

            synced = 0
            for profile in self._profiles:
                profile_id = _profile_id(profile)
                if not profile_id:
                    continue
                video_ref = _profile_field(profile, "video_template_id")
                reel_ref = _profile_field(profile, "reel_template_id")
                if video_ref == template_id:
                    self._api.upsert_profile_video_template(
                        profile_id,
                        template_id,
                        name=name,
                        kind="long",
                        template_json=template_json,
                        set_as_profile_default=True,
                    )
                    synced += 1
                if reel_ref == template_id:
                    self._api.upsert_profile_video_template(
                        profile_id,
                        template_id,
                        name=name,
                        kind="reel",
                        template_json=template_json,
                        set_as_profile_default=True,
                    )
                    synced += 1

            if synced:
                self.succeeded.emit(f"Synced template to {synced} profile link(s) on the server.")
                return

            fallback_profile = next((profile for profile in self._profiles if _profile_id(profile)), None)
            if fallback_profile is None:
                self.succeeded.emit(
                    "Saved locally. Create a channel profile to sync templates to the server."
                )
                return

            self._api.upsert_profile_video_template(
                _profile_id(fallback_profile),
                template_id,
                name=name,
                kind="long",
                template_json=template_json,
                set_as_profile_default=False,
            )
            self.succeeded.emit(
                "Synced template to the server. Link it to a channel profile in Settings to use it in the pipeline."
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc) or "Saved locally; server sync failed.")
        except Exception as exc:
            self.failed.emit(str(exc) or "Saved locally; server sync failed.")
