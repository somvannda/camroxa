"""Application bootstrap — entry point for the PyQt6 desktop application.

Two-window architecture with seamless transition:

* A frameless login QWidget is shown immediately (lightweight, ~instant).
* On authentication success the login window hides and the frameless MainWindow
  shows at the same position — visually it looks like a page transition rather
  than a window swap.
* The heavy MainWindow (DB, GPU spectrum preview, all pages, polling timers)
  is built lazily only AFTER successful authentication.
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSurfaceFormat, QIcon
from PyQt6.QtWidgets import QApplication


def run() -> int:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)

    # Ensure Windows shows our icon (not the Python/launcher icon) on the taskbar.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MusicGenerator.DesktopStudio"
            )
        except Exception:
            pass

    from .resources import icon_path
    from python_app.services.token_store import TokenStore
    from python_app.services.auth_client import AuthClient
    from python_app.services.license_gate import LicenseGate
    from python_app.services.generation_proxy import GenerationProxy

    app = QApplication(sys.argv)
    try:
        app.setWindowIcon(QIcon(icon_path("app.ico")))
    except Exception:
        pass

    # -------------------------------------------------------------------
    # Load custom font: Open Sans (variable weight)
    # -------------------------------------------------------------------
    from PyQt6.QtGui import QFontDatabase
    _font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "OpenSans-Variable.ttf")
    _font_path = os.path.normpath(_font_path)
    if os.path.exists(_font_path):
        _font_id = QFontDatabase.addApplicationFont(_font_path)
        if _font_id != -1:
            _families = QFontDatabase.applicationFontFamilies(_font_id)
            if _families:
                _DEFAULT_FONT = _families[0]
            else:
                _DEFAULT_FONT = "Segoe UI"
        else:
            _DEFAULT_FONT = "Segoe UI"
    else:
        _DEFAULT_FONT = "Segoe UI"
    app.setProperty("_default_font_family", _DEFAULT_FONT)

    # -----------------------------------------------------------------------
    # Auth/license/generation services (lightweight to construct)
    # -----------------------------------------------------------------------
    from python_app.models.music_model import default_music_app_data

    default_data = default_music_app_data()
    default_settings = default_data.get("settings") or {}
    platform_api_base_url: str = default_settings.get(
        "platformApiBaseUrl", "http://localhost:8000/api/v1"
    )

    token_store = TokenStore()
    auth_client = AuthClient(base_url=platform_api_base_url)
    license_gate = LicenseGate(base_url=platform_api_base_url)
    generation_proxy = GenerationProxy(
        base_url=platform_api_base_url,
        token_store=token_store,
        auth_client=auth_client,
    )

    app.setProperty("token_store", token_store)
    app.setProperty("auth_client", auth_client)
    app.setProperty("license_gate", license_gate)
    app.setProperty("generation_proxy", generation_proxy)

    # -------------------------------------------------------------------
    # Widget UI mode — always use original widget login
    # -------------------------------------------------------------------
    from python_app.design_system.bootstrap import apply_theme
    apply_theme(app)

    # Set application-wide default font
    from PyQt6.QtGui import QFont
    _font = QFont(_DEFAULT_FONT)
    _font.setPixelSize(14)
    app.setFont(_font)

    from python_app.views.login_view import LoginView
    from python_app.views.login_page_controller import LoginPageController

    login_view = LoginView()
    login_view.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    # Single source of truth for the app window size (see window_config.py).
    from .window_config import apply_fixed_window_size
    apply_fixed_window_size(login_view)
    try:
        login_view.setWindowIcon(QIcon(icon_path("app.ico")))
    except Exception:
        pass

    app.setProperty("login_view", login_view)

    # Holds the lazily-built MainWindow once created.
    state: dict[str, object] = {"main_window": None}

    def on_authenticated() -> None:
        """Build the main window on first auth, then reveal it seamlessly."""
        main_window = state["main_window"]
        if main_window is None:
            from .main_window import MainWindow

            main_window = MainWindow()
            # Window size is applied centrally in init_orchestrator via
            # window_config.apply_fixed_window_size — no per-call sizing here.
            try:
                main_window.setWindowIcon(QIcon(icon_path("app.ico")))
            except Exception:
                pass

            main_window._generation_proxy = generation_proxy
            if hasattr(main_window, "_music_coordinator"):
                main_window._music_coordinator._generation_proxy = generation_proxy
            if hasattr(main_window, "_image_coordinator"):
                main_window._image_coordinator._generation_proxy = generation_proxy

            state["main_window"] = main_window
            app.setProperty("main_window", main_window)

        # Seamless transition: show MainWindow at the same position as login.
        # Size is already pinned (window_config) and identical for both windows.
        main_window.move(login_view.pos())
        login_view.hide()
        main_window.show()
        main_window.setWindowTitle("Music Generator")
        main_window.apply_license_gating()

    app.setProperty("on_authenticated_fn", on_authenticated)

    # -------------------------------------------------------------------
    # Login controller
    # -------------------------------------------------------------------
    login_page_controller = LoginPageController(
        auth_client=auth_client,
        token_store=token_store,
        license_gate=license_gate,
        on_authenticated=on_authenticated,
    )
    login_page_controller.set_view(login_view)
    app.setProperty("login_page_controller", login_page_controller)

    # -----------------------------------------------------------------------
    # Startup: skip login entirely if session is active, otherwise show login.
    # -----------------------------------------------------------------------
    if token_store.has_tokens():
        # Tokens exist — try to validate/refresh them synchronously.
        # If valid, check profiles → onboarding or main app.
        # If invalid, fall through to show login.
        try:
            stored = token_store.load()
            if stored is not None:
                is_valid = auth_client.validate(stored.access_token)
                if is_valid:
                    # Session active — check if user has channel profiles
                    profiles = auth_client.check_profiles(stored.access_token)
                    if profiles.get("has_profiles", False):
                        on_authenticated()
                        return int(app.exec())
                    else:
                        # No profiles — go to onboarding, not main app
                        login_view.show()
                        login_page_controller._open_onboarding_with_token("", stored.access_token)
                        return int(app.exec())
                # Try refresh
                try:
                    new_tokens = auth_client.refresh(stored.refresh_token)
                    token_store.save(new_tokens.access_token, new_tokens.refresh_token)
                    profiles = auth_client.check_profiles(new_tokens.access_token)
                    if profiles.get("has_profiles", False):
                        on_authenticated()
                        return int(app.exec())
                    else:
                        login_view.show()
                        login_page_controller._open_onboarding_with_token("", new_tokens.access_token)
                        return int(app.exec())
                except Exception:
                    pass
        except Exception:
            pass
        # Validation/refresh failed — clear stale tokens and show login
        token_store.clear()

    login_view.show()

    return int(app.exec())
