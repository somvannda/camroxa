from __future__ import annotations

from shared.icons.chrome_assets import CHROME_SVG_BY_NAME
from shared.lib.app_paths import get_video_templates_path
from shared.lib.resource_paths import get_package_root, get_resource_path


def test_resource_paths_resolve_logo() -> None:
    root = get_package_root()
    assert root.name == "camxora_python" or (root / "resources").exists()
    logo = get_resource_path("app-logo.svg")
    assert logo == root / "resources" / "app-logo.svg"
    assert logo.is_file()


def test_app_ico_present_for_packaging() -> None:
    ico = get_resource_path("app-icon.ico")
    assert ico.is_file(), "resources/app-icon.ico is required for Windows exe branding"


def test_window_chrome_svgs_present_for_packaging() -> None:
    for name in (
        "app-logo.svg",
        "window-close.svg",
        "window-minimize.svg",
        "window-maximize.svg",
    ):
        path = get_resource_path(name)
        assert path.is_file(), f"resources/{name} is required for title-bar chrome"
        assert name in CHROME_SVG_BY_NAME


def test_login_background_present_for_packaging() -> None:
    path = get_resource_path("background_login.png")
    assert path.is_file(), "resources/background_login.png is required for the login backdrop"


def test_factory_templates_resolve_from_repo() -> None:
    path = get_video_templates_path()
    assert path.name == "video_templates_local.json"
    assert path.is_file()
