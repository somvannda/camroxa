"""Preset Manager Dialog — manage text style presets for thumbnail overlay rendering."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QImage, QPixmap

logger = logging.getLogger(__name__)


class PresetManagerDialog(QDialog):
    """Dialog for managing text style presets (CRUD operations).

    Uses QListWidget for the preset list (performant for 100+ items)
    and delegates data operations to TextPresetManagerCoordinator.
    """

    def __init__(self, parent: Any, coordinator: Any):
        super().__init__(parent)
        self._parent = parent
        self._coordinator = coordinator
        self._presets: list[dict] = []

        self.setWindowTitle("Text Style Presets")
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        self.setModal(True)

        self._build_ui()
        self._reload_presets()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Header
        title = QLabel("Text Style Presets")
        self._parent._set_label_role(title, "sectionTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Create and manage text overlay presets for thumbnail generation."
        )
        subtitle.setWordWrap(True)
        self._parent._set_label_role(subtitle, "statusMuted")
        root.addWidget(subtitle)

        # Preset list (QListWidget handles 100+ items efficiently with internal scrolling)
        self._preset_list = QListWidget()
        self._parent._apply_card_field(self._preset_list)
        self._preset_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._preset_list.setMinimumHeight(200)
        self._preset_list.currentRowChanged.connect(self._on_selection_changed)
        root.addWidget(self._preset_list, 1)

        # Action buttons
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self._btn_add = QPushButton("Add Preset")
        self._parent._set_button_role(self._btn_add, "primary")
        self._btn_add.setFixedHeight(30)
        self._btn_add.clicked.connect(self._on_add_preset)
        actions.addWidget(self._btn_add)

        self._btn_edit = QPushButton("Edit")
        self._parent._set_button_role(self._btn_edit, "secondary")
        self._btn_edit.setFixedHeight(30)
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._on_edit_preset)
        actions.addWidget(self._btn_edit)

        self._btn_delete = QPushButton("Delete")
        self._parent._set_button_role(self._btn_delete, "danger")
        self._btn_delete.setFixedHeight(30)
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete_preset)
        actions.addWidget(self._btn_delete)

        actions.addStretch(1)

        self._btn_close = QPushButton("Close")
        self._parent._set_button_role(self._btn_close, "secondary")
        self._btn_close.setFixedHeight(30)
        self._btn_close.clicked.connect(self.close)
        actions.addWidget(self._btn_close)

        root.addLayout(actions)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _reload_presets(self):
        """Reload presets from the coordinator and refresh the list widget."""
        try:
            self._presets = self._coordinator.load_presets()
        except Exception as exc:
            logger.warning("Failed to load presets: %s", exc)
            self._presets = []

        self._preset_list.setUpdatesEnabled(False)
        try:
            self._preset_list.clear()
            for preset in self._presets:
                item = QListWidgetItem()
                name = str(preset.get("name", "Unnamed"))
                color = str(preset.get("primary_color", "#FFFFFFFF"))[:7]  # Use RGB portion
                item.setText(f"  {name}")
                item.setData(Qt.ItemDataRole.UserRole, preset)
                # Set color indicator via decoration
                pixmap = QPixmap(16, 16)
                try:
                    pixmap.fill(QColor(color))
                except Exception:
                    pixmap.fill(QColor("#FFFFFF"))
                item.setIcon(QIcon(pixmap))
                self._preset_list.addItem(item)
        finally:
            self._preset_list.setUpdatesEnabled(True)

        self._on_selection_changed()

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        has_selection = self._preset_list.currentRow() >= 0
        self._btn_edit.setEnabled(has_selection)
        self._btn_delete.setEnabled(has_selection)

    def _on_add_preset(self):
        """Open form dialog to create a new preset."""
        dlg = PresetFormDialog(self._parent, self._coordinator, preset_data=None)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_presets()

    def _on_edit_preset(self):
        """Open form dialog pre-populated with the selected preset's values."""
        row = self._preset_list.currentRow()
        if row < 0:
            return
        item = self._preset_list.item(row)
        if item is None:
            return
        preset_data = item.data(Qt.ItemDataRole.UserRole)
        dlg = PresetFormDialog(self._parent, self._coordinator, preset_data=preset_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_presets()

    def _on_delete_preset(self):
        """Delete the selected preset after confirmation."""
        row = self._preset_list.currentRow()
        if row < 0:
            return
        item = self._preset_list.item(row)
        if item is None:
            return
        preset_data = item.data(Qt.ItemDataRole.UserRole)
        name = str(preset_data.get("name", "this preset"))
        preset_id = preset_data.get("id")
        if preset_id is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f'Are you sure you want to delete "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._coordinator.delete_preset(int(preset_id))
            self._reload_presets()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Failed to delete preset: {exc}")


class PresetFormDialog(QDialog):
    """Form dialog for creating or editing a text style preset.

    Contains fields for all preset properties: name, font, size, colors,
    effects (glow, shadow, stroke, gradient), and layout settings.
    """

    def __init__(self, parent: Any, coordinator: Any, preset_data: dict | None = None):
        super().__init__(parent)
        self._parent = parent
        self._coordinator = coordinator
        self._preset_data = preset_data or {}
        self._is_edit = preset_data is not None

        self.setWindowTitle("Edit Preset" if self._is_edit else "Add Preset")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self.setModal(True)

        self._build_ui()
        if self._is_edit:
            self._populate_from_preset()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Scrollable form area for all fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(4, 4, 4, 4)
        form_layout.setSpacing(10)

        # --- Basic Settings ---
        basic_label = QLabel("Basic Settings")
        self._parent._set_label_role(basic_label, "sectionTitle")
        form_layout.addWidget(basic_label)

        # Name
        self._name_input = QLineEdit()
        self._parent._apply_card_field(self._name_input)
        self._name_input.setPlaceholderText("Preset name (required)")
        self._add_field_row(form_layout, "Name", self._name_input)

        # Font path (dropdown)
        self._font_combo = QComboBox()
        self._parent._apply_card_field(self._font_combo)
        self._font_combo.addItem("(Default Font)", "")
        # Populate available fonts from font manager if accessible
        self._populate_font_list()
        self._add_field_row(form_layout, "Font", self._font_combo)

        # Font size
        self._font_size_spin = QSpinBox()
        self._parent._apply_card_field(self._font_size_spin)
        self._font_size_spin.setMinimum(12)
        self._font_size_spin.setMaximum(400)
        self._font_size_spin.setValue(72)
        self._font_size_spin.setSuffix(" px")
        self._add_field_row(form_layout, "Font Size", self._font_size_spin)

        # Primary color
        self._primary_color_input = QLineEdit()
        self._parent._apply_card_field(self._primary_color_input)
        self._primary_color_input.setText("#FFFFFFFF")
        self._primary_color_input.setPlaceholderText("#RRGGBBAA")
        color_row = self._make_color_row(self._primary_color_input)
        self._add_field_row(form_layout, "Primary Color", color_row)

        # Position
        self._position_combo = QComboBox()
        self._parent._apply_card_field(self._position_combo)
        self._position_combo.addItem("Top", "top")
        self._position_combo.addItem("Center", "center")
        self._position_combo.addItem("Bottom", "bottom")
        self._position_combo.setCurrentIndex(1)  # Default to center
        self._add_field_row(form_layout, "Position", self._position_combo)

        # --- Effects ---
        effects_label = QLabel("Effects")
        self._parent._set_label_role(effects_label, "sectionTitle")
        form_layout.addWidget(effects_label)

        # Glow
        self._glow_color_input = QLineEdit()
        self._parent._apply_card_field(self._glow_color_input)
        self._glow_color_input.setText("#00000000")
        self._glow_color_input.setPlaceholderText("#RRGGBBAA")
        glow_color_row = self._make_color_row(self._glow_color_input)
        self._add_field_row(form_layout, "Glow Color", glow_color_row)

        self._glow_radius_spin = QSpinBox()
        self._parent._apply_card_field(self._glow_radius_spin)
        self._glow_radius_spin.setMinimum(0)
        self._glow_radius_spin.setMaximum(50)
        self._glow_radius_spin.setValue(0)
        self._glow_radius_spin.setSuffix(" px")
        self._add_field_row(form_layout, "Glow Radius", self._glow_radius_spin)

        # Shadow
        self._shadow_color_input = QLineEdit()
        self._parent._apply_card_field(self._shadow_color_input)
        self._shadow_color_input.setText("#00000080")
        self._shadow_color_input.setPlaceholderText("#RRGGBBAA")
        shadow_color_row = self._make_color_row(self._shadow_color_input)
        self._add_field_row(form_layout, "Shadow Color", shadow_color_row)

        self._shadow_x_spin = QSpinBox()
        self._parent._apply_card_field(self._shadow_x_spin)
        self._shadow_x_spin.setMinimum(-50)
        self._shadow_x_spin.setMaximum(50)
        self._shadow_x_spin.setValue(0)
        self._shadow_x_spin.setSuffix(" px")
        self._add_field_row(form_layout, "Shadow X", self._shadow_x_spin)

        self._shadow_y_spin = QSpinBox()
        self._parent._apply_card_field(self._shadow_y_spin)
        self._shadow_y_spin.setMinimum(-50)
        self._shadow_y_spin.setMaximum(50)
        self._shadow_y_spin.setValue(0)
        self._shadow_y_spin.setSuffix(" px")
        self._add_field_row(form_layout, "Shadow Y", self._shadow_y_spin)

        # Stroke
        self._stroke_color_input = QLineEdit()
        self._parent._apply_card_field(self._stroke_color_input)
        self._stroke_color_input.setText("#000000FF")
        self._stroke_color_input.setPlaceholderText("#RRGGBBAA")
        stroke_color_row = self._make_color_row(self._stroke_color_input)
        self._add_field_row(form_layout, "Stroke Color", stroke_color_row)

        self._stroke_width_spin = QSpinBox()
        self._parent._apply_card_field(self._stroke_width_spin)
        self._stroke_width_spin.setMinimum(0)
        self._stroke_width_spin.setMaximum(10)
        self._stroke_width_spin.setValue(0)
        self._stroke_width_spin.setSuffix(" px")
        self._add_field_row(form_layout, "Stroke Width", self._stroke_width_spin)

        # --- Gradient ---
        gradient_label = QLabel("Gradient")
        self._parent._set_label_role(gradient_label, "sectionTitle")
        form_layout.addWidget(gradient_label)

        self._gradient_enabled_check = QCheckBox("Enable Gradient")
        self._gradient_enabled_check.setChecked(False)
        form_layout.addWidget(self._gradient_enabled_check)

        self._gradient_start_input = QLineEdit()
        self._parent._apply_card_field(self._gradient_start_input)
        self._gradient_start_input.setText("#FFFFFFFF")
        self._gradient_start_input.setPlaceholderText("#RRGGBBAA")
        grad_start_row = self._make_color_row(self._gradient_start_input)
        self._add_field_row(form_layout, "Start Color", grad_start_row)

        self._gradient_end_input = QLineEdit()
        self._parent._apply_card_field(self._gradient_end_input)
        self._gradient_end_input.setText("#000000FF")
        self._gradient_end_input.setPlaceholderText("#RRGGBBAA")
        grad_end_row = self._make_color_row(self._gradient_end_input)
        self._add_field_row(form_layout, "End Color", grad_end_row)

        # --- Layout ---
        layout_label = QLabel("Layout")
        self._parent._set_label_role(layout_label, "sectionTitle")
        form_layout.addWidget(layout_label)

        # Line spacing
        self._line_spacing_spin = QDoubleSpinBox()
        self._parent._apply_card_field(self._line_spacing_spin)
        self._line_spacing_spin.setMinimum(1.0)
        self._line_spacing_spin.setMaximum(3.0)
        self._line_spacing_spin.setSingleStep(0.1)
        self._line_spacing_spin.setValue(1.4)
        self._add_field_row(form_layout, "Line Spacing", self._line_spacing_spin)

        # Alignment
        self._alignment_combo = QComboBox()
        self._parent._apply_card_field(self._alignment_combo)
        self._alignment_combo.addItem("Left", "left")
        self._alignment_combo.addItem("Center", "center")
        self._alignment_combo.addItem("Right", "right")
        self._alignment_combo.setCurrentIndex(1)  # Default to center
        self._add_field_row(form_layout, "Alignment", self._alignment_combo)

        # Max text width %
        self._max_width_spin = QSpinBox()
        self._parent._apply_card_field(self._max_width_spin)
        self._max_width_spin.setMinimum(20)
        self._max_width_spin.setMaximum(90)
        self._max_width_spin.setValue(80)
        self._max_width_spin.setSuffix(" %")
        self._add_field_row(form_layout, "Max Width", self._max_width_spin)

        # Vertical padding %
        self._vert_padding_spin = QSpinBox()
        self._parent._apply_card_field(self._vert_padding_spin)
        self._vert_padding_spin.setMinimum(2)
        self._vert_padding_spin.setMaximum(30)
        self._vert_padding_spin.setValue(10)
        self._vert_padding_spin.setSuffix(" %")
        self._add_field_row(form_layout, "Vert. Padding", self._vert_padding_spin)

        form_layout.addStretch(1)
        scroll.setWidget(form_widget)
        root.addWidget(scroll, 1)

        # --- Live Preview Panel ---
        preview_label = QLabel("Preview")
        self._parent._set_label_role(preview_label, "sectionTitle")
        root.addWidget(preview_label)

        self._preview_display = QLabel()
        self._preview_display.setFixedSize(400, 225)
        self._preview_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        from python_app.views.helpers.style_helper import set_panel_role as _set_panel
        _set_panel(self._preview_display, "previewDisplay")
        root.addWidget(self._preview_display, 0, Qt.AlignmentFlag.AlignCenter)

        # No-fonts note (hidden by default)
        self._no_fonts_label = QLabel(
            "No custom fonts available \u2014 default font will be used"
        )
        self._parent._set_label_role(self._no_fonts_label, "statusMuted")
        self._no_fonts_label.setVisible(False)
        root.addWidget(self._no_fonts_label)

        # Show no-fonts message if font combo only has the default entry
        if self._font_combo.count() <= 1:
            self._no_fonts_label.setVisible(True)

        # --- Debounce timer for preview updates ---
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._update_preview)

        # Connect form fields to debounced preview update
        self._connect_preview_signals()

        # Initial preview render
        QTimer.singleShot(50, self._update_preview)

        # --- Action Buttons ---
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self._btn_save = QPushButton("Save")
        self._parent._set_button_role(self._btn_save, "primary")
        self._btn_save.setFixedHeight(30)
        self._btn_save.clicked.connect(self._on_save)
        actions.addWidget(self._btn_save)

        actions.addStretch(1)

        self._btn_cancel = QPushButton("Cancel")
        self._parent._set_button_role(self._btn_cancel, "secondary")
        self._btn_cancel.setFixedHeight(30)
        self._btn_cancel.clicked.connect(self.reject)
        actions.addWidget(self._btn_cancel)

        root.addLayout(actions)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_field_row(self, layout: QVBoxLayout, label_text: str, field: QWidget):
        """Add a labeled row to the form layout, matching the project's form row pattern."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label = QLabel(label_text)
        self._parent._set_label_role(label, "metricTitle")
        label.setMinimumWidth(100)
        row.addWidget(label)
        row.addWidget(field, 1)
        layout.addLayout(row)

    def _make_color_row(self, line_edit: QLineEdit) -> QWidget:
        """Create a color input row with a 'Pick' button that opens QColorDialog."""
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(line_edit, 1)
        btn = QPushButton("Pick")
        self._parent._set_button_role(btn, "compactSecondary")
        btn.clicked.connect(lambda: self._pick_color(line_edit))
        row.addWidget(btn)
        return widget

    def _pick_color(self, line_edit: QLineEdit):
        """Open a color picker dialog and write the selected RGBA hex to the line edit."""
        current_text = line_edit.text().strip()
        initial = QColor("#FFFFFFFF")
        if current_text and len(current_text) >= 7:
            initial = QColor(current_text[:7])
        color = QColorDialog.getColor(
            initial, self, "Pick Color", QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            rgba = "#{:02X}{:02X}{:02X}{:02X}".format(
                color.red(), color.green(), color.blue(), color.alpha()
            )
            line_edit.setText(rgba)

    def _populate_font_list(self):
        """Populate font dropdown from available fonts (via coordinator or settings)."""
        try:
            # Try to get font list from font manager if available
            host = getattr(self._coordinator, "_host", None)
            if host is not None:
                font_manager = getattr(host, "_font_manager", None)
                if font_manager is not None and hasattr(font_manager, "list_available_fonts"):
                    fonts = font_manager.list_available_fonts()
                    for font_path in fonts:
                        display_name = font_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                        self._font_combo.addItem(display_name, font_path)
                    return
            # Fallback: try coordinator host settings
            if host is not None and hasattr(host, "_music_settings"):
                settings = host._music_settings()
                fonts_dir = settings.get("fontsDirectory", "")
                if fonts_dir:
                    from pathlib import Path

                    fonts_path = Path(fonts_dir)
                    if fonts_path.is_dir():
                        for f in sorted(fonts_path.iterdir()):
                            if f.suffix.lower() in (".ttf", ".otf"):
                                self._font_combo.addItem(f.name, str(f))
        except Exception as exc:
            logger.debug("Could not populate font list: %s", exc)

    def _populate_from_preset(self):
        """Pre-populate form fields from existing preset data."""
        p = self._preset_data

        self._name_input.setText(str(p.get("name", "")))

        # Font path
        font_path = str(p.get("font_path", ""))
        idx = self._font_combo.findData(font_path)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)
        else:
            self._font_combo.setCurrentIndex(0)

        self._font_size_spin.setValue(int(p.get("font_size", 72)))
        self._primary_color_input.setText(str(p.get("primary_color", "#FFFFFFFF")))

        # Position
        position = str(p.get("position", "center"))
        pos_idx = self._position_combo.findData(position)
        if pos_idx >= 0:
            self._position_combo.setCurrentIndex(pos_idx)

        # Effects
        self._glow_color_input.setText(str(p.get("glow_color", "#00000000")))
        self._glow_radius_spin.setValue(int(p.get("glow_radius", 0)))
        self._shadow_color_input.setText(str(p.get("shadow_color", "#00000080")))
        self._shadow_x_spin.setValue(int(p.get("shadow_offset_x", 0)))
        self._shadow_y_spin.setValue(int(p.get("shadow_offset_y", 0)))
        self._stroke_color_input.setText(str(p.get("stroke_color", "#000000FF")))
        self._stroke_width_spin.setValue(int(p.get("stroke_width", 0)))

        # Gradient
        self._gradient_enabled_check.setChecked(bool(p.get("gradient_enabled", False)))
        self._gradient_start_input.setText(str(p.get("gradient_start_color", "#FFFFFFFF")))
        self._gradient_end_input.setText(str(p.get("gradient_end_color", "#000000FF")))

        # Layout
        self._line_spacing_spin.setValue(float(p.get("line_spacing", 1.4)))
        alignment = str(p.get("alignment", "center"))
        align_idx = self._alignment_combo.findData(alignment)
        if align_idx >= 0:
            self._alignment_combo.setCurrentIndex(align_idx)
        self._max_width_spin.setValue(int(p.get("max_text_width_pct", 80)))
        self._vert_padding_spin.setValue(int(p.get("vertical_padding_pct", 10)))

    # ------------------------------------------------------------------
    # Live Preview
    # ------------------------------------------------------------------

    def _connect_preview_signals(self):
        """Connect all form field change signals to trigger a debounced preview update."""
        # Text fields
        self._name_input.textChanged.connect(self._schedule_preview_update)
        self._primary_color_input.textChanged.connect(self._schedule_preview_update)
        self._glow_color_input.textChanged.connect(self._schedule_preview_update)
        self._shadow_color_input.textChanged.connect(self._schedule_preview_update)
        self._stroke_color_input.textChanged.connect(self._schedule_preview_update)
        self._gradient_start_input.textChanged.connect(self._schedule_preview_update)
        self._gradient_end_input.textChanged.connect(self._schedule_preview_update)

        # Spin boxes
        self._font_size_spin.valueChanged.connect(self._schedule_preview_update)
        self._glow_radius_spin.valueChanged.connect(self._schedule_preview_update)
        self._shadow_x_spin.valueChanged.connect(self._schedule_preview_update)
        self._shadow_y_spin.valueChanged.connect(self._schedule_preview_update)
        self._stroke_width_spin.valueChanged.connect(self._schedule_preview_update)
        self._max_width_spin.valueChanged.connect(self._schedule_preview_update)
        self._vert_padding_spin.valueChanged.connect(self._schedule_preview_update)
        self._line_spacing_spin.valueChanged.connect(self._schedule_preview_update)

        # Combo boxes
        self._font_combo.currentIndexChanged.connect(self._schedule_preview_update)
        self._position_combo.currentIndexChanged.connect(self._schedule_preview_update)
        self._alignment_combo.currentIndexChanged.connect(self._schedule_preview_update)

        # Checkbox
        self._gradient_enabled_check.stateChanged.connect(self._schedule_preview_update)

    def _schedule_preview_update(self):
        """Restart the debounce timer so preview updates ~300ms after the last change."""
        self._preview_timer.start()

    def _update_preview(self):
        """Render the live preview using the coordinator and display it in the preview panel."""
        try:
            preset_data = self._collect_form_data()
            pil_image = self._coordinator.render_preview(
                preset_data, "Track Title Preview", 400, 225
            )

            # Convert PIL Image (RGBA) to QPixmap
            data = pil_image.tobytes("raw", "RGBA")
            qimg = QImage(
                data, pil_image.width, pil_image.height, QImage.Format.Format_RGBA8888
            )
            pixmap = QPixmap.fromImage(qimg)
            self._preview_display.setPixmap(pixmap)
        except Exception as exc:
            logger.debug("Preview render failed: %s", exc)
            self._preview_display.setText("Preview unavailable")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        """Validate and save the preset via the coordinator."""
        preset_data = self._collect_form_data()

        # Basic client-side validation
        name = preset_data.get("name", "").strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Preset name cannot be empty.")
            self._name_input.setFocus()
            return

        # Preserve ID for edits
        if self._is_edit and "id" in self._preset_data:
            preset_data["id"] = self._preset_data["id"]

        try:
            self._coordinator.save_preset(preset_data)
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Failed to save preset: {exc}")

    def _collect_form_data(self) -> dict:
        """Collect all form field values into a dict matching the preset schema."""
        return {
            "name": self._name_input.text().strip(),
            "font_path": self._font_combo.currentData() or "",
            "font_size": self._font_size_spin.value(),
            "primary_color": self._primary_color_input.text().strip(),
            "position": self._position_combo.currentData() or "center",
            "glow_color": self._glow_color_input.text().strip(),
            "glow_radius": self._glow_radius_spin.value(),
            "shadow_offset_x": self._shadow_x_spin.value(),
            "shadow_offset_y": self._shadow_y_spin.value(),
            "shadow_color": self._shadow_color_input.text().strip(),
            "stroke_width": self._stroke_width_spin.value(),
            "stroke_color": self._stroke_color_input.text().strip(),
            "gradient_enabled": self._gradient_enabled_check.isChecked(),
            "gradient_start_color": self._gradient_start_input.text().strip(),
            "gradient_end_color": self._gradient_end_input.text().strip(),
            "line_spacing": self._line_spacing_spin.value(),
            "alignment": self._alignment_combo.currentData() or "center",
            "max_text_width_pct": self._max_width_spin.value(),
            "vertical_padding_pct": self._vert_padding_spin.value(),
        }
