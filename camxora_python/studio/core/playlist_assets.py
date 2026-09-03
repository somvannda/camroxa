"""Playlist template background assets — one folder per sub-template name.

Drop a full-scene background into::

    assets/playlist_templates/{sub_template_id}/background.png

Optional style-picker preview::

    assets/playlist_templates/{sub_template_id}/thumbnail.png

Supported extensions: ``.png``, ``.jpg``, ``.jpeg``, ``.webp``.
The renderer scales it to cover the preview canvas (16:9).
"""

from __future__ import annotations

from pathlib import Path

from studio.core.playlist_settings import PlaylistSettings

_ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets" / "playlist_templates"
_BACKGROUND_NAMES = ("background.png", "background.jpg", "background.jpeg", "background.webp")
_THUMBNAIL_NAMES = ("thumbnail.png", "thumbnail.jpg", "thumbnail.jpeg", "thumbnail.webp")
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def playlist_templates_assets_root() -> Path:
    return _ASSETS_ROOT


def template_background_dir(template_key: str) -> Path:
    """Folder for a sub-template or family template id (e.g. ``minimal-white``)."""
    return _ASSETS_ROOT / template_key


def _find_named_asset_in_dir(folder: Path, preferred_names: tuple[str, ...]) -> Path | None:
    if not folder.is_dir():
        return None
    for name in preferred_names:
        path = folder / name
        if path.is_file():
            return path
    for ext in _IMAGE_EXTENSIONS:
        for path in sorted(folder.glob(f"*{ext}")):
            if path.is_file():
                return path
    return None


def find_background_in_dir(folder: Path) -> Path | None:
    return _find_named_asset_in_dir(folder, _BACKGROUND_NAMES)


def find_thumbnail_in_dir(folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    for name in _THUMBNAIL_NAMES:
        path = folder / name
        if path.is_file():
            return path
    return None


def bundled_background_path(sub_template_id: str, family_template_id: str | None = None) -> Path | None:
    for key in (sub_template_id, family_template_id or ""):
        if not key:
            continue
        found = find_background_in_dir(template_background_dir(key))
        if found is not None:
            return found
    return None


def bundled_thumbnail_path(sub_template_id: str) -> Path | None:
    return find_thumbnail_in_dir(template_background_dir(sub_template_id))


def resolve_playlist_background(settings: PlaylistSettings) -> Path | None:
    custom = settings.background_path
    if custom:
        path = Path(custom)
        if path.is_file():
            return path
    return bundled_background_path(settings.sub_template_id, settings.template_id)


def ensure_template_background_dir(template_key: str) -> Path:
    folder = template_background_dir(template_key)
    folder.mkdir(parents=True, exist_ok=True)
    return folder
