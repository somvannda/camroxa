"""MarketplacePageController — wires MarketplaceCoordinator to the MarketplaceView.

Handles catalog fetching on page load and filter changes, install flow with
already-installed detection and reinstall prompting, success notifications
(auto-dismiss 5s), and catalog failures shown as error (not empty) state.

Install/reinstall run off the UI thread so downloads do not freeze the shell.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from features.marketplace.coordinator import CatalogResponse, InstallResult, MarketplaceCoordinator
from features.marketplace.views.marketplace_view import MarketplaceView


class MarketplacePageController(QObject):
    """Controller that connects marketplace view signals to the coordinator.

    Responsibilities:
        - Fetch catalog on init and on filter/page changes (off UI thread)
        - Handle install requests with duplicate detection (off UI thread)
        - Show success notification (auto-dismiss 5s) after install/reinstall
        - Show error state when catalog fetch fails (never confuse with empty)
        - Mark Installed card state from local store (marketplace_item_id)
        - Notify shell when local templates change so Video dropdown can refresh
    """

    _SUCCESS_DISMISS_MS = 5000
    _catalog_ready = Signal(int, object)  # seq, CatalogResponse | Exception
    _install_ready = Signal(str, object)  # item_id, InstallResult | Exception

    def __init__(
        self,
        view: MarketplaceView,
        coordinator: MarketplaceCoordinator,
        parent: QObject | None = None,
        *,
        on_templates_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._coordinator = coordinator
        self._on_templates_changed = on_templates_changed

        self._current_page: int = 1
        self._current_kind: str | None = None
        self._current_search: str | None = None
        self._refresh_seq: int = 0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mkt-catalog")
        self._install_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mkt-install")
        self._pending_reinstall: set[str] = set()

        self._view.kind_filter_changed.connect(self._on_kind_changed)
        self._view.search_changed.connect(self._on_search_changed)
        self._view.page_changed.connect(self._on_page_changed)
        self._view.install_requested.connect(self._on_install_requested)
        self._view.retry_requested.connect(self._refresh_catalog)
        self._catalog_ready.connect(self._on_catalog_ready)
        self._install_ready.connect(self._on_install_ready)

        self._refresh_catalog()

    # ─── Signal Handlers ──────────────────────────────────────────────────

    @Slot(object)
    def _on_kind_changed(self, kind: object) -> None:
        """Handle kind filter change — reset to page 1 and refresh."""
        self._current_kind = kind if isinstance(kind, str) and kind else None
        self._current_page = 1
        self._refresh_catalog()

    @Slot(str)
    def _on_search_changed(self, search: str) -> None:
        """Handle search text change (already debounced by the view)."""
        cleaned = (search or "").strip()
        self._current_search = cleaned or None
        self._current_page = 1
        self._refresh_catalog()

    @Slot(int)
    def _on_page_changed(self, page: int) -> None:
        """Handle pagination page change."""
        self._current_page = page
        self._refresh_catalog()

    @Slot(str)
    def _on_install_requested(self, item_id: str) -> None:
        """Handle install button click on a template card."""
        self._view.set_install_progress(item_id, True)

        reinstall = False
        try:
            if self._coordinator.is_installed(item_id):
                reply = QMessageBox.question(
                    self._view,
                    "Template Already Installed",
                    "This template is already installed. Do you want to reinstall it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self._view.set_install_progress(item_id, False)
                    return
                reinstall = True
                self._pending_reinstall.add(item_id)
        except Exception as exc:
            self._view.set_install_progress(item_id, False)
            QMessageBox.warning(self._view, "Marketplace", f"Installation failed: {exc}")
            return

        def _work() -> InstallResult:
            if reinstall:
                return self._coordinator.reinstall_template(item_id)
            return self._coordinator.install_template(item_id)

        def _done(future) -> None:  # type: ignore[no-untyped-def]
            try:
                result: object = future.result()
            except Exception as exc:
                result = exc
            self._install_ready.emit(item_id, result)

        self._install_executor.submit(_work).add_done_callback(_done)

    @Slot(str, object)
    def _on_install_ready(self, item_id: str, result: object) -> None:
        self._view.set_install_progress(item_id, False)

        if isinstance(result, Exception):
            self._pending_reinstall.discard(item_id)
            QMessageBox.warning(self._view, "Marketplace", f"Installation failed: {result}")
            return

        if not isinstance(result, InstallResult):
            self._pending_reinstall.discard(item_id)
            QMessageBox.warning(self._view, "Marketplace", "Installation failed: unexpected response")
            return

        if result.error:
            self._pending_reinstall.discard(item_id)
            QMessageBox.warning(self._view, "Marketplace", result.error)
            return

        if result.ok:
            was_reinstall = item_id in self._pending_reinstall
            self._pending_reinstall.discard(item_id)
            self._view.set_item_installed(item_id, True)
            if self._on_templates_changed is not None:
                try:
                    self._on_templates_changed()
                except Exception:
                    pass
            self._show_success_notification(
                "Template reinstalled successfully."
                if was_reinstall
                else "Template installed successfully."
            )

    # ─── Catalog Refresh ──────────────────────────────────────────────────

    @Slot()
    def _refresh_catalog(self) -> None:
        """Fetch the catalog off the UI thread and update the view."""
        self._refresh_seq += 1
        seq = self._refresh_seq
        page = self._current_page
        kind = self._current_kind
        search = self._current_search

        self._view.set_loading(True)
        self._view.begin_preview_generation()

        def _work() -> CatalogResponse:
            return self._coordinator.fetch_catalog(page=page, kind=kind, search=search)

        def _done(future) -> None:  # type: ignore[no-untyped-def]
            try:
                result: object = future.result()
            except Exception as exc:
                result = exc
            self._catalog_ready.emit(seq, result)

        self._executor.submit(_work).add_done_callback(_done)

    @Slot(int, object)
    def _on_catalog_ready(self, seq: int, result: object) -> None:
        if seq != self._refresh_seq:
            return

        if isinstance(result, Exception):
            self._view.set_loading(False)
            self._view.set_error(f"Failed to load catalog: {result}")
            return

        if not isinstance(result, CatalogResponse):
            self._view.set_loading(False)
            self._view.set_error("Failed to load catalog: unexpected response")
            return

        if result.error:
            self._view.set_loading(False)
            self._view.set_error(result.error)
            return

        installed_ids = {
            item.id for item in result.items if self._coordinator.is_installed(item.id)
        }
        self._view.set_loading(False)
        self._view.set_catalog(
            result.items,
            result.total,
            result.page,
            result.page_size,
            installed_ids=installed_ids,
        )

    # ─── Notifications ────────────────────────────────────────────────────

    def _show_success_notification(self, message: str) -> None:
        """Show a temporary success message that auto-dismisses after 5 seconds."""
        msg_box = QMessageBox(self._view)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Success")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.show()
        QTimer.singleShot(self._SUCCESS_DISMISS_MS, msg_box.close)
