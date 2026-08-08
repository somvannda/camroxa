"""Root window — startup, auth, onboarding, and app shell navigation."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from app.application import AppShellWidget
from features.account.views.auth_view import AuthView
from features.account.views.startup_view import StartupView
from features.onboarding.views.onboarding_views import OnboardingWelcomeView, OnboardingWizardView
from shared.constants.auth import REGISTRATION_ENABLED
from shared.lib.app_icon import apply_app_window_icon
from shared.lib.opengl_startup import prime_opengl_on_window
from shared.lib.window_chrome import (
    center_window_on_screen,
    configure_rounded_window,
    sync_rounded_window_shape,
)
from shared.services.push_notification_runtime import PushNotificationRuntime
from shared.services.session_service import BootstrapDestination, BootstrapResult, SessionService
from shared.services.setup_readiness_service import refresh_setup_readiness
from shared.services.software_update_service import SoftwareUpdateService
from shared.widgets.software_update_gate import SoftwareUpdateGateOverlay
from shared.widgets.window_title_bar import WindowTitleBar
from shared.workers.bootstrap_worker import AuthWorker, BootstrapWorker
from shared.workers.shell_warmup_worker import ShellWarmupWorker


class RootWindow(QMainWindow):
    """Top-level window managing auth flow and main application shell."""

    MIN_WIDTH = 1920
    MIN_HEIGHT = 1080

    _PAGE_STARTUP = 0
    _PAGE_AUTH = 1
    _PAGE_ONBOARDING_WELCOME = 2
    _PAGE_ONBOARDING_WIZARD = 3

    def __init__(self, session: SessionService | None = None) -> None:
        super().__init__()
        self._session = session or SessionService()
        self._worker: BootstrapWorker | AuthWorker | ShellWarmupWorker | None = None
        self._push_runtime: PushNotificationRuntime | None = None
        self._centered_on_launch = False

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowTitle("Camxora")
        apply_app_window_icon(self)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(self.MIN_WIDTH, self.MIN_HEIGHT)
        center_window_on_screen(self)

        self._stack = QStackedWidget()
        self._title_bar = WindowTitleBar(self)
        self._build_window_surface()

        self._startup = StartupView()
        self._auth = AuthView(storage=self._session.storage)
        self._onboarding_welcome = OnboardingWelcomeView()
        self._onboarding_wizard = OnboardingWizardView()
        self._app_shell: AppShellWidget | None = None

        self._stack.addWidget(self._startup)
        self._stack.addWidget(self._auth)
        self._stack.addWidget(self._onboarding_welcome)
        self._stack.addWidget(self._onboarding_wizard)

        self._connect_signals()
        configure_rounded_window(self)
        # Parent a 1x1 hidden QOpenGLWidget before the first show() so Windows
        # creates an OpenGL-capable HWND. Video prewarm mounts the real preview
        # later; without this prime the splash window briefly "restarts".
        prime_opengl_on_window(self)
        self._show_page(self._PAGE_STARTUP)
        self._start_bootstrap()

    def _build_window_surface(self) -> None:
        surface = QWidget(self)
        surface.setObjectName("window_surface")
        surface.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(surface)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._title_bar)
        layout.addWidget(self._stack, stretch=1)

        self.setCentralWidget(surface)
        self._window_surface = surface
        self._software_update_gate = SoftwareUpdateGateOverlay(surface)
        self._software_update_gate.update_requested.connect(self._start_software_update_install)
        # Restore a mandatory update left over if Setup was still running / failed.
        SoftwareUpdateService.instance().restore_from_disk()
        self._sync_software_update_gate_geometry()

    def _connect_signals(self) -> None:
        self._auth.login_requested.connect(self._on_login_requested)
        self._auth.register_requested.connect(self._on_register_requested)
        self._auth.switch_account_requested.connect(self._on_switch_account_requested)
        self._onboarding_welcome.continue_clicked.connect(self._show_login)
        self._onboarding_wizard.refresh_requested.connect(self._retry_bootstrap_after_onboarding)
        self._onboarding_wizard.skip_to_app.connect(self._show_app_shell)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        # Stop shell background workers before destroying the window hierarchy.
        # Sync/push QThreads used to be parented under the shell and destroyed
        # mid-run with an empty objectName while Manual Export was still alive.
        from PySide6.QtWidgets import QApplication

        from shared.services.video_pipeline_activity import (
            any_video_pipeline_threads_running,
            set_app_quitting,
            shutdown_video_pipeline_threads,
            terminate_video_pipeline_threads,
        )

        set_app_quitting(True)
        try:
            if self._app_shell is not None:
                self._app_shell.prepare_app_quit()
        except Exception:
            pass
        try:
            self._stop_push_notifications()
        except Exception:
            pass
        try:
            if self._app_shell is not None:
                self._app_shell.shutdown_background_workers()
        except Exception:
            pass
        try:
            from shared.services.app_thread_registry import shutdown_app_threads

            # Single budget for remaining sync/push workers (~10s), then export join.
            shutdown_app_threads(wait_ms=10_000)
        except Exception:
            pass
        try:
            shutdown_video_pipeline_threads(wait_ms=20_000)
        except Exception:
            pass
        # Drain finished handlers now that stop/quit flags block batch chaining.
        try:
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
            shutdown_video_pipeline_threads(wait_ms=5_000)
        except Exception:
            pass

        if any_video_pipeline_threads_running():
            retries = int(getattr(self, "_quit_join_retries", 0) or 0)
            if retries < 40:
                self._quit_join_retries = retries + 1
                event.ignore()
                QTimer.singleShot(500, self.close)
                return
            try:
                terminate_video_pipeline_threads()
            except Exception:
                pass

        self._quit_join_retries = 0
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.WindowStateChange:
            self._title_bar.sync_window_state()
            sync_rounded_window_shape(self)
        if event.type() in {QEvent.Type.ActivationChange, QEvent.Type.WindowActivate}:
            # GPU export / preview can steal the taskbar surface; restamp branding.
            apply_app_window_icon(self)
        super().changeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        sync_rounded_window_shape(self)
        self._sync_software_update_gate_geometry()
        super().resizeEvent(event)

    def showEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        sync_rounded_window_shape(self)
        super().showEvent(event)
        # Native taskbar icon needs a real HWND; apply again after the window is visible.
        apply_app_window_icon(self)
        # Screen geometry is reliable after the first show; center once on launch only.
        if not self._centered_on_launch:
            center_window_on_screen(self)
            self._centered_on_launch = True
            # One deferred pass covers Windows DPI / frame-size settling after map.
            QTimer.singleShot(0, self._center_after_map)

    def _center_after_map(self) -> None:
        if self.isMaximized() or self.isFullScreen():
            return
        center_window_on_screen(self)

    def bring_to_front(self) -> None:
        """Restore and focus this window (used when a second instance is launched)."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        try:
            # Windows: force foreground when another process launched us.
            import ctypes

            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
        except Exception:
            pass

    def _destroy_app_shell(self) -> None:
        self._stop_push_notifications()
        if self._app_shell is None:
            return
        try:
            self._app_shell.shutdown_background_workers()
        except Exception:
            pass
        try:
            self._app_shell.logout_requested.disconnect(self._on_logout)
        except (RuntimeError, TypeError):
            pass
        self._stack.removeWidget(self._app_shell)
        self._app_shell.deleteLater()
        self._app_shell = None

    def _ensure_app_shell(self) -> AppShellWidget:
        if self._app_shell is None:
            self._app_shell = AppShellWidget(session=self._session)
            self._app_shell.logout_requested.connect(self._on_logout)
            self._stack.addWidget(self._app_shell)
        return self._app_shell

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _start_bootstrap(self) -> None:
        worker = BootstrapWorker(self._session, self)
        worker.progress.connect(self._startup.set_progress)
        worker.finished_with_result.connect(self._on_bootstrap_finished)
        self._worker = worker
        worker.start()

    def _on_bootstrap_finished(self, result: object) -> None:
        if not isinstance(result, BootstrapResult):
            self._show_login()
            return
        self._apply_bootstrap_result(result)

    def _apply_bootstrap_result(self, result: BootstrapResult) -> None:
        if result.destination == BootstrapDestination.LOGIN:
            self._show_login(error=result.message)
        elif result.destination == BootstrapDestination.ONBOARDING_WELCOME:
            self._show_page(self._PAGE_ONBOARDING_WELCOME)
        elif result.destination == BootstrapDestination.ONBOARDING_WIZARD:
            self._show_page(self._PAGE_ONBOARDING_WIZARD)
        else:
            self._show_app_shell()

    def _show_login(self, *, error: str = "") -> None:
        self._stop_push_notifications()
        self._title_bar.set_setup_notifications_visible(False)
        self._auth.show_login_form()
        if error.strip():
            self._auth.set_error(error.strip())
        self._show_page(self._PAGE_AUTH)

    def _retry_bootstrap_after_onboarding(self) -> None:
        self._startup.reset_progress(40)
        self._show_page(self._PAGE_STARTUP)
        self._startup.set_progress("Checking profiles", "Refreshing your account.", 45)
        worker = BootstrapWorker(self._session, parent=self)
        worker.progress.connect(self._startup.set_progress)
        worker.finished_with_result.connect(self._on_bootstrap_finished)
        worker.start()
        self._worker = worker

    def _show_app_shell(self) -> None:
        # Rebuild the shell so lazy pages never keep the previous account's UI.
        self._destroy_app_shell()
        # Keep one continuous loading pass. Only reset progress when coming
        # from auth/onboarding (not already on the startup screen).
        if self._stack.currentWidget() is not self._startup:
            self._startup.reset_progress(55)
            self._show_page(self._PAGE_STARTUP)
        self._startup.set_progress("Preparing workspace", "Loading shared studio data.", 60)
        worker = ShellWarmupWorker(self._session.api, self._session.workspace_cache, parent=self)
        worker.progress.connect(self._startup.set_progress)
        worker.succeeded.connect(self._on_shell_warmup_succeeded)
        worker.failed.connect(self._on_shell_warmup_failed)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_shell_warmup_succeeded(self) -> None:
        # Build the shell and every heavy page while the startup screen is
        # still up, so the app never stalls or "reloads" after it opens.
        shell = self._ensure_app_shell()
        shell.refresh_account_summary()
        self._title_bar.set_setup_notifications_visible(True)
        refresh_setup_readiness(
            api=self._session.api,
            cache=self._session.workspace_cache,
            parent=self,
            force_network=True,
        )
        self._start_push_notifications()
        self._startup.set_progress("Opening studio", "Building workspace pages.", 92)
        QTimer.singleShot(0, self._prewarm_next_shell_page)

    def _prewarm_next_shell_page(self) -> None:
        shell = self._ensure_app_shell()
        key = shell.prewarm_pending_page()
        if key is not None:
            self._startup.set_progress("Opening studio", f"Preparing {key} workspace.", 96)
            QTimer.singleShot(0, self._prewarm_next_shell_page)
            return
        self._startup.set_progress("Opening studio", "Workspace ready.", 100)
        # Apply cached dashboard before the shell is shown so Home is not empty.
        # This must never leave the user stuck on the startup screen: log and
        # still reveal the shell even if home-page activation raises (e.g. a
        # machine-specific rendering/network fault during dashboard load).
        try:
            shell.show_home()
        except Exception as exc:
            from shared.services.app_logger import log_error

            log_error("show_home() failed during startup", category="startup", exc=exc)
        self._stack.setCurrentWidget(shell)

    def _on_shell_warmup_failed(self, _message: str) -> None:
        # Continue into the app even if warmup fails — pages will fetch on demand.
        self._on_shell_warmup_succeeded()

    def _on_switch_account_requested(self, user_id: str) -> None:
        self._destroy_app_shell()
        result = self._session.switch_saved_account(user_id)
        self._auth.set_busy(False)
        self._auth.clear_loading_status()
        if isinstance(result, BootstrapResult):
            self._apply_bootstrap_result(result)
            return
        self._show_login(error="Unable to switch accounts.")

    def _on_login_requested(self, email: str, password: str) -> None:
        self._run_auth_worker(mode="login", email=email, password=password)

    def _on_register_requested(self, email: str, password: str, display_name: str) -> None:
        if not REGISTRATION_ENABLED:
            self._auth.set_error("Account registration is not available. Contact your administrator.")
            return
        self._run_auth_worker(
            mode="register",
            email=email,
            password=password,
            display_name=display_name,
        )

    def _run_auth_worker(
        self,
        *,
        mode: str,
        email: str,
        password: str,
        display_name: str = "",
    ) -> None:
        self._session.set_api_base_url(self._auth.get_api_base_url())
        self._auth.set_busy(True)
        self._auth.set_loading_status("Signing in", "Checking your credentials.")
        worker = AuthWorker(
            self._session,
            mode=mode,
            email=email,
            password=password,
            display_name=display_name,
            parent=self,
        )
        worker.progress.connect(lambda label, detail, _value: self._auth.set_loading_status(label, detail))
        worker.succeeded.connect(self._on_auth_succeeded)
        worker.failed.connect(self._on_auth_failed)
        worker.finished.connect(lambda: self._auth.set_busy(False))
        self._worker = worker
        worker.start()

    def _on_auth_succeeded(self, result: object) -> None:
        try:
            from shared.services.app_logger import log_info

            log_info("Authentication succeeded", category="auth")
        except Exception:
            pass
        self._auth.clear_loading_status()
        if isinstance(result, BootstrapResult):
            self._apply_bootstrap_result(result)
            return
        self._show_page(self._PAGE_ONBOARDING_WELCOME)

    def _on_auth_failed(self, message: str) -> None:
        try:
            from shared.services.app_logger import log_error

            log_error(f"Authentication failed: {message}", category="auth")
        except Exception:
            pass
        self._auth.clear_loading_status()
        self._auth.set_error(message)
        self._show_page(self._PAGE_AUTH)

    def _on_logout(self) -> None:
        try:
            from shared.services.app_logger import log_info

            log_info("User logged out", category="auth")
        except Exception:
            pass
        self._stop_push_notifications()
        self._session.logout()
        self._destroy_app_shell()
        self._show_login()

    def _start_push_notifications(self) -> None:
        self._stop_push_notifications()
        self._push_runtime = PushNotificationRuntime(self._session, parent=self)
        self._push_runtime.start()

    def _stop_push_notifications(self) -> None:
        if self._push_runtime is None:
            return
        self._push_runtime.stop()
        self._push_runtime = None

    def _sync_software_update_gate_geometry(self) -> None:
        if not hasattr(self, "_software_update_gate"):
            return
        self._software_update_gate.setGeometry(self._window_surface.rect())
        if SoftwareUpdateService.instance().should_block_app():
            self._software_update_gate.raise_()

    def _start_software_update_install(self) -> None:
        SoftwareUpdateService.instance().start_install(parent=self)
