"""Marketplace page — paginated card grid of marketplace templates with filtering and install."""

from __future__ import annotations

from urllib.parse import urljoin

from PySide6.QtCore import Qt, Signal, QTimer, QByteArray, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.marketplace.coordinator import CatalogItem
from features.marketplace.preview_loader import MarketplacePreviewLoader


# ─── Helpers ──────────────────────────────────────────────────────────────────


def truncate_description(text: str, max_len: int = 90) -> str:
    """Truncate description to max_len characters with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\u2026"


def resolve_marketplace_asset_url(api_base_url: str, path_or_url: str) -> str:
    """Join API base with a relative asset path without doubling ``/api/v3``.

    Catalog responses return absolute-path URLs like
    ``/api/v3/marketplace/items/{id}/preview``. The desktop client's base URL is
    already ``http://host:port/api/v3``, so a naive concatenate produces a 404.
    """
    candidate = (path_or_url or "").strip()
    if not candidate:
        return ""
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate

    base = (api_base_url or "").strip().rstrip("/") + "/"
    path = candidate if candidate.startswith("/") else f"/{candidate}"

    if base.rstrip("/").endswith("/api/v3") and path.startswith("/api/v3/"):
        path = path[len("/api/v3") :]

    return urljoin(base, path.lstrip("/"))


# ─── Template Card ────────────────────────────────────────────────────────────

_CARD_STYLE = """
QFrame#MarketplaceTemplateCard {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
}
QFrame#MarketplaceTemplateCard:hover {
    border-color: #4f8fff;
}
"""

_INSTALL_BTN_STYLE = (
    "QPushButton { background-color: #0ea5e9; color: white; border: none;"
    " border-radius: 5px; padding: 2px 12px; font-size: 10px; font-weight: 700; }"
    "QPushButton:hover { background-color: #0284c7; }"
    "QPushButton:disabled { background-color: #475569; color: #94a3b8; }"
)

_INSTALLED_BTN_STYLE = (
    "QPushButton { background-color: #334155; color: #cbd5e1; border: 1px solid #475569;"
    " border-radius: 5px; padding: 2px 12px; font-size: 10px; font-weight: 700; }"
    "QPushButton:hover { background-color: #475569; color: #e2e8f0; }"
    "QPushButton:disabled { background-color: #1e293b; color: #64748b; border-color: #334155; }"
)

# Sized for a 4-up grid at typical marketplace content (~1000px+ view ≈ viewport
# after shell chrome). Breakpoints use: n * min + (n-1) * gap (+ reserve).
_CARD_MIN_WIDTH = 180
_GRID_GAP = 12
_COLUMN_WIDTH_RESERVE = 16
_PREVIEW_HEIGHT = 120
# Margins(16) + spacing×4(20) + name(20) + desc(34) + price(18) + bottom(28)
_CARD_CHROME_HEIGHT = 132
_CARD_NATURAL_HEIGHT = _PREVIEW_HEIGHT + _CARD_CHROME_HEIGHT
_GRID_COLUMNS_DESKTOP = 4


class _TemplateCard(QFrame):
    """Template card with fixed-height preview, metadata, kind badge, and install."""

    install_clicked = Signal(str)  # item_id

    def __init__(
        self,
        item: CatalogItem,
        *,
        is_installed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item_id = item.id
        self._preview_url = item.preview_url or ""
        self._preview_pixmap: QPixmap | None = None
        self._is_installed = bool(is_installed)
        self._installing = False
        self.setObjectName("MarketplaceTemplateCard")
        self.setStyleSheet(_CARD_STYLE)
        self.setFixedHeight(_CARD_NATURAL_HEIGHT)
        self.setMinimumWidth(_CARD_MIN_WIDTH)
        # Expand horizontally to fill the column; never grow vertically.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        self._preview_label = QLabel()
        self._preview_label.setFixedHeight(_PREVIEW_HEIGHT)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preview_label.setStyleSheet(
            "background-color: #0f172a; border-radius: 6px; color: #64748b; font-size: 11px;"
        )
        if self._preview_url:
            self._preview_label.setText("Loading…")
        else:
            self._preview_label.setText("No Preview")
        layout.addWidget(self._preview_label, stretch=0)

        self._name_label = QLabel(item.name)
        self._name_label.setStyleSheet("font-weight: 700; font-size: 12px; color: #e2e8f0;")
        self._name_label.setWordWrap(False)
        self._name_label.setFixedHeight(20)
        layout.addWidget(self._name_label)

        desc_text = truncate_description(item.description, 72)
        self._desc_label = QLabel(desc_text)
        self._desc_label.setStyleSheet("font-size: 10px; color: #94a3b8;")
        self._desc_label.setWordWrap(True)
        self._desc_label.setFixedHeight(34)
        layout.addWidget(self._desc_label)

        if item.price == 0.0:
            price_text = "FREE"
            price_style = "font-size: 11px; font-weight: 700; color: #4ade80;"
        else:
            price_text = f"${item.price:.2f}"
            price_style = "font-size: 11px; font-weight: 700; color: #fbbf24;"
        self._price_label = QLabel(price_text)
        self._price_label.setStyleSheet(price_style)
        self._price_label.setFixedHeight(18)
        layout.addWidget(self._price_label)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(6)

        kind_colors = {
            "video": ("#1d4ed8", "#bfdbfe"),
            "reel": ("#7c3aed", "#ddd6fe"),
        }
        kind_key = (item.kind or "").strip().lower()
        bg_color, text_color = kind_colors.get(kind_key, ("#334155", "#94a3b8"))
        badge_text = kind_key.upper() if kind_key else "TEMPLATE"
        self._kind_badge = QLabel(badge_text)
        self._kind_badge.setFixedHeight(26)
        self._kind_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kind_badge.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; border-radius: 5px;"
            f" padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        bottom.addWidget(self._kind_badge, stretch=0)

        bottom.addStretch(1)

        self._install_btn = QPushButton()
        self._install_btn.setFixedHeight(26)
        self._install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_btn.setMinimumWidth(72)
        self._install_btn.clicked.connect(self._on_install_clicked)
        self._apply_install_button_state()
        bottom.addWidget(self._install_btn, stretch=0)

        layout.addLayout(bottom)

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt override
        super().resizeEvent(event)
        self._apply_preview_pixmap()

    @property
    def preview_url(self) -> str:
        return self._preview_url

    def apply_preview_bytes(self, data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(data))
        if pixmap.isNull():
            self.show_empty_preview()
            return
        self._preview_pixmap = pixmap
        self._apply_preview_pixmap()

    def _apply_preview_pixmap(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        target = self._preview_label.size()
        if target.width() < 8 or target.height() < 8:
            return
        scaled = self._preview_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - target.width()) // 2)
        y = max(0, (scaled.height() - target.height()) // 2)
        cropped = scaled.copy(
            x, y, min(target.width(), scaled.width()), min(target.height(), scaled.height())
        )
        self._preview_label.setPixmap(cropped)
        self._preview_label.setText("")

    def show_empty_preview(self) -> None:
        self._preview_pixmap = None
        self._preview_label.clear()
        self._preview_label.setText("No Preview")

    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def is_installed(self) -> bool:
        return self._is_installed

    def set_installed(self, installed: bool) -> None:
        self._is_installed = bool(installed)
        if not self._installing:
            self._apply_install_button_state()

    def set_installing(self, in_progress: bool) -> None:
        self._installing = bool(in_progress)
        if self._installing:
            self._install_btn.setEnabled(False)
            self._install_btn.setText("…")
        else:
            self._apply_install_button_state()

    def _apply_install_button_state(self) -> None:
        if self._is_installed:
            self._install_btn.setText("Installed")
            self._install_btn.setEnabled(True)
            self._install_btn.setStyleSheet(_INSTALLED_BTN_STYLE)
            self._install_btn.setToolTip("Already installed — click to reinstall")
        else:
            self._install_btn.setText("Install")
            self._install_btn.setEnabled(True)
            self._install_btn.setStyleSheet(_INSTALL_BTN_STYLE)
            self._install_btn.setToolTip("")

    def _on_install_clicked(self) -> None:
        self.install_clicked.emit(self._item_id)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return QSize(_CARD_MIN_WIDTH, _CARD_NATURAL_HEIGHT)


# ─── Marketplace View ─────────────────────────────────────────────────────────


_DEBOUNCE_MS = 400


class MarketplaceView(QWidget):
    """Marketplace page with paginated card grid, filter controls, and state management.

    Signals:
        kind_filter_changed(object): Emitted when kind filter changes (str or None).
        search_changed(str): Emitted after debounce when search text changes.
        page_changed(int): Emitted when user navigates pages.
        install_requested(str): Emitted when user clicks Install on a card.
        retry_requested(): Emitted when user clicks Retry in error state.
    """

    kind_filter_changed = Signal(object)
    search_changed = Signal(str)
    page_changed = Signal(int)
    install_requested = Signal(str)
    retry_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        api_base_url: str = "",
        preview_loader: MarketplacePreviewLoader | None = None,
    ) -> None:
        super().__init__(parent)
        self._api_base_url = api_base_url or "http://localhost:8000/api/v3"
        self._preview_loader = preview_loader or MarketplacePreviewLoader(parent=self)
        self._preview_generation = 0
        self._current_page = 1
        self._total_pages = 1
        self._cards: dict[str, _TemplateCard] = {}
        self._items: list[CatalogItem] = []
        self._installed_ids: set[str] = set()
        self._grid_columns = _GRID_COLUMNS_DESKTOP

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(_DEBOUNCE_MS)
        self._search_debounce_timer.timeout.connect(self._emit_search)

        self._preview_loader.loaded.connect(self._on_preview_loaded)
        self._preview_loader.failed.connect(self._on_preview_failed)

        self._build_ui()

    # ─── Public Methods ───────────────────────────────────────────────────

    def begin_preview_generation(self) -> int:
        """Invalidate in-flight preview loads (call before a new catalog fetch)."""
        self._preview_generation = self._preview_loader.begin_generation()
        return self._preview_generation

    def set_catalog(
        self,
        items: list[CatalogItem],
        total: int,
        page: int,
        page_size: int,
        *,
        installed_ids: set[str] | frozenset[str] | None = None,
    ) -> None:
        """Update the grid with new catalog data."""
        self._current_page = page
        self._total_pages = max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
        self._items = list(items)
        self._installed_ids = {str(item_id) for item_id in (installed_ids or ()) if str(item_id)}

        self._clear_grid()

        if not items:
            self._show_state("empty")
            self._update_pagination()
            return

        self._show_state("content")
        self._populate_grid()
        self._update_pagination()

    def set_item_installed(self, item_id: str, installed: bool = True) -> None:
        """Update installed button state for one catalog card after install/reinstall."""
        key = str(item_id or "").strip()
        if not key:
            return
        if installed:
            self._installed_ids.add(key)
        else:
            self._installed_ids.discard(key)
        card = self._cards.get(key)
        if card is not None:
            card.set_installed(installed)

    def set_loading(self, loading: bool) -> None:
        """Toggle loading state."""
        if loading:
            self._show_state("loading")

    def set_error(self, message: str) -> None:
        """Show error state with message and retry button."""
        self._error_message_label.setText(message)
        self._show_state("error")

    def set_install_progress(self, item_id: str, in_progress: bool) -> None:
        """Toggle install button state for a specific card."""
        card = self._cards.get(item_id)
        if card is not None:
            card.set_installing(in_progress)

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt override
        super().resizeEvent(event)
        if not self._items:
            return
        columns = self._columns_for_width(self._scroll_area.viewport().width())
        if columns != self._grid_columns:
            self._grid_columns = columns
            self._reflow_grid()

    # ─── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        root.addLayout(self._build_filter_bar())

        self._main_card = QFrame()
        self._main_card.setObjectName("MarketplaceMainCard")
        self._main_card.setStyleSheet(
            "QFrame#MarketplaceMainCard {"
            " background-color: #0f172a;"
            " border: 1px solid #1e293b;"
            " border-radius: 8px;"
            "}"
        )
        card_layout = QVBoxLayout(self._main_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        self._loading_label = QLabel("Loading marketplace...")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet("color: #64748b; font-size: 13px; padding: 40px;")
        card_layout.addWidget(self._loading_label)

        self._error_widget = self._build_error_widget()
        card_layout.addWidget(self._error_widget)

        self._empty_label = QLabel("No templates found")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #64748b; font-size: 13px; padding: 40px;")
        card_layout.addWidget(self._empty_label)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(_GRID_GAP)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._scroll_area.setWidget(self._grid_widget)
        card_layout.addWidget(self._scroll_area, stretch=1)

        root.addWidget(self._main_card, stretch=1)
        root.addLayout(self._build_pagination())
        self._show_state("loading")

    def _build_filter_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._filter_buttons: dict[str | None, QPushButton] = {}
        for label, kind_value in [("All", None), ("Video", "video"), ("Reel", "reel")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(kind_value is None)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;"
                " border-radius: 6px; padding: 4px 14px; font-size: 11px; }"
                "QPushButton:checked { background-color: #0ea5e9; color: white; border-color: #0ea5e9; }"
                "QPushButton:hover { border-color: #4f8fff; }"
            )
            btn.clicked.connect(lambda checked=False, k=kind_value: self._on_filter_clicked(k))
            self._filter_buttons[kind_value] = btn
            bar.addWidget(btn)

        bar.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search templates...")
        self._search_input.setFixedWidth(240)
        self._search_input.setFixedHeight(30)
        self._search_input.setStyleSheet(
            "QLineEdit { background-color: #1e293b; color: #e2e8f0; border: 1px solid #334155;"
            " border-radius: 6px; padding: 4px 10px; font-size: 11px; }"
            "QLineEdit:focus { border-color: #0ea5e9; }"
        )
        self._search_input.textChanged.connect(self._on_search_text_changed)
        bar.addWidget(self._search_input)

        return bar

    def _build_error_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        self._error_message_label = QLabel("An error occurred")
        self._error_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_message_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self._error_message_label.setWordWrap(True)
        layout.addWidget(self._error_message_label)

        retry_btn = QPushButton("Retry")
        retry_btn.setFixedWidth(80)
        retry_btn.clicked.connect(self.retry_requested.emit)
        layout.addWidget(retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def _build_pagination(self) -> QHBoxLayout:
        pagination = QHBoxLayout()
        pagination.setSpacing(8)

        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setFixedHeight(30)
        self._prev_btn.clicked.connect(self._on_prev_page)
        pagination.addWidget(self._prev_btn)

        pagination.addStretch()

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination.addWidget(self._page_label)

        pagination.addStretch()

        self._next_btn = QPushButton("Next")
        self._next_btn.setFixedHeight(30)
        self._next_btn.clicked.connect(self._on_next_page)
        pagination.addWidget(self._next_btn)

        return pagination

    # ─── State Management ─────────────────────────────────────────────────

    def _show_state(self, state: str) -> None:
        self._loading_label.setVisible(state == "loading")
        self._error_widget.setVisible(state == "error")
        self._empty_label.setVisible(state == "empty")
        show_content = state == "content"
        self._scroll_area.setVisible(show_content)
        # Keep pagination visible for empty results so page controls stay consistent.
        show_pager = state in ("content", "empty")
        self._prev_btn.setVisible(show_pager)
        self._next_btn.setVisible(show_pager)
        self._page_label.setVisible(show_pager)

    # ─── Grid Management ──────────────────────────────────────────────────

    def _columns_for_width(self, available_width: int) -> int:
        """Pick 4 / 3 / 2 / 1 columns based on viewport width (primary target: 4)."""
        gap = self._grid_layout.spacing()
        usable = max(0, available_width - _COLUMN_WIDTH_RESERVE)
        for columns in range(_GRID_COLUMNS_DESKTOP, 0, -1):
            needed = columns * _CARD_MIN_WIDTH + max(0, columns - 1) * gap
            if usable >= needed:
                return columns
        return 1

    def _populate_grid(self) -> None:
        self._grid_columns = self._columns_for_width(self._scroll_area.viewport().width())
        for col in range(_GRID_COLUMNS_DESKTOP):
            self._grid_layout.setColumnStretch(col, 1 if col < self._grid_columns else 0)
            self._grid_layout.setColumnMinimumWidth(
                col, _CARD_MIN_WIDTH if col < self._grid_columns else 0
            )

        for idx, item in enumerate(self._items):
            card = _TemplateCard(
                item,
                is_installed=item.id in self._installed_ids,
                parent=self._grid_widget,
            )
            card.install_clicked.connect(self._on_card_install)
            row = idx // self._grid_columns
            col = idx % self._grid_columns
            self._grid_layout.addWidget(
                card,
                row,
                col,
                Qt.AlignmentFlag.AlignTop,
            )
            self._grid_layout.setRowStretch(row, 0)
            self._cards[item.id] = card
            if item.preview_url:
                url = resolve_marketplace_asset_url(self._api_base_url, item.preview_url)
                self._preview_loader.request(item.id, url, self._preview_generation)

        # Absorb leftover vertical space below the last row so cards do not stretch.
        rows_used = max(1, (len(self._items) + self._grid_columns - 1) // self._grid_columns)
        self._grid_layout.setRowStretch(rows_used, 1)

    def _on_preview_loaded(self, item_id: str, data: bytes, generation: int) -> None:
        if generation != self._preview_generation:
            return
        card = self._cards.get(item_id)
        if card is not None:
            card.apply_preview_bytes(data)

    def _on_preview_failed(self, item_id: str, generation: int) -> None:
        if generation != self._preview_generation:
            return
        card = self._cards.get(item_id)
        if card is not None:
            card.show_empty_preview()

    def _reflow_grid(self) -> None:
        """Move existing cards into a new column count without re-fetching previews."""
        cards = [self._cards[item.id] for item in self._items if item.id in self._cards]
        if not cards:
            return

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                self._grid_layout.removeWidget(widget)

        for col in range(_GRID_COLUMNS_DESKTOP):
            self._grid_layout.setColumnStretch(col, 1 if col < self._grid_columns else 0)
            self._grid_layout.setColumnMinimumWidth(
                col, _CARD_MIN_WIDTH if col < self._grid_columns else 0
            )

        for idx, card in enumerate(cards):
            row = idx // self._grid_columns
            col = idx % self._grid_columns
            self._grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop)
            self._grid_layout.setRowStretch(row, 0)

        rows_used = max(1, (len(cards) + self._grid_columns - 1) // self._grid_columns)
        self._grid_layout.setRowStretch(rows_used, 1)

    def _clear_grid(self) -> None:
        self._cards.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ─── Pagination ───────────────────────────────────────────────────────

    def _update_pagination(self) -> None:
        self._page_label.setText(f"Page {self._current_page} of {self._total_pages}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    def _on_prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self.page_changed.emit(self._current_page)

    def _on_next_page(self) -> None:
        if self._current_page < self._total_pages:
            self._current_page += 1
            self.page_changed.emit(self._current_page)

    # ─── Filter Handlers ──────────────────────────────────────────────────

    def _on_filter_clicked(self, kind: str | None) -> None:
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == kind)
        self.kind_filter_changed.emit(kind)

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_debounce_timer.start()

    def _emit_search(self) -> None:
        self.search_changed.emit(self._search_input.text())

    # ─── Install Handler ──────────────────────────────────────────────────

    def _on_card_install(self, item_id: str) -> None:
        self.install_requested.emit(item_id)
