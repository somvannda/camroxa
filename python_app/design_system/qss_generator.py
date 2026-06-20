"""QSS stylesheet generator from design tokens.

Produces a valid, application-wide Qt Style Sheet string from a ThemeTokens
instance. The generated QSS covers all 14 base widget types, Style_Role
property selectors, and pseudo-state rules for interactive widgets.
"""

from __future__ import annotations

from python_app.design_system.tokens import ThemeTokens


class QSSGenerator:
    """Produces a valid QSS string from ThemeTokens."""

    def __init__(self, tokens: ThemeTokens, *, arrow_urls: dict[str, str] | None = None) -> None:
        self._tokens = tokens
        self._arrow_urls = arrow_urls or {}

    def generate(self) -> str:
        """Generate the complete application-wide QSS string."""
        sections = [
            self._base_widgets(),
            self._buttons(),
            self._inputs(),
            self._lists_and_tables(),
            self._scrollbars(),
            self._sliders(),
            self._tabs(),
            self._menus(),
            self._checkboxes(),
            self._progress_bars(),
            self._style_roles(),
            self._app_panels(),
            self._app_labels(),
            self._app_nav(),
            self._tooltips(),
            self._enhanced_tables(),
            self._enhanced_inputs(),
            self._enhanced_progress(),
            self._ghost_outlined(),
            self._title_bar(),
            self._sidebar_nav(),
            self._greeting_bar(),
            self._login_shell(),
            self._view_specific_roles(),
            self._gradient_buttons(),
        ]
        return "\n\n".join(sections)

    def _base_widgets(self) -> str:
        """Generate base widget styling rules."""
        c = self._tokens.colors
        t = self._tokens.typography
        s = self._tokens.spacing
        sh = self._tokens.shape

        return (
            f"QMainWindow {{\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f"QWidget {{\n"
            f"    background: transparent;\n"
            f"    color: {c.text_primary};\n"
            f'    font-family: "{t.font_family}";\n'
            f"    font-size: {t.size_body}px;\n"
            f"}}\n\n"
            f"QLabel {{\n"
            f"    color: {c.text_primary};\n"
            f"    background: transparent;\n"
            f"}}"
        )

    def _buttons(self) -> str:
        """Generate button styling with hover, pressed, disabled states."""
        c = self._tokens.colors
        sh = self._tokens.shape

        return (
            f"QPushButton {{\n"
            f"    min-height: 30px;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    border: {sh.border_width_thin}px solid {c.accent};\n"
            f"    background-color: {c.accent};\n"
            f"    color: {c.text_primary};\n"
            f"    padding: 0 {self._tokens.spacing.padding_md}px;\n"
            f"    font-size: {self._tokens.typography.size_body}px;\n"
            f"    font-weight: {self._tokens.typography.weight_medium};\n"
            f"}}\n\n"
            f"QPushButton:hover {{\n"
            f"    background-color: {c.accent_hover};\n"
            f"}}\n\n"
            f"QPushButton:pressed {{\n"
            f"    background-color: {c.accent_pressed};\n"
            f"}}\n\n"
            f"QPushButton:disabled {{\n"
            f"    background-color: {c.surface_overlay};\n"
            f"    border: {sh.border_width_thin}px solid {c.border};\n"
            f"    color: {c.text_muted};\n"
            f"}}\n\n"
            f"QPushButton:focus {{\n"
            f"    border: {sh.border_width_medium}px solid {c.focus_ring};\n"
            f"}}"
        )

    def _inputs(self) -> str:
        """Generate input field styling for QLineEdit, QComboBox, QSpinBox, QTextEdit."""
        c = self._tokens.colors
        sh = self._tokens.shape
        s = self._tokens.spacing

        return (
            f"QLineEdit, QComboBox, QTextEdit, QSpinBox {{\n"
            f"    min-height: 30px;\n"
            f"    border-radius: {sh.radius_md - 2}px;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    padding: 0 {s.padding_md}px;\n"
            f"    background: {c.surface_overlay};\n"
            f"    color: {c.text_primary};\n"
            f"    selection-background-color: {c.selection};\n"
            f"}}\n\n"
            f"QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus {{\n"
            f"    border: {sh.border_width_medium}px solid {c.focus_ring};\n"
            f"}}\n\n"
            f"QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled, QSpinBox:disabled {{\n"
            f"    color: {c.text_muted};\n"
            f"    background: {c.surface_sunken};\n"
            f"}}\n\n"
            # Card variant
            f'QLineEdit[uiField="card"], QComboBox[uiField="card"], '
            f'QTextEdit[uiField="card"], QSpinBox[uiField="card"] {{\n'
            f"    background: transparent;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"}}\n\n"
            # Standalone variant
            f'QLineEdit[uiField="standalone"], QComboBox[uiField="standalone"], '
            f'QTextEdit[uiField="standalone"], QSpinBox[uiField="standalone"] {{\n'
            f"    background: {c.surface_overlay};\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"}}\n\n"
            # SpinBox buttons
            f"QSpinBox {{\n"
            f"    padding-right: 30px;\n"
            f"}}\n\n"
            f"QSpinBox::up-button {{\n"
            f"    subcontrol-origin: border;\n"
            f"    subcontrol-position: top right;\n"
            f"    width: 24px;\n"
            f"    border-left: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    border-bottom: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    background-color: {c.surface_raised};\n"
            f"    border-top-right-radius: {sh.radius_md - 2}px;\n"
            f"}}\n\n"
            f"QSpinBox::down-button {{\n"
            f"    subcontrol-origin: border;\n"
            f"    subcontrol-position: bottom right;\n"
            f"    width: 24px;\n"
            f"    border-left: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    background-color: {c.surface_raised};\n"
            f"    border-bottom-right-radius: {sh.radius_md - 2}px;\n"
            f"}}\n\n"
            f"QSpinBox::up-button:hover, QSpinBox::down-button:hover {{\n"
            f"    background-color: {c.surface_overlay};\n"
            f"}}\n\n"
            f"QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{\n"
            f"    background-color: {c.surface_sunken};\n"
            f"}}\n\n"
            # ComboBox dropdown
            f"QComboBox::drop-down {{\n"
            f"    width: 20px;\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"    subcontrol-origin: padding;\n"
            f"    subcontrol-position: top right;\n"
            f"}}\n\n"
            + (
                f'QComboBox::down-arrow {{ image: url("{self._arrow_urls["combo"]}"); width: 10px; height: 10px; }}\n\n'
                f'QSpinBox::up-arrow {{ image: url("{self._arrow_urls.get("spin_up", self._arrow_urls["combo"])}"); width: 10px; height: 10px; }}\n\n'
                f'QSpinBox::down-arrow {{ image: url("{self._arrow_urls.get("spin_down", self._arrow_urls["combo"])}"); width: 10px; height: 10px; }}\n\n'
                if "combo" in self._arrow_urls else ""
            )
            + f"QComboBox QAbstractItemView {{\n"
            f"    background: {c.surface_overlay};\n"
            f"    color: {c.text_primary};\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    selection-background-color: {c.selection};\n"
            f"    selection-color: {c.text_primary};\n"
            f"    outline: none;\n"
            f"    padding: {s.padding_sm}px;\n"
            f"}}\n\n"
            f"QComboBox QAbstractItemView::item {{\n"
            f"    min-height: 24px;\n"
            f"    padding: {s.padding_sm}px {s.padding_md}px;\n"
            f"    border-radius: {sh.radius_sm}px;\n"
            f"    margin: 1px 2px;\n"
            f"}}\n\n"
            f"QComboBox QAbstractItemView::item:selected {{\n"
            f"    background: {c.selection};\n"
            f"    color: {c.text_primary};\n"
            f"}}"
        )

    def _lists_and_tables(self) -> str:
        """Generate table and list widget styling with hover rows, themed headers."""
        c = self._tokens.colors
        sh = self._tokens.shape
        s = self._tokens.spacing
        t = self._tokens.typography

        return (
            # Table widget
            f"QTableWidget {{\n"
            f"    background: transparent;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    border-radius: {sh.radius_md - 2}px;\n"
            f"    gridline-color: {c.separator};\n"
            f"    color: {c.text_primary};\n"
            f"    selection-background-color: {c.selection};\n"
            f"    selection-color: {c.text_primary};\n"
            f"}}\n\n"
            f"QTableWidget::item {{\n"
            f"    padding: {s.padding_md}px;\n"
            f"}}\n\n"
            f"QTableWidget::item:hover {{\n"
            f"    background: {c.surface_overlay};\n"
            f"}}\n\n"
            # Header styling
            f"QHeaderView::section {{\n"
            f"    background: {c.surface_sunken};\n"
            f"    color: {c.text_muted};\n"
            f"    border: none;\n"
            f"    border-bottom: {sh.border_width_thin}px solid {c.separator};\n"
            f"    padding: {s.padding_md}px;\n"
            f"    font-size: {t.size_subtitle}px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            # List widget
            f"QListWidget {{\n"
            f"    border-radius: {sh.radius_md - 2}px;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    padding: 2px;\n"
            f"    outline: none;\n"
            f"}}\n\n"
            f'QListWidget[uiField="card"] {{\n'
            f"    background: transparent;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"}}\n\n"
            f'QListWidget[uiField="standalone"] {{\n'
            f"    background: {c.surface_overlay};\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"}}\n\n"
            f"QListWidget::item {{\n"
            f"    padding: {s.padding_md}px {s.padding_md}px;\n"
            f"    margin: 1px 0;\n"
            f"    border-radius: {sh.radius_sm + 1}px;\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f"QListWidget::item:hover {{\n"
            f"    background: {c.surface_overlay};\n"
            f"}}\n\n"
            f"QListWidget::item:selected {{\n"
            f"    background: {c.accent};\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f"QListWidget::item:disabled {{\n"
            f"    color: {c.text_muted};\n"
            f"    background: transparent;\n"
            f"}}"
        )

    def _scrollbars(self) -> str:
        """Generate scrollbar styling with track and handle."""
        c = self._tokens.colors
        sh = self._tokens.shape

        return (
            f"QScrollArea {{\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f"QScrollBar:vertical {{\n"
            f"    width: 8px;\n"
            f"    background: {c.surface_sunken};\n"
            f"    margin: 2px;\n"
            f"    border-radius: {sh.radius_sm}px;\n"
            f"}}\n\n"
            f"QScrollBar::handle:vertical {{\n"
            f"    background: {c.border_strong};\n"
            f"    border-radius: {sh.radius_sm}px;\n"
            f"    min-height: 24px;\n"
            f"}}\n\n"
            f"QScrollBar::handle:vertical:hover {{\n"
            f"    background: {c.accent};\n"
            f"}}\n\n"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{\n"
            f"    height: 0px;\n"
            f"}}\n\n"
            f"QScrollBar:horizontal {{\n"
            f"    height: 8px;\n"
            f"    background: {c.surface_sunken};\n"
            f"    margin: 2px;\n"
            f"    border-radius: {sh.radius_sm}px;\n"
            f"}}\n\n"
            f"QScrollBar::handle:horizontal {{\n"
            f"    background: {c.border_strong};\n"
            f"    border-radius: {sh.radius_sm}px;\n"
            f"    min-width: 24px;\n"
            f"}}\n\n"
            f"QScrollBar::handle:horizontal:hover {{\n"
            f"    background: {c.accent};\n"
            f"}}\n\n"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{\n"
            f"    width: 0px;\n"
            f"}}"
        )

    def _sliders(self) -> str:
        """Generate slider groove, handle, and sub-page accent fill."""
        c = self._tokens.colors
        sh = self._tokens.shape

        return (
            f"QSlider::groove:horizontal {{\n"
            f"    height: 4px;\n"
            f"    border-radius: 2px;\n"
            f"    background: {c.border_strong};\n"
            f"}}\n\n"
            f"QSlider::handle:horizontal {{\n"
            f"    background: {c.accent};\n"
            f"    width: 14px;\n"
            f"    height: 14px;\n"
            f"    margin: -6px 0;\n"
            f"    border-radius: 7px;\n"
            f"    border: {sh.border_width_thin}px solid {c.accent_hover};\n"
            f"}}\n\n"
            f"QSlider::handle:horizontal:hover {{\n"
            f"    background: {c.accent_hover};\n"
            f"}}\n\n"
            f"QSlider::handle:horizontal:pressed {{\n"
            f"    background: {c.accent_pressed};\n"
            f"}}\n\n"
            f"QSlider::sub-page:horizontal {{\n"
            f"    background: {c.accent};\n"
            f"    border-radius: 2px;\n"
            f"}}\n\n"
            f"QSlider::groove:vertical {{\n"
            f"    width: 4px;\n"
            f"    border-radius: 2px;\n"
            f"    background: {c.border_strong};\n"
            f"}}\n\n"
            f"QSlider::handle:vertical {{\n"
            f"    background: {c.accent};\n"
            f"    width: 14px;\n"
            f"    height: 14px;\n"
            f"    margin: 0 -6px;\n"
            f"    border-radius: 7px;\n"
            f"    border: {sh.border_width_thin}px solid {c.accent_hover};\n"
            f"}}\n\n"
            f"QSlider::handle:vertical:hover {{\n"
            f"    background: {c.accent_hover};\n"
            f"}}\n\n"
            f"QSlider::handle:vertical:pressed {{\n"
            f"    background: {c.accent_pressed};\n"
            f"}}\n\n"
            f"QSlider:disabled {{\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f"QSlider::groove:horizontal:disabled {{\n"
            f"    background: {c.border};\n"
            f"}}\n\n"
            f"QSlider::handle:horizontal:disabled {{\n"
            f"    background: {c.text_muted};\n"
            f"    border: {sh.border_width_thin}px solid {c.border};\n"
            f"}}"
        )

    def _tabs(self) -> str:
        """Generate tab widget styling."""
        c = self._tokens.colors
        sh = self._tokens.shape
        s = self._tokens.spacing
        t = self._tokens.typography

        return (
            f"QTabWidget::pane {{\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f"QTabBar::tab {{\n"
            f"    background: {c.surface_raised};\n"
            f"    color: {c.text_secondary};\n"
            f"    padding: {s.padding_md}px {s.padding_lg}px;\n"
            f"    min-width: 54px;\n"
            f"    border: none;\n"
            f"    border-radius: {sh.radius_md - 2}px;\n"
            f"    margin-right: 2px;\n"
            f"    font-size: {t.size_body}px;\n"
            f"    font-weight: {t.weight_medium};\n"
            f"}}\n\n"
            f"QTabBar::tab:selected {{\n"
            f"    background: {c.accent};\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f"QTabBar::tab:hover:!selected {{\n"
            f"    background: {c.surface_overlay};\n"
            f"}}\n\n"
            f"QTabBar::tab:disabled {{\n"
            f"    color: {c.text_muted};\n"
            f"    background: {c.surface_sunken};\n"
            f"}}"
        )

    def _menus(self) -> str:
        """Generate menu styling with glass-morphism border and accent selection."""
        c = self._tokens.colors
        sh = self._tokens.shape
        s = self._tokens.spacing

        return (
            f"QMenu {{\n"
            f"    background: {c.surface_overlay};\n"
            f"    color: {c.text_primary};\n"
            f"    border: 1px solid {c.border_glass};\n"
            f"    border-radius: 8px;\n"
            f"}}\n\n"
            f"QMenu::item {{\n"
            f"    padding: {s.padding_md}px {s.padding_lg}px;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f"QMenu::item:selected {{\n"
            f"    background: {c.accent}26;\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f"QMenu::item:disabled {{\n"
            f"    color: {c.text_muted};\n"
            f"}}\n\n"
            f"QMenu::separator {{\n"
            f"    height: 1px;\n"
            f"    background: {c.separator}80;\n"
            f"    margin: 4px 8px;\n"
            f"}}"
        )

    def _checkboxes(self) -> str:
        """Generate checkbox with themed background and check indicator."""
        c = self._tokens.colors
        sh = self._tokens.shape

        return (
            f"QCheckBox {{\n"
            f"    spacing: {self._tokens.spacing.padding_md}px;\n"
            f"}}\n\n"
            f"QCheckBox::indicator {{\n"
            f"    width: 14px;\n"
            f"    height: 14px;\n"
            f"    border-radius: 7px;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    background: {c.surface_overlay};\n"
            f"}}\n\n"
            f"QCheckBox::indicator:checked {{\n"
            f"    background: {c.accent};\n"
            f"    border: {sh.border_width_thin}px solid {c.accent_hover};\n"
            f"}}\n\n"
            f"QCheckBox::indicator:hover {{\n"
            f"    border: {sh.border_width_thin}px solid {c.accent};\n"
            f"}}\n\n"
            f"QCheckBox:disabled {{\n"
            f"    color: {c.text_muted};\n"
            f"}}\n\n"
            f"QCheckBox::indicator:disabled {{\n"
            f"    background: {c.surface_sunken};\n"
            f"    border: {sh.border_width_thin}px solid {c.border};\n"
            f"}}"
        )

    def _progress_bars(self) -> str:
        """Generate progress bar with accent chunk color."""
        c = self._tokens.colors
        sh = self._tokens.shape
        t = self._tokens.typography

        return (
            f"QProgressBar {{\n"
            f"    background: {c.surface_sunken};\n"
            f"    border: {sh.border_width_thin}px solid {c.border};\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    color: {c.text_primary};\n"
            f"    text-align: center;\n"
            f"    font-size: {t.size_caption + 1}px;\n"
            f"}}\n\n"
            f"QProgressBar::chunk {{\n"
            f"    background: {c.accent};\n"
            f"    border-radius: {sh.radius_md - 1}px;\n"
            f"}}"
        )

    def _style_roles(self) -> str:
        """Generate property-selector rules for Style_Roles."""
        c = self._tokens.colors
        sh = self._tokens.shape
        t = self._tokens.typography
        s = self._tokens.spacing

        return (
            # Primary button role (green CTA like template)
            f'QPushButton[uiRole="primary"] {{\n'
            f"    background-color: {c.success};\n"
            f"    border: {sh.border_width_thin}px solid {c.success_hover};\n"
            f"    color: #ffffff;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="primary"]:hover {{\n'
            f"    background-color: {c.success_hover};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="primary"]:pressed {{\n'
            f"    background-color: {c.success};\n"
            f"}}\n\n"
            # Secondary button role (dark outlined)
            f'QPushButton[uiRole="secondary"] {{\n'
            f"    background-color: transparent;\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="secondary"]:hover {{\n'
            f"    background-color: rgba(255, 255, 255, 0.05);\n"
            f"    border-color: {c.text_muted};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="secondary"]:pressed {{\n'
            f"    background-color: rgba(255, 255, 255, 0.08);\n"
            f"}}\n\n"
            # Danger button role
            f'QPushButton[uiRole="danger"] {{\n'
            f"    background-color: {c.danger};\n"
            f"    border: {sh.border_width_thin}px solid {c.danger_hover};\n"
            f"    color: {c.text_primary};\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="danger"]:hover {{\n'
            f"    background-color: {c.danger_hover};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="danger"]:pressed {{\n'
            f"    background-color: {c.danger};\n"
            f"}}\n\n"
            # Success button role
            f'QPushButton[uiRole="success"] {{\n'
            f"    background-color: {c.success};\n"
            f"    border: {sh.border_width_thin}px solid {c.success_hover};\n"
            f"    color: {c.text_primary};\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="success"]:hover {{\n'
            f"    background-color: {c.success_hover};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="success"]:pressed {{\n'
            f"    background-color: {c.success};\n"
            f"}}\n\n"
            # Toggle button role
            f'QPushButton[uiRole="toggle"] {{\n'
            f"    min-height: 20px;\n"
            f"    max-height: 20px;\n"
            f"    min-width: 42px;\n"
            f"    max-width: 42px;\n"
            f"    border-radius: 10px;\n"
            f"    padding: 0 {s.padding_md}px;\n"
            f"    background-color: {c.surface_sunken};\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    color: {c.text_muted};\n"
            f"    font-size: {t.size_caption}px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="toggle"]:checked {{\n'
            f"    background-color: {c.accent};\n"
            f"    border: {sh.border_width_thin}px solid {c.accent_hover};\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="toggle"]:hover {{\n'
            f"    background-color: {c.surface_overlay};\n"
            f"}}\n\n"
            # Transport button role
            f'QPushButton[uiRole="transport"] {{\n'
            f"    min-height: 26px;\n"
            f"    background-color: {c.surface_raised};\n"
            f"    border: {sh.border_width_thin}px solid {c.border_strong};\n"
            f"    color: {c.text_primary};\n"
            f"    padding: 0 {s.padding_md}px;\n"
            f"    font-size: {t.size_caption + 1}px;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="transport"]:hover {{\n'
            f"    background-color: {c.surface_overlay};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="transport"]:pressed {{\n'
            f"    background-color: {c.surface_sunken};\n"
            f"}}\n\n"
            # Warning button role (uses warning tokens)
            f'QPushButton[uiRole="warning"] {{\n'
            f"    background-color: {c.warning};\n"
            f"    border: {sh.border_width_thin}px solid {c.warning_hover};\n"
            f"    color: {c.text_primary};\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="warning"]:hover {{\n'
            f"    background-color: {c.warning_hover};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="warning"]:pressed {{\n'
            f"    background-color: {c.warning};\n"
            f"}}\n\n"
            # Transport primary button role
            f'QPushButton[uiRole="transportPrimary"] {{\n'
            f"    min-height: 26px;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    background-color: {c.accent};\n"
            f"    border: {sh.border_width_thin}px solid {c.accent_hover};\n"
            f"    color: {c.text_primary};\n"
            f"    padding: 0 {s.padding_lg}px;\n"
            f"    font-size: {t.size_caption + 1}px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="transportPrimary"]:hover {{\n'
            f"    background-color: {c.accent_hover};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="transportPrimary"]:pressed {{\n'
            f"    background-color: {c.accent_pressed};\n"
            f"}}"
        )

    def _app_panels(self) -> str:
        """Generate legacy app-specific panel selectors for backward compatibility."""
        c = self._tokens.colors

        return (
            f'QWidget[uiPanel="appRoot"] {{\n'
            f"    background-color: {c.surface_base};\n"
            f"}}\n\n"
            f'QWidget[uiPanel="appHeader"] {{\n'
            f"    background-color: #0f1827;\n"
            f"    border-bottom: 1px solid {c.border};\n"
            f"}}\n\n"
            f'QWidget[uiPanel="sidebarLeft"] {{\n'
            f"    background: transparent;\n"
            f"    border-right: 1px solid rgba(255, 255, 255, 0.06);\n"
            f"}}\n\n"
            f'QWidget[uiPanel="sidebarRight"] {{\n'
            f"    background: transparent;\n"
            f"    border-left: 1px solid rgba(255, 255, 255, 0.06);\n"
            f"}}\n\n"
            f'QWidget[uiPanel="appNav"] {{\n'
            f"    background-color: transparent;\n"
            f"    border-right: none;\n"
            f"}}\n\n"
            f'QWidget[uiPanel="center"] {{\n'
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QWidget[uiPanel="footer"] {{\n'
            f"    background: transparent;\n"
            f"    border-top: 1px solid rgba(255, 255, 255, 0.06);\n"
            f"}}\n\n"
            f'QWidget[uiPanel="section"] {{\n'
            f"    background: #081028;\n"
            f"    border: 1px solid rgba(255, 255, 255, 0.06);\n"
            f"    border-radius: {self._tokens.shape.radius_md}px;\n"
            f"}}\n\n"
            f'QWidget[uiPanel="softSection"] {{\n'
            f"    background: #081028;\n"
            f"    border: 1px solid rgba(255, 255, 255, 0.04);\n"
            f"    border-radius: {self._tokens.shape.radius_md}px;\n"
            f"}}"
        )

    def _app_labels(self) -> str:
        """Generate legacy app-specific label role selectors."""
        c = self._tokens.colors
        t = self._tokens.typography

        return (
            f'QLabel[uiRole="pageTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 15px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QLabel[uiRole="pageSubtitle"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 11px;\n"
            f"    margin-top: -4px;\n"
            f"}}\n\n"
            f'QLabel[uiRole="sectionTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 13px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QLabel[uiRole="compactTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 12px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QLabel[uiRole="compactSubtitle"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 10px;\n"
            f"    margin-top: -3px;\n"
            f"}}\n\n"
            f'QLabel[uiRole="subheading"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 11px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    margin-top: 2px;\n"
            f"}}\n\n"
            f'QLabel[uiRole="value"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 11px;\n"
            f"}}\n\n"
            f'QLabel[uiRole="metricTitle"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 13px;\n"
            f"    font-weight: 600;\n"
            f"}}\n\n"
            f'QLabel[uiRole="metricValue"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 32px;\n"
            f"    font-weight: 700;\n"
            f"}}\n\n"
            f'QLabel[uiRole="meta"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 10px;\n"
            f"}}\n\n"
            f'QLabel[uiRole="toolbarTitle"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 12px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="statusLabel"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 10px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="statusHeadline"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 12px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="statusStrong"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 11px;\n"
            f"    font-weight: 600;\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="statusMuted"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 11px;\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="statusGood"] {{\n'
            f"    color: #4ade80;\n"
            f"    font-size: 11px;\n"
            f"    font-weight: 600;\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="timer"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 11px;\n"
            f"    font-weight: 600;\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"    padding: 0;\n"
            f"}}\n\n"
            f'QLabel[uiRole="footerText"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 10px;\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QLabel[uiRole="brandTitle"] {{\n'
            f"    color: #f7fbff;\n"
            f"    font-size: 15px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QLabel[uiRole="brandSubtitle"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 10px;\n"
            f"    font-weight: 600;\n"
            f"}}\n\n"
            f'QLabel[uiRole="headerUserName"] {{\n'
            f"    color: #f4f8ff;\n"
            f"    font-size: 11px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QLabel[uiRole="navPageTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 24px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QLabel[uiRole="navPageSubtitle"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 12px;\n"
            f"}}"
        )

    def _app_nav(self) -> str:
        """Generate legacy app navigation button and toolbar selectors."""
        c = self._tokens.colors
        sh = self._tokens.shape

        return (
            f'QPushButton[uiRole="toolbar"] {{\n'
            f"    min-height: 28px;\n"
            f"    background-color: {c.surface_raised};\n"
            f"    border: 1px solid {c.border};\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="compactSecondary"] {{\n'
            f"    min-height: 26px;\n"
            f"    background-color: {c.surface_raised};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    color: {c.text_primary};\n"
            f"    padding: 0 6px;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="tableIcon"] {{\n'
            f"    min-height: 22px;\n"
            f"    max-height: 22px;\n"
            f"    min-width: 22px;\n"
            f"    max-width: 22px;\n"
            f"    padding: 0;\n"
            f"    background-color: {c.surface_raised};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    color: {c.text_primary};\n"
            f"    border-radius: 6px;\n"
            f"}}\n\n"
            f'QToolButton[uiRole="appNavButton"] {{\n'
            f"    background-color: #101927;\n"
            f"    border: 1px solid transparent;\n"
            f"    border-radius: 7px;\n"
            f"    padding: 10px;\n"
            f"}}\n\n"
            f'QToolButton[uiRole="appNavButton"]:hover {{\n'
            f"    background-color: #1f2a3a;\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"}}\n\n"
            f'QToolButton[uiRole="appNavButton"]:checked {{\n'
            f"    background-color: {c.text_muted};\n"
            f"    border: 1px solid transparent;\n"
            f"    border-radius: 7px;\n"
            f"}}\n\n"
            f'QToolButton[uiRole="appNavButton"]:checked:hover {{\n'
            f"    background-color: #9cadc9;\n"
            f"    border: 1px solid transparent;\n"
            f"}}\n\n"
            f'QToolButton[uiRole="headerLogout"] {{\n'
            f"    background-color: transparent;\n"
            f"    border: none;\n"
            f"    border-radius: 8px;\n"
            f"    padding: 4px;\n"
            f"}}\n\n"
            f'QToolButton[uiRole="headerLogout"]:hover {{\n'
            f"    background-color: #1a2638;\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"}}\n\n"
            f'QListWidget[uiRole="trackList"] {{\n'
            f"    font-size: 11px;\n"
            f"}}\n\n"
            f'QListWidget[uiRole="trackList"]::item {{\n'
            f"    padding: 4px 8px;\n"
            f"    margin: 0;\n"
            f"    border-radius: 4px;\n"
            f"    border: 1px solid transparent;\n"
            f"    min-height: 18px;\n"
            f"}}\n\n"
            f'QListWidget[uiRole="trackList"]::item:hover {{\n'
            f"    background: {c.surface_overlay};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"}}\n\n"
            f'QListWidget[uiRole="trackList"]::item:selected {{\n'
            f"    background: {c.accent};\n"
            f"    border: 1px solid {c.accent_hover};\n"
            f"    color: #ffffff;\n"
            f"    font-weight: {self._tokens.typography.weight_bold};\n"
            f"}}"
        )

    def _tooltips(self) -> str:
        """Generate QToolTip styling with overlay background and glass-morphism border."""
        c = self._tokens.colors
        t = self._tokens.typography

        return (
            f"QToolTip {{\n"
            f"    background: {c.surface_overlay};\n"
            f"    border: 1px solid {c.border_glass};\n"
            f"    border-radius: 6px;\n"
            f"    color: {c.text_primary};\n"
            f"    font-size: {t.size_body}px;\n"
            f"    padding: 6px 8px;\n"
            f"}}"
        )

    def _enhanced_tables(self) -> str:
        """Generate enhanced table styling with alternating rows and styled headers."""
        c = self._tokens.colors
        t = self._tokens.typography

        return (
            f"QTableWidget {{\n"
            f"    alternate-background-color: {c.surface_raised};\n"
            f"    background-color: {c.surface_base};\n"
            f"}}\n\n"
            f"QHeaderView::section {{\n"
            f"    color: {c.text_muted};\n"
            f"    font-size: {t.size_caption}px;\n"
            f"    border: none;\n"
            f"    border-bottom: 1px solid {c.separator};\n"
            f"    text-transform: uppercase;\n"
            f"}}"
        )

    def _enhanced_inputs(self) -> str:
        """Generate enhanced input field styling with glass-morphism border and focus glow."""
        c = self._tokens.colors
        t = self._tokens.typography

        return (
            f"QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {{\n"
            f"    background: {c.surface_overlay};\n"
            f"    border: 1px solid {c.border_glass};\n"
            f"    border-radius: 8px;\n"
            f"    min-height: 38px;\n"
            f"    color: {c.text_primary};\n"
            f"    padding: 4px 8px;\n"
            f"}}\n\n"
            f"QLineEdit::placeholder, QTextEdit::placeholder {{\n"
            f"    color: {c.text_muted};\n"
            f"}}\n\n"
            f"QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{\n"
            f"    border: 1px solid {c.accent};\n"
            f"}}\n\n"
            f"QLineEdit:disabled, QTextEdit:disabled {{\n"
            f"    background: {c.surface_sunken};\n"
            f"    color: {c.text_muted};\n"
            f"}}"
        )

    def _enhanced_progress(self) -> str:
        """Generate enhanced progress bar styling with sunken track, accent fill, and caption text."""
        c = self._tokens.colors
        t = self._tokens.typography

        return (
            f"QProgressBar {{\n"
            f"    background: {c.surface_sunken};\n"
            f"    border: none;\n"
            f"    border-radius: 4px;\n"
            f"    height: 7px;\n"
            f"    text-align: center;\n"
            f"    color: {c.text_primary};\n"
            f"    font-size: {t.size_caption}px;\n"
            f"}}\n\n"
            f"QProgressBar::chunk {{\n"
            f"    background: {c.accent};\n"
            f"    border-radius: 4px;\n"
            f"}}"
        )

    def _ghost_outlined(self) -> str:
        """Generate QSS for ghost and outlined button variants via uiRole property selectors."""
        c = self._tokens.colors

        return (
            f'QPushButton[uiRole="ghost"] {{\n'
            f"    background: transparent;\n"
            f"    color: {c.accent};\n"
            f"    border: none;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="ghost"]:hover {{\n'
            f"    background: {c.accent}1a;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="outlined"] {{\n'
            f"    background: transparent;\n"
            f"    color: {c.accent};\n"
            f"    border: 1px solid {c.accent};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="outlined"]:hover {{\n'
            f"    background: {c.accent};\n"
            f"    color: #ffffff;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="ghostDanger"] {{\n'
            f"    background: transparent;\n"
            f"    color: {c.danger};\n"
            f"    border: none;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="ghostDanger"]:hover {{\n'
            f"    background: {c.danger}1a;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="outlinedDanger"] {{\n'
            f"    background: transparent;\n"
            f"    color: {c.danger};\n"
            f"    border: 1px solid {c.danger};\n"
            f"}}\n\n"
            f'QPushButton[uiRole="outlinedDanger"]:hover {{\n'
            f"    background: {c.danger};\n"
            f"    color: #ffffff;\n"
            f"}}"
        )

    def _title_bar(self) -> str:
        """Generate QSS for custom title bar panel, window control buttons, and app title label."""
        c = self._tokens.colors
        t = self._tokens.typography

        return (
            # Title bar container: 40px height, token background, no border
            f'QWidget[uiPanel="titleBar"] {{\n'
            f"    background-color: {c.title_bar_bg};\n"
            f"    min-height: 40px;\n"
            f"    max-height: 40px;\n"
            f"    border: none;\n"
            f"}}\n\n"
            # Window control buttons: transparent bg, fixed 32x28, hover overlay
            f'QToolButton[uiRole="windowControl"] {{\n'
            f"    background-color: transparent;\n"
            f"    border: none;\n"
            f"    min-width: 32px;\n"
            f"    max-width: 32px;\n"
            f"    min-height: 28px;\n"
            f"    max-height: 28px;\n"
            f"    border-radius: 4px;\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f'QToolButton[uiRole="windowControl"]:hover {{\n'
            f"    background-color: {c.surface_overlay};\n"
            f"}}\n\n"
            # Close button: extends windowControl with danger-red hover
            f'QToolButton[uiRole="windowClose"] {{\n'
            f"    background-color: transparent;\n"
            f"    border: none;\n"
            f"    min-width: 32px;\n"
            f"    max-width: 32px;\n"
            f"    min-height: 28px;\n"
            f"    max-height: 28px;\n"
            f"    border-radius: 4px;\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            f'QToolButton[uiRole="windowClose"]:hover {{\n'
            f"    background-color: {c.danger};\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            # App title label: brand title styling
            f'QLabel[uiRole="appTitle"] {{\n'
            f"    color: {c.text_primary};\n"
            f"    font-size: {t.size_subtitle}px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    background: transparent;\n"
            f"    border: none;\n"
            f"}}"
        )

    def _sidebar_nav(self) -> str:
        """Generate QSS for sidebar navigation panel, nav items, and user profile section."""
        c = self._tokens.colors
        t = self._tokens.typography
        sh = self._tokens.shape

        return (
            # Sidebar container: 260px width, transparent
            f'QWidget[uiPanel="sidebar"] {{\n'
            f"    background: transparent;\n"
            f"    max-width: 260px;\n"
            f"    border-right: 1px solid rgba(255, 255, 255, 0.06);\n"
            f"}}\n\n"
            # Nav item button: 15px font, 20px icon, centered layout
            f'QPushButton[uiRole="navItem"] {{\n'
            f"    background-color: transparent;\n"
            f"    border: none;\n"
            f"    color: {c.text_secondary};\n"
            f"    font-size: 15px;\n"
            f"    font-weight: {t.weight_medium};\n"
            f"    icon-size: 20px;\n"
            f"    text-align: left;\n"
            f"    padding: 10px 20px;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    margin: 0px 4px;\n"
            f"}}\n\n"
            # Nav item hover: subtle purple glow
            f'QPushButton[uiRole="navItem"]:hover {{\n'
            f"    background-color: rgba(124, 58, 237, 0.10);\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            # Nav item active: gradient pill, centered
            f'QPushButton[uiRole="navItemActive"] {{\n'
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {c.nav_active_gradient_start}, stop:1 {c.nav_active_gradient_end});\n"
            f"    border: none;\n"
            f"    color: #ffffff;\n"
            f"    font-size: 15px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    icon-size: 20px;\n"
            f"    text-align: left;\n"
            f"    padding: 10px 20px;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    margin: 0px 4px;\n"
            f"}}\n\n"
            # Sidebar brand title (CAMXORA)
            f'QLabel[uiRole="sidebarBrandTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 16px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    letter-spacing: 2px;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Sidebar user name (bold)
            f'QLabel[uiRole="sidebarUserName"] {{\n'
            f"    color: {c.text_primary};\n"
            f"    font-size: 13px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Sidebar plan label (orange)
            f'QLabel[uiRole="sidebarPlanLabel"] {{\n'
            f"    color: #f97316;\n"
            f"    font-size: 11px;\n"
            f"    font-weight: {t.weight_medium};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Sidebar logout button
            f'QPushButton[uiRole="sidebarLogout"] {{\n'
            f"    background-color: transparent;\n"
            f"    border: none;\n"
            f"    color: #ef4444;\n"
            f"    font-size: 15px;\n"
            f"    font-weight: {t.weight_medium};\n"
            f"    text-align: left;\n"
            f"    padding: 10px 20px;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    margin: 0px 4px;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="sidebarLogout"]:hover {{\n'
            f"    background-color: rgba(239, 68, 68, 0.15);\n"
            f"}}\n\n"
            # User profile section: top border only
            f'QWidget[uiPanel="userProfile"] {{\n'
            f"    background: transparent;\n"
            f"    border-top: 1px solid rgba(255, 255, 255, 0.08);\n"
            f"    color: {c.text_muted};\n"
            f"}}"
        )

    def _greeting_bar(self) -> str:
        """Generate QSS for the greeting bar (top of content area)."""
        c = self._tokens.colors
        t = self._tokens.typography
        sh = self._tokens.shape

        return (
            # Header bar (right of sidebar, window controls only)
            f'QWidget[uiPanel="headerBar"] {{\n'
            f"    background: transparent;\n"
            f"    border-bottom: 1px solid rgba(255, 255, 255, 0.06);\n"
            f"}}\n\n"
            # Header brand title (CAMXORA)
            f'QLabel[uiRole="headerBrandTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 16px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Greeting title (Good morning, Username.)
            f'QLabel[uiRole="greetingTitle"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 26px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Greeting subtitle
            f'QLabel[uiRole="greetingSubtitle"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 15px;\n"
            f"    background: transparent;\n"
            f"}}"
        )

    def _login_shell(self) -> str:
        """Generate QSS for login screen: brand gradient panel, tab bar, tab buttons, form inputs, and labels."""
        c = self._tokens.colors
        t = self._tokens.typography
        sh = self._tokens.shape

        return (
            # Brand gradient panel (purple gradient background)
            f'QWidget[uiPanel="brandGradient"] {{\n'
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.brand_gradient_start}, stop:0.55 {c.brand_gradient_mid}, stop:1 {c.brand_gradient_end});\n"
            f"}}\n\n"
            # Login tab bar container (dark semi-transparent with glass border)
            f'QWidget[uiPanel="loginTabBar"] {{\n'
            f"    background: rgba(10, 14, 39, 0.8);\n"
            f"    border: 1px solid {c.border_glass};\n"
            f"    border-radius: {sh.radius_lg}px;\n"
            f"}}\n\n"
            # Active login tab (purple gradient pill, white text, bold)
            f'QPushButton[uiRole="loginTabActive"] {{\n'
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.nav_active_gradient_start}, stop:1 {c.nav_active_gradient_end});\n"
            f"    color: #ffffff;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    font-size: 15px;\n"
            f"    border: none;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    min-height: 40px;\n"
            f"    max-height: 40px;\n"
            f"    padding: 0px 16px;\n"
            f"}}\n\n"
            # Inactive login tab (transparent bg, muted text, hover tint)
            f'QPushButton[uiRole="loginTabInactive"] {{\n'
            f"    background: transparent;\n"
            f"    color: {c.text_muted};\n"
            f"    font-size: 15px;\n"
            f"    font-weight: {t.weight_medium};\n"
            f"    border: none;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    min-height: 40px;\n"
            f"    max-height: 40px;\n"
            f"    padding: 0px 16px;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="loginTabInactive"]:hover {{\n'
            f"    background: rgba(168, 85, 247, 0.12);\n"
            f"    color: {c.text_primary};\n"
            f"}}\n\n"
            # Login form input (48px height, 15px font, focus border)
            f'QLineEdit[uiField="loginInput"] {{\n'
            f"    min-height: 48px;\n"
            f"    font-size: 15px;\n"
            f"    background: {c.surface_overlay};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    color: {c.text_primary};\n"
            f"    padding: 0 14px;\n"
            f"    selection-background-color: {c.secondary_accent};\n"
            f"}}\n\n"
            f'QLineEdit[uiField="loginInput"]:focus {{\n'
            f"    border: 2px solid {c.secondary_accent_hover};\n"
            f"}}\n\n"
            # Login headline (hero title, 30px bold white)
            f'QLabel[uiRole="loginHeadline"] {{\n'
            f"    color: #ffffff;\n"
            f"    font-size: 26px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Login subtitle (15px muted text for form panel)
            f'QLabel[uiRole="loginSubtitle"] {{\n'
            f"    color: {c.text_muted};\n"
            f"    font-size: 15px;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Login tagline (brand panel descriptive text)
            f'QLabel[uiRole="loginTagline"] {{\n'
            f"    color: rgba(255, 255, 255, 0.78);\n"
            f"    font-size: {t.size_subtitle}px;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Login feature row text (brand panel value props)
            f'QLabel[uiRole="loginFeatureText"] {{\n'
            f"    color: rgba(255, 255, 255, 0.92);\n"
            f"    font-size: {t.size_body}px;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Login field label (14px medium weight secondary text)
            f'QLabel[uiRole="loginFieldLabel"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 14px;\n"
            f"    font-weight: {t.weight_medium};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Login form title (30px bold primary text)
            f'QLabel[uiRole="loginFormTitle"] {{\n'
            f"    color: {c.text_primary};\n"
            f"    font-size: 30px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            # Login error message label
            f'QLabel[uiRole="loginError"] {{\n'
            f"    color: {c.danger};\n"
            f"    font-size: {t.size_body}px;\n"
            f"    background: transparent;\n"
            f"    padding: 2px 0px;\n"
            f"}}\n\n"
            # Login success message label
            f'QLabel[uiRole="loginSuccess"] {{\n'
            f"    color: {c.success};\n"
            f"    font-size: {t.size_body}px;\n"
            f"    background: transparent;\n"
            f"    padding: 2px 0px;\n"
            f"}}\n\n"
            # Login field errors (smaller danger text)
            f'QLabel[uiRole="loginFieldErrors"] {{\n'
            f"    color: {c.danger};\n"
            f"    font-size: {t.size_caption + 1}px;\n"
            f"    background: transparent;\n"
            f"    padding: 2px 0px;\n"
            f"}}\n\n"
            # Forgot password link button
            f'QPushButton[uiRole="loginLink"] {{\n'
            f"    color: {c.secondary_accent_hover};\n"
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"    font-size: 14px;\n"
            f"    padding: 0;\n"
            f"}}\n\n"
            f'QPushButton[uiRole="loginLink"]:hover {{\n'
            f"    color: #c084fc;\n"
            f"}}"
        )

    def _view_specific_roles(self) -> str:
        """Generate QSS for view-specific property selectors replacing inline setStyleSheet calls."""
        c = self._tokens.colors
        t = self._tokens.typography
        sh = self._tokens.shape

        return (
            # Video preview / aspect ratio box: black background for letterboxing
            f'QWidget[uiPanel="videoPreview"] {{\n'
            f"    background-color: #000000;\n"
            f"}}\n\n"
            # Preview display panel (preset manager preview area)
            f'QWidget[uiPanel="previewDisplay"] {{\n'
            f"    background-color: {c.surface_sunken};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    border-radius: 4px;\n"
            f"}}\n\n"
            # Compact tabs (music settings, settings view)
            f'QTabWidget[uiPanel="compactTabs"]::pane {{\n'
            f"    border: none;\n"
            f"    background: transparent;\n"
            f"}}\n\n"
            f'QTabWidget[uiPanel="compactTabs"] QTabBar::tab {{\n'
            f"    background: {c.surface_raised};\n"
            f"    color: {c.text_secondary};\n"
            f"    padding: 9px 18px;\n"
            f"    min-width: 96px;\n"
            f"    border: none;\n"
            f"    border-radius: 7px;\n"
            f"    margin-right: 4px;\n"
            f"    font-size: {t.size_body}px;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"}}\n\n"
            f'QTabWidget[uiPanel="compactTabs"] QTabBar::tab:selected {{\n'
            f"    background: {c.accent};\n"
            f"    color: #ffffff;\n"
            f"}}\n\n"
            f'QTabWidget[uiPanel="compactTabs"] QTabBar::tab:hover:!selected {{\n'
            f"    background: {c.surface_overlay};\n"
            f"}}\n\n"
            # Settings compact tabs (smaller padding)
            f'QTabWidget[uiPanel="compactTabsSmall"]::pane {{\n'
            f"    border: none;\n"
            f"    margin-top: 4px;\n"
            f"}}\n\n"
            f'QTabWidget[uiPanel="compactTabsSmall"] QTabBar::tab {{\n'
            f"    background: {c.surface_raised};\n"
            f"    color: {c.text_secondary};\n"
            f"    padding: 4px 7px;\n"
            f"    min-width: 0px;\n"
            f"    border-top-left-radius: 4px;\n"
            f"    border-top-right-radius: 4px;\n"
            f"    border: none;\n"
            f"}}\n\n"
            f'QTabWidget[uiPanel="compactTabsSmall"] QTabBar::tab:selected {{\n'
            f"    background: {c.accent};\n"
            f"    color: #ffffff;\n"
            f"}}\n\n"
            # Credit cost label (music view)
            f'QLabel[uiRole="creditCost"] {{\n'
            f"    color: {c.text_secondary};\n"
            f"    font-size: 11px;\n"
            f"    font-weight: 600;\n"
            f"    background: transparent;\n"
            f"    border: none;\n"
            f"}}\n\n"
            # Log console (plain text edit for log output)
            f'QPlainTextEdit[uiField="logConsole"] {{\n'
            f"    background-color: {c.surface_base};\n"
            f"    color: {c.text_secondary};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    border-radius: 6px;\n"
            f"    padding: 6px;\n"
            f"}}\n\n"
            # Export progress bar (blue chunk)
            f'QProgressBar[uiRole="exportProgress"] {{\n'
            f"    background: {c.surface_base};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    border-radius: 8px;\n"
            f"    color: {c.text_primary};\n"
            f"    text-align: center;\n"
            f"    font-size: 11px;\n"
            f"    font-weight: 600;\n"
            f"}}\n\n"
            f'QProgressBar[uiRole="exportProgress"]::chunk {{\n'
            f"    background: {c.accent};\n"
            f"    border-radius: 7px;\n"
            f"}}\n\n"
            # Merge progress bar (orange/warning chunk)
            f'QProgressBar[uiRole="mergeProgress"] {{\n'
            f"    background: {c.surface_base};\n"
            f"    border: 1px solid {c.border_strong};\n"
            f"    border-radius: 8px;\n"
            f"    color: {c.text_primary};\n"
            f"    text-align: center;\n"
            f"    font-size: 11px;\n"
            f"    font-weight: 600;\n"
            f"}}\n\n"
            f'QProgressBar[uiRole="mergeProgress"]::chunk {{\n'
            f"    background: {c.warning};\n"
            f"    border-radius: 7px;\n"
            f"}}"
        )

    def _gradient_buttons(self) -> str:
        """Generate QSS for gradient primary CTA button with hover, pressed, and disabled states."""
        c = self._tokens.colors
        sh = self._tokens.shape
        t = self._tokens.typography

        return (
            # Gradient primary button: purple gradient, white text, 44px height, 8px radius
            f'QPushButton[uiRole="gradientPrimary"] {{\n'
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {c.nav_active_gradient_start}, stop:1 {c.nav_active_gradient_end});\n"
            f"    color: #ffffff;\n"
            f"    min-height: 44px;\n"
            f"    border-radius: {sh.radius_md}px;\n"
            f"    border: none;\n"
            f"    font-weight: {t.weight_bold};\n"
            f"    padding: 0 16px;\n"
            f"}}\n\n"
            # Hover: brighter purple
            f'QPushButton[uiRole="gradientPrimary"]:hover {{\n'
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #8b6fff, stop:1 #b87dff);\n"
            f"}}\n\n"
            # Pressed: darker purple
            f'QPushButton[uiRole="gradientPrimary"]:pressed {{\n'
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #5a3dc7, stop:1 #7c4dff);\n"
            f"}}\n\n"
            # Disabled: flat surface_overlay, muted text
            f'QPushButton[uiRole="gradientPrimary"]:disabled {{\n'
            f"    background: {c.surface_overlay};\n"
            f"    color: {c.text_muted};\n"
            f"    border: none;\n"
            f"}}"
        )
