"""Album and Title domain inspectors — Spectrum-parity text domains."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_controls import StudioCheckBox

from features.video.lib.text_color_engine import (
    TEXT_FILL_MODE_OPTIONS,
    TEXT_GLOW_MODE_OPTIONS,
    TEXT_GRADIENT_DIRECTION_OPTIONS,
    normalize_text_gradient_colors,
)
from features.video.lib.text_domain_registry import (
    CONTENT_MODE_OPTIONS,
    PLAYLIST_LOOK_PRESET_OPTIONS,
    TEXT_ALIGN_OPTIONS,
    TEXT_DOMAIN_PRESET_OPTIONS,
    TITLE_LAYOUT_OPTIONS,
    TITLE_LIST_STYLE_OPTIONS,
    TITLE_NUMBER_INDENT_OPTIONS,
    build_playlist_layout_side_draft_patch,
    build_playlist_look_draft_patch,
    get_font_options,
)
from features.video.widgets.inspector_fields import (
    InspectorSection,
    build_color_field,
    build_float_slider,
)
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID


def _stacked_field(label: str, widget: QWidget) -> QWidget:
    """Label-above-control row — fits narrow right rail without clipping combos."""
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    caption = QLabel(label)
    caption.setObjectName(SUBTITLE_LABEL_ID)
    layout.addWidget(caption)
    widget.setMinimumWidth(0)
    layout.addWidget(widget)
    return host


class _TextDomainInspectorBase(QWidget):
    """Shared Album/Title inspector chrome."""

    draft_patch_requested = Signal(dict)
    preset_apply_requested = Signal(str)
    preset_restore_requested = Signal()

    _DOMAIN = "album"
    _PREFIX = "album"
    _ENABLE_LABEL = "Enable Album"
    _TITLE = "Album"
    _SUBTITLE = "Album name styling for preview and export."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._enable: QCheckBox | None = None
        self._content_mode: QComboBox | None = None
        self._preset_combo: QComboBox | None = None
        self._selected_preset_key: str | None = None
        self._previous_preset_key: str | None = None
        self._font_combo: QComboBox | None = None
        self._align_combo: QComboBox | None = None
        self._fill_mode: QComboBox | None = None
        self._gradient_direction: QComboBox | None = None
        self._gradient_host: QWidget | None = None
        self._bound_gradient_colors: list[str] = []
        self._glow_mode: QComboBox | None = None
        self._glow_gradient_direction: QComboBox | None = None
        self._glow_gradient_host: QWidget | None = None
        self._bound_glow_gradient_colors: list[str] = []
        self._bold: QCheckBox | None = None
        self._italic: QCheckBox | None = None
        self._float_setters: dict[str, object] = {}
        self._color_setters: dict[str, object] = {}
        self._manual_album: QLineEdit | None = None
        self._manual_titles: QPlainTextEdit | None = None
        self._list_style: QComboBox | None = None
        self._number_indent: QComboBox | None = None
        self._layout_combo: QComboBox | None = None
        self._playlist_look: QComboBox | None = None
        self._toggle_fields: dict[str, QCheckBox] = {}
        self._effect_pack_host: QVBoxLayout | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(8)

        section = InspectorSection(self._TITLE, subtitle=self._SUBTITLE)
        if hasattr(section, "_root"):
            section._root.setContentsMargins(10, 10, 10, 10)

        # Install ZIP / effect pack at top (Spectrum/Particles pattern).
        self._effect_pack_host = QVBoxLayout()
        self._effect_pack_host.setContentsMargins(0, 0, 0, 0)
        section.add_layout(self._effect_pack_host)

        self._enable = StudioCheckBox(self._ENABLE_LABEL)
        self._enable.toggled.connect(lambda checked: self._emit_patch({f"{self._PREFIX}Enabled": checked}))
        section.add_widget(self._enable)

        self._preset_combo = QComboBox()
        for value, label in TEXT_DOMAIN_PRESET_OPTIONS:
            self._preset_combo.addItem(label, value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        section.add_widget(_stacked_field("Style Preset", self._preset_combo))

        restore_row = QHBoxLayout()
        restore_row.addStretch()
        restore_btn = QPushButton("Restore original")
        restore_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        restore_btn.setToolTip("Reset the selected preset to factory defaults (local override only).")
        restore_btn.clicked.connect(self.preset_restore_requested.emit)
        restore_row.addWidget(restore_btn)
        section.add_layout(restore_row)

        self._content_mode = QComboBox()
        for value, label in CONTENT_MODE_OPTIONS:
            self._content_mode.addItem(label, value)
        self._content_mode.currentIndexChanged.connect(self._on_content_mode_changed)
        section.add_widget(_stacked_field("Content", self._content_mode))

        self._build_content_fields(section)

        root.addWidget(section)

        style = InspectorSection("Typography", subtitle="Font, weight, color, and stroke.")
        if hasattr(style, "_root"):
            style._root.setContentsMargins(10, 10, 10, 10)
        self._font_combo = QComboBox()
        self._font_combo.setEditable(True)
        self._font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._font_combo.setMaxVisibleItems(24)
        for value, label in get_font_options():
            self._font_combo.addItem(label, value)
        self._font_combo.currentIndexChanged.connect(
            lambda _i: self._emit_combo(self._font_combo, f"{self._PREFIX}FontFamily")
        )
        style.add_widget(_stacked_field("Font", self._font_combo))

        weight_row = QHBoxLayout()
        self._bold = StudioCheckBox("Bold")
        self._bold.toggled.connect(lambda checked: self._emit_patch({f"{self._PREFIX}Bold": checked}))
        self._italic = StudioCheckBox("Italic")
        self._italic.toggled.connect(lambda checked: self._emit_patch({f"{self._PREFIX}Italic": checked}))
        weight_row.addWidget(self._bold)
        weight_row.addWidget(self._italic)
        weight_row.addStretch()
        style.add_layout(weight_row)

        for field, label, minimum, maximum, step in (
            (f"{self._PREFIX}FontSize", "Size", 5, 160, 1),
            (f"{self._PREFIX}LetterSpacing", "Letter Spacing", -20, 20, 0.1),
            (f"{self._PREFIX}LineSpacing", "Line Spacing", 0.8, 2.5, 0.05),
            (f"{self._PREFIX}BoxWidth", "Box Width", 0, 1200, 1),
            (f"{self._PREFIX}StrokeWidth", "Stroke Width", 0, 10, 0.1),
            (f"{self._PREFIX}Shadow", "Shadow", 0, 1, 0.01),
            (f"{self._PREFIX}ShadowBlur", "Shadow Blur", 0, 24, 0.5),
            (f"{self._PREFIX}Glow", "Glow", 0, 1, 0.01),
            (f"{self._PREFIX}GlowBlur", "Glow Blur", 0, 32, 0.5),
            (f"{self._PREFIX}ExtrudeDepth", "Extrude Depth", 0, 16, 1),
            (f"{self._PREFIX}Opacity", "Opacity", 0, 1, 0.01),
            (f"{self._PREFIX}X", "Offset X", -800, 800, 1),
            (f"{self._PREFIX}Y", "Offset Y", -800, 800, 1),
        ):
            widget, setter = build_float_slider(
                label,
                minimum=minimum,
                maximum=maximum,
                step=step,
                value=minimum,
                on_change=lambda value, key=field: self._emit_patch({key: value}),
            )
            self._float_setters[field] = setter
            style.add_widget(widget)

        self._fill_mode = QComboBox()
        for value, label in TEXT_FILL_MODE_OPTIONS:
            self._fill_mode.addItem(label, value)
        self._fill_mode.currentIndexChanged.connect(self._on_fill_mode_changed)
        style.add_widget(_stacked_field("Fill Mode", self._fill_mode))

        for field, label in (
            (f"{self._PREFIX}Color", "Fill"),
            (f"{self._PREFIX}StrokeColor", "Stroke"),
            (f"{self._PREFIX}GlowColor", "Glow Color"),
            (f"{self._PREFIX}ExtrudeColor", "Extrude Color"),
        ):
            widget, setter = build_color_field(
                label,
                value="#ffffff",
                on_change=lambda value, key=field: self._emit_patch({key: value}),
                parent=self,
                show_label=False,
            )
            self._color_setters[field] = setter
            style.add_widget(_stacked_field(label, widget))

        self._gradient_host = QWidget()
        gradient_layout = QVBoxLayout(self._gradient_host)
        gradient_layout.setContentsMargins(0, 0, 0, 0)
        gradient_layout.setSpacing(4)
        self._gradient_direction = QComboBox()
        for value, label in TEXT_GRADIENT_DIRECTION_OPTIONS:
            self._gradient_direction.addItem(label, value)
        self._gradient_direction.currentIndexChanged.connect(
            lambda _i: self._emit_combo(self._gradient_direction, f"{self._PREFIX}GradientDirection")
        )
        gradient_layout.addWidget(_stacked_field("Gradient Direction", self._gradient_direction))
        for field, label in (
            (f"{self._PREFIX}GradientColor0", "Gradient A"),
            (f"{self._PREFIX}GradientColor1", "Gradient B"),
            (f"{self._PREFIX}GradientColor2", "Gradient C"),
        ):
            widget, setter = build_color_field(
                label,
                value="#ffffff",
                on_change=lambda value, key=field: self._on_gradient_stop_changed(key, value),
                parent=self,
                show_label=False,
            )
            self._color_setters[field] = setter
            gradient_layout.addWidget(_stacked_field(label, widget))
        style.add_widget(self._gradient_host)
        self._gradient_host.hide()

        self._glow_mode = QComboBox()
        for value, label in TEXT_GLOW_MODE_OPTIONS:
            self._glow_mode.addItem(label, value)
        self._glow_mode.currentIndexChanged.connect(self._on_glow_mode_changed)
        style.add_widget(_stacked_field("Glow Mode", self._glow_mode))

        self._glow_gradient_host = QWidget()
        glow_grad_layout = QVBoxLayout(self._glow_gradient_host)
        glow_grad_layout.setContentsMargins(0, 0, 0, 0)
        glow_grad_layout.setSpacing(4)
        self._glow_gradient_direction = QComboBox()
        for value, label in TEXT_GRADIENT_DIRECTION_OPTIONS:
            self._glow_gradient_direction.addItem(label, value)
        self._glow_gradient_direction.currentIndexChanged.connect(
            lambda _i: self._emit_combo(
                self._glow_gradient_direction, f"{self._PREFIX}GlowGradientDirection"
            )
        )
        glow_grad_layout.addWidget(_stacked_field("Glow Gradient Direction", self._glow_gradient_direction))
        for field, label in (
            (f"{self._PREFIX}GlowGradientColor0", "Glow Gradient A"),
            (f"{self._PREFIX}GlowGradientColor1", "Glow Gradient B"),
            (f"{self._PREFIX}GlowGradientColor2", "Glow Gradient C"),
        ):
            widget, setter = build_color_field(
                label,
                value="#ff1a3c",
                on_change=lambda value, key=field: self._on_glow_gradient_stop_changed(key, value),
                parent=self,
                show_label=False,
            )
            self._color_setters[field] = setter
            glow_grad_layout.addWidget(_stacked_field(label, widget))
        style.add_widget(self._glow_gradient_host)
        self._glow_gradient_host.hide()

        self._build_list_color_fields(style)

        self._align_combo = QComboBox()
        for value, label in TEXT_ALIGN_OPTIONS:
            self._align_combo.addItem(label, value)
        self._align_combo.currentIndexChanged.connect(
            lambda _i: self._emit_combo(self._align_combo, f"{self._PREFIX}Align")
        )
        style.add_widget(_stacked_field("Alignment", self._align_combo))
        root.addWidget(style)
        root.addStretch()

    def _build_content_fields(self, section: InspectorSection) -> None:
        raise NotImplementedError

    def _build_list_color_fields(self, style: InspectorSection) -> None:
        return

    def mount_effect_pack_selector(self, widget: QWidget) -> None:
        if self._effect_pack_host is None:
            return
        while self._effect_pack_host.count():
            item = self._effect_pack_host.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
        self._effect_pack_host.addWidget(widget)

    def _emit_patch(self, patch: dict) -> None:
        if self._binding or not patch:
            return
        self.draft_patch_requested.emit(patch)

    def _emit_combo(self, combo: QComboBox | None, key: str) -> None:
        if self._binding or combo is None:
            return
        data = combo.currentData()
        if isinstance(data, str):
            self._emit_patch({key: data})

    def _on_fill_mode_changed(self, _index: int) -> None:
        if self._binding or self._fill_mode is None:
            return
        mode = str(self._fill_mode.currentData() or "solid")
        patch: dict = {f"{self._PREFIX}FillMode": mode}
        if mode == "gradient":
            colors = normalize_text_gradient_colors(
                self._bound_gradient_colors or ["#ffffff", "#22d3ee"],
                "#ffffff",
                require_stops=True,
            )
            patch[f"{self._PREFIX}GradientColors"] = colors
            self._bound_gradient_colors = list(colors)
        self._emit_patch(patch)
        self._sync_fill_visibility(mode)

    def _on_gradient_stop_changed(self, key: str, value: str) -> None:
        if self._binding:
            return
        stops = list(self._bound_gradient_colors) if self._bound_gradient_colors else ["#ffffff", "#22d3ee", "#ff4fd8"]
        while len(stops) < 3:
            stops.append(stops[-1] if stops else "#ffffff")
        index_map = {
            f"{self._PREFIX}GradientColor0": 0,
            f"{self._PREFIX}GradientColor1": 1,
            f"{self._PREFIX}GradientColor2": 2,
        }
        idx = index_map.get(key)
        if idx is None:
            return
        stops[idx] = value
        # Keep at least two stops; drop unused third if still default-padded.
        usable = stops[:3]
        colors = normalize_text_gradient_colors(usable, value, require_stops=True)
        self._bound_gradient_colors = list(colors)
        self._emit_patch(
            {
                f"{self._PREFIX}GradientColors": colors,
                f"{self._PREFIX}FillMode": "gradient",
            }
        )

    def _on_glow_mode_changed(self, _index: int) -> None:
        if self._binding or self._glow_mode is None:
            return
        mode = str(self._glow_mode.currentData() or "solid")
        patch: dict = {f"{self._PREFIX}GlowMode": mode}
        if mode == "gradient":
            colors = normalize_text_gradient_colors(
                self._bound_glow_gradient_colors or ["#ff1a3c", "#ff6a00"],
                "#ff1a3c",
                require_stops=True,
            )
            patch[f"{self._PREFIX}GlowGradientColors"] = colors
            self._bound_glow_gradient_colors = list(colors)
        self._emit_patch(patch)
        self._sync_glow_visibility(mode)

    def _on_glow_gradient_stop_changed(self, key: str, value: str) -> None:
        if self._binding:
            return
        stops = (
            list(self._bound_glow_gradient_colors)
            if self._bound_glow_gradient_colors
            else ["#ff1a3c", "#ff6a00", "#ffd166"]
        )
        while len(stops) < 3:
            stops.append(stops[-1] if stops else "#ff1a3c")
        index_map = {
            f"{self._PREFIX}GlowGradientColor0": 0,
            f"{self._PREFIX}GlowGradientColor1": 1,
            f"{self._PREFIX}GlowGradientColor2": 2,
        }
        idx = index_map.get(key)
        if idx is None:
            return
        stops[idx] = value
        colors = normalize_text_gradient_colors(stops[:3], value, require_stops=True)
        self._bound_glow_gradient_colors = list(colors)
        self._emit_patch(
            {
                f"{self._PREFIX}GlowGradientColors": colors,
                f"{self._PREFIX}GlowMode": "gradient",
            }
        )

    def _sync_fill_visibility(self, mode: str) -> None:
        is_gradient = str(mode or "").lower() == "gradient"
        if self._gradient_host is not None:
            self._gradient_host.setVisible(is_gradient)

    def _sync_glow_visibility(self, mode: str) -> None:
        is_gradient = str(mode or "").lower() == "gradient"
        if self._glow_gradient_host is not None:
            self._glow_gradient_host.setVisible(is_gradient)

    def _on_preset_changed(self, _index: int) -> None:
        if self._binding or self._preset_combo is None:
            return
        key = str(self._preset_combo.currentData() or "")
        if not key or key == self._selected_preset_key:
            return
        self._previous_preset_key = self._selected_preset_key
        self._selected_preset_key = key
        self.preset_apply_requested.emit(key)

    def _on_content_mode_changed(self, _index: int) -> None:
        if self._binding or self._content_mode is None:
            return
        data = self._content_mode.currentData()
        if isinstance(data, str):
            self._emit_patch({f"{self._PREFIX}ContentMode": data})
            self._sync_manual_visibility(data)

    def _sync_manual_visibility(self, mode: str) -> None:
        is_manual = str(mode or "").lower() == "manual"
        if self._manual_album is not None:
            self._manual_album.setVisible(is_manual)
        if self._manual_titles is not None:
            self._manual_titles.setVisible(is_manual)

    def _set_combo(self, combo: QComboBox | None, value: str) -> None:
        if combo is None:
            return
        key = str(value or "")
        index = combo.findData(key)
        if index < 0:
            index = combo.findText(key)
        if index < 0 and key:
            # System / custom font not yet in the list — keep it selectable.
            combo.addItem(key, key)
            index = combo.findData(key)
        if index < 0:
            index = 0
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def bind_draft(self, draft: dict, *, preview_lines: list[str] | None = None) -> None:
        _ = preview_lines
        self._binding = True
        try:
            enabled = bool(draft.get(f"{self._PREFIX}Enabled", False))
            if self._enable is not None:
                self._enable.setChecked(enabled)
            mode = str(draft.get(f"{self._PREFIX}ContentMode") or "pipeline")
            self._set_combo(self._content_mode, mode)
            self._sync_manual_visibility(mode)
            preset = str(draft.get(f"{self._PREFIX}StylePreset") or "")
            self._selected_preset_key = preset
            self._set_combo(self._preset_combo, preset)
            self._set_combo(self._font_combo, str(draft.get(f"{self._PREFIX}FontFamily") or "arial"))
            self._set_combo(self._align_combo, str(draft.get(f"{self._PREFIX}Align") or "left"))
            fill_mode = str(draft.get(f"{self._PREFIX}FillMode") or "solid")
            self._set_combo(self._fill_mode, fill_mode)
            self._set_combo(
                self._gradient_direction,
                str(draft.get(f"{self._PREFIX}GradientDirection") or "vertical"),
            )
            self._sync_fill_visibility(fill_mode)
            glow_mode = str(draft.get(f"{self._PREFIX}GlowMode") or "solid")
            self._set_combo(self._glow_mode, glow_mode)
            self._set_combo(
                self._glow_gradient_direction,
                str(draft.get(f"{self._PREFIX}GlowGradientDirection") or "horizontal"),
            )
            self._sync_glow_visibility(glow_mode)
            if self._bold is not None:
                self._bold.setChecked(bool(draft.get(f"{self._PREFIX}Bold", False)))
            if self._italic is not None:
                self._italic.setChecked(bool(draft.get(f"{self._PREFIX}Italic", False)))
            for key, setter in self._float_setters.items():
                if callable(setter):
                    setter(float(draft.get(key, 0) or 0))
            gradient = draft.get(f"{self._PREFIX}GradientColors")
            colors = list(gradient) if isinstance(gradient, list) else []
            self._bound_gradient_colors = list(colors)
            padded = list(colors)
            while len(padded) < 3:
                padded.append(padded[-1] if padded else str(draft.get(f"{self._PREFIX}Color") or "#ffffff"))
            glow_gradient = draft.get(f"{self._PREFIX}GlowGradientColors")
            glow_colors = list(glow_gradient) if isinstance(glow_gradient, list) else []
            self._bound_glow_gradient_colors = list(glow_colors)
            glow_padded = list(glow_colors)
            while len(glow_padded) < 3:
                glow_padded.append(
                    glow_padded[-1]
                    if glow_padded
                    else str(draft.get(f"{self._PREFIX}GlowColor") or "#ff1a3c")
                )
            draft_colors = {
                f"{self._PREFIX}GradientColor0": padded[0],
                f"{self._PREFIX}GradientColor1": padded[1],
                f"{self._PREFIX}GradientColor2": padded[2],
                f"{self._PREFIX}GlowGradientColor0": glow_padded[0],
                f"{self._PREFIX}GlowGradientColor1": glow_padded[1],
                f"{self._PREFIX}GlowGradientColor2": glow_padded[2],
            }
            for key, setter in self._color_setters.items():
                if not callable(setter):
                    continue
                if key in draft_colors:
                    setter(str(draft_colors[key]))
                else:
                    setter(str(draft.get(key) or "#ffffff"))
            self._bind_domain_fields(draft)
        finally:
            self._binding = False

    def _bind_domain_fields(self, draft: dict) -> None:
        return


class AlbumInspector(_TextDomainInspectorBase):
    _DOMAIN = "album"
    _PREFIX = "album"
    _ENABLE_LABEL = "Enable Album"
    _TITLE = "Album"
    _SUBTITLE = "Album name from pipeline or manual entry. Saved with the video template."

    def _build_content_fields(self, section: InspectorSection) -> None:
        self._manual_album = QLineEdit()
        self._manual_album.setPlaceholderText("Album name")
        self._manual_album.editingFinished.connect(self._on_manual_album)
        section.add_widget(_stacked_field("Manual name", self._manual_album))

    def _on_manual_album(self) -> None:
        if self._binding or self._manual_album is None:
            return
        self._emit_patch({"albumManualText": self._manual_album.text().strip()})

    def _bind_domain_fields(self, draft: dict) -> None:
        if self._manual_album is not None:
            self._manual_album.blockSignals(True)
            self._manual_album.setText(str(draft.get("albumManualText") or ""))
            self._manual_album.blockSignals(False)


class TitleInspector(_TextDomainInspectorBase):
    _DOMAIN = "title"
    _PREFIX = "title"
    _ENABLE_LABEL = "Enable Playlist"
    _TITLE = "Playlist"
    _SUBTITLE = (
        "Long-play track list. Auto-loads from the pipeline track list. "
        "Pick a Playlist Look, layout, and glass panel."
    )

    def _build_content_fields(self, section: InspectorSection) -> None:
        self._playlist_look = QComboBox()
        self._playlist_look.addItem("Custom / none", "")
        for value, label in PLAYLIST_LOOK_PRESET_OPTIONS:
            self._playlist_look.addItem(label, value)
        self._playlist_look.setToolTip("Playlist Look — layout, glass panel, fonts, and colors")
        self._playlist_look.currentIndexChanged.connect(self._on_playlist_look_changed)
        section.add_widget(_stacked_field("Playlist Look", self._playlist_look))

        self._list_style = QComboBox()
        for value, label in TITLE_LIST_STYLE_OPTIONS:
            self._list_style.addItem(label, value)
        self._list_style.currentIndexChanged.connect(
            lambda _i: self._emit_combo(self._list_style, "titleListStyle")
        )
        section.add_widget(_stacked_field("List style", self._list_style))

        self._number_indent = QComboBox()
        for value, label in TITLE_NUMBER_INDENT_OPTIONS:
            self._number_indent.addItem(label, value)
        self._number_indent.currentIndexChanged.connect(
            lambda _i: self._emit_combo(self._number_indent, "titleNumberIndent")
        )
        section.add_widget(_stacked_field("Number indent", self._number_indent))

        self._layout_combo = QComboBox()
        for value, label in TITLE_LAYOUT_OPTIONS:
            self._layout_combo.addItem(label, value)
        self._layout_combo.currentIndexChanged.connect(self._on_playlist_layout_changed)
        section.add_widget(_stacked_field("Layout", self._layout_combo))

        for field, label in (
            ("titleShowDurations", "Show durations"),
            ("titleNowPlayingEnabled", "Now Playing highlight"),
            ("titleNowPlayingPill", "NOW PLAYING pill"),
            ("titleTracklistHeader", "TRACKLIST header"),
            ("titleActiveRowPlate", "Active row neon plate"),
            ("titleTrackCountBadge", "Track count badge"),
        ):
            box = StudioCheckBox(label)
            box.toggled.connect(
                lambda checked, key=field: (
                    None if self._binding else self._emit_patch({key: bool(checked)})
                )
            )
            self._toggle_fields[field] = box
            section.add_widget(box)

        for field, label, minimum, maximum, step in (
            ("titlePanelOpacity", "Panel Opacity", 0.05, 1.0, 0.01),
            ("titlePanelFrost", "Panel Frost", 0.0, 1.0, 0.01),
            ("titlePanelBorderWidth", "Panel Border", 0.0, 8.0, 0.25),
            ("titlePanelSpecular", "Panel Specular", 0.0, 1.0, 0.01),
        ):
            widget, setter = build_float_slider(
                label,
                minimum=minimum,
                maximum=maximum,
                step=step,
                value=minimum,
                on_change=lambda value, key=field: self._emit_patch({key: round(float(value), 3)}),
            )
            self._float_setters[field] = setter
            section.add_widget(widget)

        for field, label, default in (
            ("titlePanelBorderColor", "Panel Border Color", "#94a3b8"),
            ("titlePanelFill", "Panel Fill", "#0f172a"),
        ):
            widget, setter = build_color_field(
                label,
                value=default,
                on_change=lambda value, key=field: self._emit_patch({key: value}),
                parent=self,
                show_label=False,
            )
            self._color_setters[field] = setter
            section.add_widget(_stacked_field(label, widget))

        self._manual_titles = QPlainTextEdit()
        self._manual_titles.setPlaceholderText("One title per line (manual mode)")
        self._manual_titles.setMaximumBlockCount(200)
        self._manual_titles.setFixedHeight(110)
        self._manual_titles.textChanged.connect(self._on_manual_titles)
        section.add_widget(self._manual_titles)

    def _on_playlist_layout_changed(self, _index: int) -> None:
        if self._binding or self._layout_combo is None:
            return
        key = self._layout_combo.currentData()
        if not isinstance(key, str):
            return
        self._emit_patch(build_playlist_layout_side_draft_patch(key))

    def _on_playlist_look_changed(self, _index: int) -> None:
        if self._binding or self._playlist_look is None:
            return
        key = self._playlist_look.currentData()
        if not isinstance(key, str) or not key:
            self._emit_patch({"titlePlaylistLook": ""})
            return
        patch = build_playlist_look_draft_patch(key)
        if patch:
            self._emit_patch(patch)

    def _build_list_color_fields(self, style: InspectorSection) -> None:
        for field, label in (
            ("titleListColor", "List Color"),
            ("titleListActiveColor", "Active Color"),
        ):
            widget, setter = build_color_field(
                label,
                value="#ffffff",
                on_change=lambda value, key=field: self._emit_patch({key: value}),
                parent=self,
                show_label=False,
            )
            self._color_setters[field] = setter
            style.add_widget(_stacked_field(label, widget))
        widget, setter = build_float_slider(
            "Active Index",
            minimum=-1,
            maximum=32,
            step=1,
            value=0,
            on_change=lambda value: self._emit_patch({"titleListActiveIndex": int(round(value))}),
        )
        self._float_setters["titleListActiveIndex"] = setter
        style.add_widget(widget)
        # Preview/export override this from the selected / playing / exporting track.
        note = QLabel("Auto: follows selected / playing / exporting track.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        style.add_widget(note)

    def _on_manual_titles(self) -> None:
        if self._binding or self._manual_titles is None:
            return
        lines = [line.strip() for line in self._manual_titles.toPlainText().splitlines() if line.strip()]
        self._emit_patch({"titleManualTitles": lines})

    def _bind_domain_fields(self, draft: dict) -> None:
        self._set_combo(self._playlist_look, str(draft.get("titlePlaylistLook") or ""))
        self._set_combo(self._list_style, str(draft.get("titleListStyle") or "number"))
        self._set_combo(self._number_indent, str(draft.get("titleNumberIndent") or "aligned"))
        self._set_combo(self._layout_combo, str(draft.get("titleLayout") or "column"))
        for field, checkbox in self._toggle_fields.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(draft.get(field)))
            checkbox.blockSignals(False)
        if self._manual_titles is not None:
            titles = draft.get("titleManualTitles")
            text = "\n".join(str(item) for item in titles) if isinstance(titles, list) else ""
            if self._manual_titles.toPlainText() != text:
                self._manual_titles.blockSignals(True)
                self._manual_titles.setPlainText(text)
                self._manual_titles.blockSignals(False)
