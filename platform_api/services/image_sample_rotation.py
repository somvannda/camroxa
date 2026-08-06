"""Image sample candidate resolution and least-used rotation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from platform_api.models.enums import ImageKind


class ImageSampleRepositoryProtocol(Protocol):
    async def pick_least_used_value(
        self,
        *,
        kind: str,
        values: list[str],
        exclude: list[str] | None = None,
    ) -> str: ...


class ImageSamplePackRepositoryProtocol(Protocol):
    async def list_vps_asset_paths(self, *, category: str) -> list[str]: ...


class ImageSampleRotationService:
    """Resolve sample image paths with DB-backed least-used rotation."""

    def __init__(
        self,
        repo: ImageSampleRepositoryProtocol,
        pack_repo: ImageSamplePackRepositoryProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._pack_repo = pack_repo

    @staticmethod
    def _coerce_setting_paths(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item or "").strip() for item in value if str(item or "").strip()]

    @staticmethod
    def _list_directory_images(directory: str) -> list[str]:
        base = Path(str(directory or "").strip()).expanduser()
        if not base.exists() or not base.is_dir():
            return []
        supported = {".png", ".jpg", ".jpeg", ".webp"}
        return sorted(
            str(path)
            for path in base.iterdir()
            if path.is_file() and path.suffix.lower() in supported
        )

    @classmethod
    def build_candidates(
        cls,
        settings: dict[str, Any],
        kind: ImageKind,
    ) -> list[str]:
        if kind == ImageKind.BACKGROUND:
            selected_key = "imageBgSamples"
            dir_key = "imageBackgroundSamplesDir"
        else:
            selected_key = "imageThumbSamples"
            dir_key = "imageThumbnailSamplesDir"

        selected = [
            path
            for path in cls._coerce_setting_paths(settings.get(selected_key))
            if Path(path).is_file()
        ]
        discovered = cls._list_directory_images(str(settings.get(dir_key, "") or ""))
        return selected or discovered

    @staticmethod
    def _history_kind(kind: ImageKind) -> str:
        return "bg_sample" if kind == ImageKind.BACKGROUND else "thumb_sample"

    @staticmethod
    def _category_for_kind(kind: ImageKind) -> str:
        return "background" if kind == ImageKind.BACKGROUND else "thumbnail"

    async def _resolve_candidates(
        self,
        settings: dict[str, Any],
        kind: ImageKind,
    ) -> list[str]:
        """Category mode uses admin VPS sample packs only.

        Local ``imageBackgroundSamplesDir`` / ``imageBgSamples`` settings are legacy
        and must not be used on the API host (they point at desktop paths).
        """
        del settings  # intentionally unused — no desktop-folder fallback
        if self._pack_repo is None:
            return []
        try:
            vps_paths = await self._pack_repo.list_vps_asset_paths(
                category=self._category_for_kind(kind)
            )
        except Exception:
            return []
        return [path for path in vps_paths if Path(path).is_file()]

    async def pick_sample_path(
        self,
        *,
        settings: dict[str, Any],
        kind: ImageKind,
        exclude: list[str] | None = None,
    ) -> str | None:
        candidates = await self._resolve_candidates(settings, kind)
        if not candidates:
            return None
        chosen = await self._repo.pick_least_used_value(
            kind=self._history_kind(kind),
            values=candidates,
            exclude=exclude,
        )
        return str(chosen or "").strip() or None
