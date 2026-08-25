"""Build-time configuration baked into sandbox/production desktop installers.

Release builds must set CAMXORA_BUILD_ENV and CAMXORA_API_BASE_URL at compile
time (PyInstaller env, CI pipeline, or bundled `.env` next to the executable).
End users cannot switch API endpoints from Settings — each installer artifact
targets exactly one environment.
"""

from __future__ import annotations

import os
from pathlib import Path

from shared.lib.runtime_paths import get_install_dir, is_frozen_runtime

_BUILD_ENV = os.environ.get("CAMXORA_BUILD_ENV", "development").strip().lower()
_API_BASE_URL = os.environ.get("CAMXORA_API_BASE_URL", "").strip()
_PORTAL_BASE_URL = os.environ.get("CAMXORA_PORTAL_BASE_URL", "").strip()

_ENV_FILE_NAMES = (".env", ".env.local", ".env.sandbox", ".env.production")


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_bundled_env() -> dict[str, str]:
    candidates: list[Path] = []
    install_dir = get_install_dir()
    if install_dir is not None:
        candidates.extend(install_dir / name for name in _ENV_FILE_NAMES)
        internal = install_dir / "_internal"
        if internal.is_dir():
            candidates.extend(internal / name for name in _ENV_FILE_NAMES)
    if is_frozen_runtime():
        import sys

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.extend(Path(meipass) / name for name in _ENV_FILE_NAMES)
    module_dir = Path(__file__).resolve().parents[2]
    candidates.extend(module_dir / name for name in _ENV_FILE_NAMES)
    merged: dict[str, str] = {}
    for candidate in candidates:
        if candidate.is_file():
            merged.update(_read_env_file(candidate))
    return merged


def _resolve_build_env() -> str:
    bundled = _load_bundled_env()
    raw = (
        os.environ.get("CAMXORA_BUILD_ENV")
        or bundled.get("CAMXORA_BUILD_ENV")
        or _BUILD_ENV
    )
    return str(raw).strip().lower() or "development"


def _resolve_api_base_url() -> str | None:
    bundled = _load_bundled_env()
    raw = (
        os.environ.get("CAMXORA_API_BASE_URL")
        or bundled.get("CAMXORA_API_BASE_URL")
        or _API_BASE_URL
    )
    cleaned = str(raw).strip().rstrip("/")
    return cleaned or None


def _resolve_portal_base_url() -> str | None:
    bundled = _load_bundled_env()
    raw = (
        os.environ.get("CAMXORA_PORTAL_BASE_URL")
        or bundled.get("CAMXORA_PORTAL_BASE_URL")
        or _PORTAL_BASE_URL
    )
    cleaned = str(raw).strip().rstrip("/")
    return cleaned or None


def build_environment() -> str:
    """One of: development, sandbox, production."""
    return _resolve_build_env()


def is_api_url_locked() -> bool:
    """True when the desktop build targets sandbox or production."""
    if is_frozen_runtime():
        return True
    return build_environment() in {"sandbox", "production"}


def get_bundled_api_base_url() -> str | None:
    """Locked API base URL for release builds, or None in local development."""
    if not is_api_url_locked():
        return None
    return _resolve_api_base_url()


def get_portal_base_url() -> str:
    """User portal URL for onboarding / billing deep links."""
    explicit = _resolve_portal_base_url()
    if explicit:
        return explicit
    env = build_environment()
    if env == "sandbox":
        return "https://app.sandbox.camxora.com"
    if env == "production":
        return "https://app.camxora.com"
    return "http://localhost:3001"


def get_onboarding_url() -> str:
    return f"{get_portal_base_url()}/onboarding"


def get_music_web_base_url() -> str:
    """Music web (Create + Choose Your Plan pricing)."""
    bundled = _load_bundled_env()
    raw = (
        os.environ.get("CAMXORA_MUSIC_WEB_BASE_URL")
        or bundled.get("CAMXORA_MUSIC_WEB_BASE_URL")
        or ""
    ).strip().rstrip("/")
    if raw:
        return raw
    env = build_environment()
    if env == "sandbox":
        return "https://music.sandbox.camxora.com"
    if env == "production":
        return "https://music.camxora.com"
    return "http://localhost:3002"


def get_pricing_url(*, embed: bool = False) -> str:
    """Music web plans UI opened from the desktop Choose Your Plan dialog."""
    base = get_music_web_base_url()
    if embed:
        return f"{base}/pricing/embed"
    return f"{base}/pricing"


def build_label() -> str:
    env = build_environment()
    if env == "sandbox":
        return "Sandbox"
    if env == "production":
        return "Production"
    return "Development"


def should_show_api_environment_badge() -> bool:
    """Production builds hide the API environment badge from end users."""
    return build_environment() != "production"


def footer_environment_badge() -> tuple[str | None, str]:
    """Short footer label + tooltip for the active API target (non-production only)."""
    if not should_show_api_environment_badge():
        return None, ""

    env = build_environment()
    api_url = get_bundled_api_base_url() or _resolve_api_base_url() or ""

    if env == "sandbox":
        return "Sandbox API", api_url
    if env == "development":
        lowered = api_url.lower()
        if "localhost" in lowered or "127.0.0.1" in lowered:
            return "Local API", api_url
        return "Dev API", api_url
    return None, api_url


def footer_version_badge() -> tuple[str, str]:
    """Short footer label + tooltip for the running desktop build."""
    from shared.constants.app_version import get_app_version

    version = get_app_version()
    return f"v{version}", f"Camxora desktop {version}"
