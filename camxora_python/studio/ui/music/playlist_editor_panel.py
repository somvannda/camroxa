"""Playlist tab — Templates and Settings sub-tabs."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from studio.core.playlist_layout import is_forest_mist_layout, is_standalone_track_list_layout
from studio.core.playlist_palette import (
    GLASS_COLOR_KEYS,
    PALETTE_SLOT_KEYS,
    PALETTE_SLOT_LABELS,
    STANDALONE_CUSTOM_COLOR_KEYS,
    apply_palette_slot_for_layout,
    hex_with_alpha_percent,
    pick_color_hex,
    rgba_alpha_percent,
    rgb_hex_from_color,
    swatch_stylesheet,
)
from studio.core.playlist_fonts import (
    PLAYLIST_FONT_CHOICES,
    PLAYLIST_FONT_VARIANTS,
    PLAYLIST_FONT_VARIANT_LABELS,
    font_choice_index,
    font_variant_index,
)
from studio.core.playlist_row_chrome import PLAY_WHEN_PLAYING, sync_legacy_row_flags
from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_style import apply_style_to_settings
from studio.core.playlist_sub_template_styles import reset_row_chrome_to_default, reset_sub_template_style, switch_sub_template
from studio.render.playlist_cache import invalidate_playlist_render_cache
from studio.ui.inspector_layout import (
    FIELD_GAP,
    FORM_LABEL_WIDTH,
    INSPECTOR_CONTENT_MAX_WIDTH,
    SECTION_GAP,
    add_section_spacer,
    apply_scroll_page_layout,
)
from studio.ui.music.playlist_background_picker import PlaylistBackgroundPicker
from studio.ui.music.playlist_card_position_bar import PlaylistCardPositionBar
from studio.ui.music.playlist_color_filter_grid import PlaylistColorFilterGrid
from studio.ui.music.playlist_presets import PRESETS_BY_ID
from studio.ui.music.playlist_settings_section import PlaylistSettingsSection
from studio.ui.music.playlist_style_picker import PlaylistStylePicker


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _form_label(text: str) -> QLabel:
    """Fixed-width label column for settings form rows."""
    label = _field_label(text)
    label.setFixedWidth(FORM_LABEL_WIDTH)
    label.setWordWrap(False)
    return label


class _ScrollPage(QWidget):
    def __init__(self, parent: QWidget | None = None, *, settings_page: bool = False) -> None:
        super().__init__(parent)
        self._settings_page = settings_page
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._inner = QWidget()
        if not settings_page:
            # Only cap non-settings pages; Playlist Settings fills the panel.
            self._inner.setMaximumWidth(INSPECTOR_CONTENT_MAX_WIDTH)
        self._layout = QVBoxLayout(self._inner)
        if settings_page:
            from studio.ui.inspector_layout import apply_playlist_settings_layout

            apply_playlist_settings_layout(self._layout)
        else:
            apply_scroll_page_layout(self._layout)
        self._scroll.setWidget(self._inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scroll)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        viewport_w = self._scroll.viewport().width()
        if viewport_w > 0:
            if self._settings_page:
                self._inner.setFixedWidth(viewport_w)
            else:
                self._inner.setFixedWidth(min(viewport_w, INSPECTOR_CONTENT_MAX_WIDTH))


class PlaylistEditorPanel(QWidget):
    settings_changed = Signal()

    _TAB_TEMPLATES = 0
    _TAB_SETTINGS = 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = PlaylistSettings()
        self._color_buttons: dict[str, QPushButton] = {}
        self._color_rows: dict[str, QWidget] = {}
        self._sliders: dict[str, QSlider] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._typo_rows: dict[str, QWidget] = {}
        self._typo_variant_combos: dict[str, QComboBox] = {}
        self._font_combo: QComboBox | None = None
        self._active_row_opacity_slider: QSlider | None = None

        self._stack = QStackedWidget(self)
        self._templates_page = self._build_templates_page()
        self._settings_page = self._build_settings_page()
        self._stack.addWidget(self._templates_page)
        self._stack.addWidget(self._settings_page)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

    def set_tab_index(self, index: int) -> None:
        self._stack.setCurrentIndex(max(0, min(index, self._stack.count() - 1)))

    def _build_templates_page(self) -> QWidget:
        page = _ScrollPage()
        layout = page._layout

        self._template_label = QLabel("")
        self._template_label.setObjectName("DetailsSectionTitle")
        layout.addWidget(self._template_label)

        add_section_spacer(layout)
        self._style_picker = PlaylistStylePicker()
        self._style_picker.style_changed.connect(self._on_style_changed)
        layout.addWidget(self._style_picker)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = _ScrollPage(settings_page=True)
        layout = page._layout
        layout.setSpacing(SECTION_GAP)

        scene_section = PlaylistSettingsSection("Scene background")
        self._background_picker = PlaylistBackgroundPicker()
        self._background_picker.background_changed.connect(self.settings_changed.emit)
        scene_section.body.addWidget(self._background_picker)
        layout.addWidget(scene_section)

        position_section = PlaylistSettingsSection("Position")
        self._position_bar = PlaylistCardPositionBar()
        self._position_bar.position_changed.connect(self._on_position_changed)
        position_section.body.addWidget(self._position_bar)
        layout.addWidget(position_section)

        color_sets_section = PlaylistSettingsSection("Color sets")
        self._color_filters = PlaylistColorFilterGrid()
        self._color_filters.style_changed.connect(self._on_color_filter_changed)
        color_sets_section.body.addWidget(self._color_filters)
        layout.addWidget(color_sets_section)

        self._custom_colors_section = PlaylistSettingsSection("Custom colors")
        self._color_rows_host = QWidget()
        self._custom_colors_layout = QVBoxLayout(self._color_rows_host)
        self._custom_colors_layout.setContentsMargins(0, 0, 0, 0)
        self._custom_colors_layout.setSpacing(FIELD_GAP)
        self._custom_colors_section.body.addWidget(self._color_rows_host)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        self._reset_style_btn = QPushButton("Reset style to default")
        self._reset_style_btn.setObjectName("GhostButton")
        self._reset_style_btn.clicked.connect(self._on_reset_style_to_default)
        reset_row.addWidget(self._reset_style_btn)
        reset_wrap = QWidget()
        reset_wrap.setLayout(reset_row)
        self._custom_colors_section.body.addWidget(reset_wrap)
        self._build_color_picker_rows()
        layout.addWidget(self._custom_colors_section)

        typo_section = PlaylistSettingsSection("Typography")
        font_row = QHBoxLayout()
        font_row.setContentsMargins(0, 0, 0, 0)
        font_row.setSpacing(8)
        font_row.addWidget(_form_label("Font"))
        self._font_combo = QComboBox()
        for _fid, name in PLAYLIST_FONT_CHOICES:
            self._font_combo.addItem(name)
        self._font_combo.currentIndexChanged.connect(self._on_font_changed)
        font_row.addWidget(self._font_combo, 1)
        font_wrap = QWidget()
        font_wrap.setLayout(font_row)
        typo_section.body.addWidget(font_wrap)
        for key, label, default, max_val in (
            ("album_title_size", "Album title", 28, 64),
            ("now_playing_size", "Now playing", 18, 48),
            ("song_title_size", "Song title", 15, 36),
            ("song_meta_size", "Song meta", 12, 24),
        ):
            row_wrap = QWidget()
            row_layout = QVBoxLayout(row_wrap)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            row_layout.addLayout(self._slider_row(key, label, default, max_val))
            if key == "song_title_size":
                row_layout.addLayout(self._typo_variant_row("song_title_variant", "Song title"))
            elif key == "song_meta_size":
                row_layout.addLayout(self._typo_variant_row("song_meta_variant", "Song meta"))
            self._typo_rows[key] = row_wrap
            typo_section.body.addWidget(row_wrap)
        layout.addWidget(typo_section)

        layout_section = PlaylistSettingsSection("Layout")
        self._cover_size_row = QWidget()
        self._cover_size_row.setLayout(self._slider_row("cover_size_pct", "Cover size", 38, 60))
        layout_section.body.addWidget(self._cover_size_row)
        layout_section.body.addLayout(self._slider_row("corner_radius", "Corner radius", 12, 40))
        layout_section.body.addLayout(self._slider_row("list_row_gap", "List row gap", 6, 24))

        self._show_numbers = QCheckBox("Show track numbers")
        self._show_numbers.setChecked(True)
        self._show_numbers.toggled.connect(self._on_show_numbers)
        layout_section.body.addWidget(self._show_numbers)

        self._show_durations = QCheckBox("Show durations")
        self._show_durations.setChecked(True)
        self._show_durations.toggled.connect(self._on_show_durations)
        layout_section.body.addWidget(self._show_durations)
        layout.addWidget(layout_section)

        self._row_elements_section = PlaylistSettingsSection("Row elements")
        self._row_show_numbers = QCheckBox("Show track numbers")
        self._row_show_numbers.toggled.connect(self._on_row_numbers_enabled)
        self._row_elements_section.body.addWidget(self._row_show_numbers)

        num_fmt_row = QHBoxLayout()
        num_fmt_row.setContentsMargins(0, 0, 0, 0)
        num_fmt_row.setSpacing(8)
        num_fmt_row.addWidget(_form_label("Number format"))
        self._row_number_format = QComboBox()
        self._row_number_format.addItem("01, 02, …", "padded2")
        self._row_number_format.addItem("1, 2, …", "plain")
        self._row_number_format.currentIndexChanged.connect(self._on_row_number_format)
        num_fmt_row.addWidget(self._row_number_format, 1)
        num_fmt_wrap = QWidget()
        num_fmt_wrap.setLayout(num_fmt_row)
        self._row_elements_section.body.addWidget(num_fmt_wrap)

        self._row_play_enabled = QCheckBox("Show play icon")
        self._row_play_enabled.toggled.connect(self._on_row_play_enabled)
        self._row_elements_section.body.addWidget(self._row_play_enabled)

        self._row_play_inactive = QCheckBox("Play icon on inactive rows")
        self._row_play_inactive.toggled.connect(self._on_row_play_inactive)
        self._row_elements_section.body.addWidget(self._row_play_inactive)

        when_row = QHBoxLayout()
        when_row.setContentsMargins(0, 0, 0, 0)
        when_row.setSpacing(8)
        when_row.addWidget(_form_label("When playing"))
        self._row_when_playing = QComboBox()
        for mode in PLAY_WHEN_PLAYING:
            label = {
                "play_icon": "Play icon",
                "animation": "Equalizer bars",
                "both": "Play icon + bars",
                "hide": "Hide leading chrome",
            }.get(mode, mode)
            self._row_when_playing.addItem(label, mode)
        self._row_when_playing.currentIndexChanged.connect(self._on_row_when_playing)
        when_row.addWidget(self._row_when_playing, 1)
        when_wrap = QWidget()
        when_wrap.setLayout(when_row)
        self._row_elements_section.body.addWidget(when_wrap)

        self._row_show_durations = QCheckBox("Show durations")
        self._row_show_durations.toggled.connect(self._on_row_duration_enabled)
        self._row_elements_section.body.addWidget(self._row_show_durations)

        self._row_show_animation = QCheckBox("Show playing animation")
        self._row_show_animation.toggled.connect(self._on_row_animation_enabled)
        self._row_elements_section.body.addWidget(self._row_show_animation)

        anim_place_row = QHBoxLayout()
        anim_place_row.setContentsMargins(0, 0, 0, 0)
        anim_place_row.setSpacing(8)
        anim_place_row.addWidget(_form_label("Animation placement"))
        self._row_anim_placement = QComboBox()
        self._row_anim_placement.addItem("Leading (after numbers)", "leading")
        self._row_anim_placement.addItem("Trailing (end of row)", "trailing")
        self._row_anim_placement.currentIndexChanged.connect(self._on_row_anim_placement)
        anim_place_row.addWidget(self._row_anim_placement, 1)
        anim_place_wrap = QWidget()
        anim_place_wrap.setLayout(anim_place_row)
        self._row_elements_section.body.addWidget(anim_place_wrap)

        reset_row_btn_row = QHBoxLayout()
        reset_row_btn_row.addStretch(1)
        self._reset_row_chrome_btn = QPushButton("Reset row defaults")
        self._reset_row_chrome_btn.setObjectName("GhostButton")
        self._reset_row_chrome_btn.clicked.connect(self._on_reset_row_chrome)
        reset_row_btn_row.addWidget(self._reset_row_chrome_btn)
        reset_row_btn_wrap = QWidget()
        reset_row_btn_wrap.setLayout(reset_row_btn_row)
        self._row_elements_section.body.addWidget(reset_row_btn_wrap)

        layout.addWidget(self._row_elements_section)

        layout.addStretch(1)
        return page

    def _build_color_picker_rows(self) -> None:
        while self._custom_colors_layout.count():
            item = self._custom_colors_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._color_buttons.clear()
        self._color_rows.clear()

        if is_standalone_track_list_layout(self._settings):
            fields = [(key, PALETTE_SLOT_LABELS[key]) for key in STANDALONE_CUSTOM_COLOR_KEYS]
        else:
            fields = list(GLASS_COLOR_KEYS)

        for key, label in fields:
            row_widget = QWidget()
            if key == "selected_row" and is_standalone_track_list_layout(self._settings):
                row_widget.setLayout(self._active_row_fill_row())
            else:
                row_widget.setLayout(self._color_row(key, label))
            self._color_rows[key] = row_widget
            self._custom_colors_layout.addWidget(row_widget)

    def _active_row_fill_row(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(6)
        wrap.addLayout(self._color_row("selected_row", PALETTE_SLOT_LABELS["selected_row"]))

        opacity_row = QHBoxLayout()
        opacity_row.setContentsMargins(0, 0, 0, 0)
        opacity_row.setSpacing(8)
        opacity_row.addWidget(_form_label("Fill opacity"))
        opacity_val = QLabel("40")
        opacity_val.setObjectName("DetailsFieldValue")
        self._value_labels["active_row_opacity"] = opacity_val
        opacity_row.addWidget(opacity_val, 0, Qt.AlignmentFlag.AlignRight)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(40)
        slider.valueChanged.connect(self._on_active_row_opacity)
        self._active_row_opacity_slider = slider

        wrap.addLayout(opacity_row)
        wrap.addWidget(slider)
        return wrap

    def _sync_active_row_opacity_controls(self) -> None:
        slider = self._active_row_opacity_slider
        if slider is None:
            return
        current = self._settings.colors.get("selected_row", "#f2f2f7")
        alpha_pct = rgba_alpha_percent(current)
        slider.blockSignals(True)
        slider.setValue(alpha_pct)
        slider.blockSignals(False)
        val_lbl = self._value_labels.get("active_row_opacity")
        if val_lbl is not None:
            val_lbl.setText(str(alpha_pct))

    def _apply_active_row_fill(self, *, rgb_hex: str | None = None, alpha_pct: int | None = None) -> None:
        current = self._settings.colors.get("selected_row", "#f2f2f7")
        rgb = rgb_hex or rgb_hex_from_color(current)
        if alpha_pct is None:
            slider = self._active_row_opacity_slider
            alpha_pct = slider.value() if slider is not None else rgba_alpha_percent(current)
        hex_color = hex_with_alpha_percent(rgb, alpha_pct)
        layout_style = "forest_mist" if is_forest_mist_layout(self._settings) else "minimal_white"
        self._settings.colors = apply_palette_slot_for_layout(
            self._settings.colors,
            "selected_row",
            hex_color,
            layout_style=layout_style,
        )
        self._settings.color_filter_id = "custom"

    def _on_active_row_opacity(self, value: int) -> None:
        val_lbl = self._value_labels.get("active_row_opacity")
        if val_lbl is not None:
            val_lbl.setText(str(value))
        self._apply_active_row_fill(alpha_pct=value)
        invalidate_playlist_render_cache()
        self._color_filters.load_settings(self._settings)
        self._sync_color_swatches()
        self.settings_changed.emit()

    def _color_row(self, key: str, label: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(_form_label(label))
        btn = QPushButton()
        btn.setFixedSize(40, 26)
        btn.setObjectName("ColorSwatchButton")
        btn.clicked.connect(lambda _=False, k=key: self._pick_color(k))
        self._color_buttons[key] = btn
        row.addWidget(btn)
        row.addStretch(1)
        return row

    def _slider_row(self, key: str, label: str, default: int, max_val: int) -> QVBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(_form_label(label))
        val_label = QLabel(str(default))
        val_label.setObjectName("DetailsFieldValue")
        val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value_labels[key] = val_label
        row.addWidget(val_label, 1)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(8 if "size" in key else 0, max_val)
        slider.setValue(default)
        slider.valueChanged.connect(lambda v, k=key: self._on_slider(k, v))
        self._sliders[key] = slider

        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(FIELD_GAP)
        wrap.addLayout(row)
        wrap.addWidget(slider)
        return wrap

    def _typo_variant_row(self, variant_key: str, label: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(_form_label(f"{label} style"))
        combo = QComboBox()
        for variant in PLAYLIST_FONT_VARIANTS:
            combo.addItem(PLAYLIST_FONT_VARIANT_LABELS[variant], variant)
        combo.currentIndexChanged.connect(lambda idx, k=variant_key: self._on_typo_variant(k, idx))
        self._typo_variant_combos[variant_key] = combo
        row.addWidget(combo, 1)
        return row

    def _on_style_changed(self) -> None:
        picked = self._style_picker.settings()
        switch_sub_template(self._settings, picked.sub_template_id)
        apply_style_to_settings(self._settings)
        self._style_picker.load_settings(self._settings)
        invalidate_playlist_render_cache()
        self._rebuild_color_pickers()
        self._sync_color_swatches()
        self._color_filters.load_settings(self._settings)
        self._position_bar.bind_settings(self._settings)
        self._load_panel_from_settings()
        self._update_minimal_white_ui()
        self.settings_changed.emit()

    def _on_color_filter_changed(self) -> None:
        self._settings = self._color_filters.settings()
        invalidate_playlist_render_cache()
        self._sync_color_swatches()
        self.settings_changed.emit()

    def _on_position_changed(self) -> None:
        invalidate_playlist_render_cache()
        self.settings_changed.emit()

    def load_settings(self, settings: PlaylistSettings) -> None:
        self._settings = settings
        preset = PRESETS_BY_ID.get(settings.template_id)
        name = preset.name if preset else settings.template_id
        self._template_label.setText(f"Template: {name}")

        apply_style_to_settings(settings)
        self._style_picker.load_settings(settings)
        self._rebuild_color_pickers()
        self._color_filters.load_settings(settings)
        self._position_bar.bind_settings(settings)
        self._background_picker.bind_settings(settings)
        self._sync_color_swatches()
        self._load_panel_from_settings()
        self._update_minimal_white_ui()

    def _load_panel_from_settings(self) -> None:
        typo = self._settings.typography
        slider_values = {
            "album_title_size": typo.album_title_size,
            "now_playing_size": typo.now_playing_size,
            "song_title_size": typo.song_title_size,
            "song_meta_size": typo.song_meta_size,
            "cover_size_pct": self._settings.cover_size_pct,
            "corner_radius": self._settings.corner_radius,
            "list_row_gap": self._settings.list_row_gap,
        }
        for key, val in slider_values.items():
            slider = self._sliders.get(key)
            if slider is not None:
                slider.blockSignals(True)
                slider.setValue(val)
                slider.blockSignals(False)
            val_lbl = self._value_labels.get(key)
            if val_lbl is not None:
                val_lbl.setText(str(val))

        self._show_numbers.blockSignals(True)
        self._show_numbers.setChecked(self._settings.show_track_numbers)
        self._show_numbers.blockSignals(False)
        self._show_durations.blockSignals(True)
        self._show_durations.setChecked(self._settings.show_durations)
        self._show_durations.blockSignals(False)

        self._sync_row_chrome_controls()

        if self._font_combo is not None:
            self._font_combo.blockSignals(True)
            self._font_combo.setCurrentIndex(font_choice_index(typo.font_family))
            self._font_combo.blockSignals(False)

        for variant_key, combo in self._typo_variant_combos.items():
            current = getattr(typo, variant_key, "normal")
            combo.blockSignals(True)
            combo.setCurrentIndex(font_variant_index(current))
            combo.blockSignals(False)

    def _sync_row_chrome_controls(self) -> None:
        chrome = self._settings.row_chrome
        blocks = (
            (self._row_show_numbers, chrome.numbers.enabled),
            (self._row_play_enabled, chrome.play.enabled),
            (self._row_play_inactive, chrome.play.show_on_inactive),
            (self._row_show_durations, chrome.duration.enabled),
            (self._row_show_animation, chrome.animation.enabled),
        )
        for widget, checked in blocks:
            widget.blockSignals(True)
            widget.setChecked(checked)
            widget.blockSignals(False)

        fmt_idx = self._row_number_format.findData(chrome.numbers.format)
        self._row_number_format.blockSignals(True)
        self._row_number_format.setCurrentIndex(max(0, fmt_idx))
        self._row_number_format.blockSignals(False)

        when_idx = self._row_when_playing.findData(chrome.play.when_playing)
        self._row_when_playing.blockSignals(True)
        self._row_when_playing.setCurrentIndex(max(0, when_idx))
        self._row_when_playing.blockSignals(False)

        place_idx = self._row_anim_placement.findData(chrome.animation.placement)
        self._row_anim_placement.blockSignals(True)
        self._row_anim_placement.setCurrentIndex(max(0, place_idx))
        self._row_anim_placement.blockSignals(False)

    def _emit_row_chrome_changed(self) -> None:
        sync_legacy_row_flags(self._settings)
        invalidate_playlist_render_cache()
        self.settings_changed.emit()

    def _on_row_numbers_enabled(self, checked: bool) -> None:
        self._settings.row_chrome.numbers.enabled = checked
        self._emit_row_chrome_changed()

    def _on_row_number_format(self, index: int) -> None:
        fmt = self._row_number_format.itemData(index)
        if fmt:
            self._settings.row_chrome.numbers.format = str(fmt)
            self._emit_row_chrome_changed()

    def _on_row_play_enabled(self, checked: bool) -> None:
        self._settings.row_chrome.play.enabled = checked
        self._emit_row_chrome_changed()

    def _on_row_play_inactive(self, checked: bool) -> None:
        self._settings.row_chrome.play.show_on_inactive = checked
        self._emit_row_chrome_changed()

    def _on_row_when_playing(self, index: int) -> None:
        mode = self._row_when_playing.itemData(index)
        if mode:
            self._settings.row_chrome.play.when_playing = str(mode)
            self._emit_row_chrome_changed()

    def _on_row_duration_enabled(self, checked: bool) -> None:
        self._settings.row_chrome.duration.enabled = checked
        self._emit_row_chrome_changed()

    def _on_row_animation_enabled(self, checked: bool) -> None:
        self._settings.row_chrome.animation.enabled = checked
        self._emit_row_chrome_changed()

    def _on_row_anim_placement(self, index: int) -> None:
        place = self._row_anim_placement.itemData(index)
        if place:
            self._settings.row_chrome.animation.placement = str(place)
            self._emit_row_chrome_changed()

    def _on_reset_row_chrome(self) -> None:
        reset_row_chrome_to_default(self._settings)
        invalidate_playlist_render_cache()
        self._sync_row_chrome_controls()
        self._show_numbers.blockSignals(True)
        self._show_numbers.setChecked(self._settings.show_track_numbers)
        self._show_numbers.blockSignals(False)
        self._show_durations.blockSignals(True)
        self._show_durations.setChecked(self._settings.show_durations)
        self._show_durations.blockSignals(False)
        self.settings_changed.emit()

    def _on_reset_style_to_default(self) -> None:
        reset_sub_template_style(self._settings)
        apply_style_to_settings(self._settings)
        invalidate_playlist_render_cache()
        self._color_filters.load_settings(self._settings)
        self._position_bar.bind_settings(self._settings)
        self._sync_color_swatches()
        self._load_panel_from_settings()
        self._update_minimal_white_ui()
        self.settings_changed.emit()

    def _rebuild_color_pickers(self) -> None:
        known_keys = set(PALETTE_SLOT_KEYS) | set(STANDALONE_CUSTOM_COLOR_KEYS) | {key for key, _ in GLASS_COLOR_KEYS}
        for key in known_keys:
            self._color_rows.pop(key, None)
            self._color_buttons.pop(key, None)
        self._active_row_opacity_slider = None
        self._value_labels.pop("active_row_opacity", None)
        self._build_color_picker_rows()
        self._sync_color_swatches()

    def _sync_color_swatches(self) -> None:
        for key, btn in self._color_buttons.items():
            hex_color = self._settings.colors.get(key, "#ffffff")
            btn.setStyleSheet(swatch_stylesheet(hex_color))
        self._sync_active_row_opacity_controls()

    def _update_minimal_white_ui(self) -> None:
        minimal = is_standalone_track_list_layout(self._settings)
        self._cover_size_row.setVisible(not minimal)
        self._show_numbers.setVisible(not minimal)
        self._show_durations.setVisible(not minimal)
        self._row_elements_section.setVisible(minimal)
        reset_btn = getattr(self, "_reset_style_btn", None)
        if reset_btn is not None:
            try:
                reset_btn.setVisible(minimal)
            except RuntimeError:
                pass
        for key in ("album_title_size", "now_playing_size"):
            row = self._typo_rows.get(key)
            if row is not None:
                row.setVisible(not minimal)

    def settings(self) -> PlaylistSettings:
        return self._settings

    def _pick_color(self, key: str) -> None:
        current = self._settings.colors.get(key, "#ffffff")
        if is_standalone_track_list_layout(self._settings) and key == "selected_row":
            rgb_current = rgb_hex_from_color(current)
            picked_rgb = pick_color_hex(
                self,
                title=f"Pick {PALETTE_SLOT_LABELS.get(key, key)}",
                current=rgb_current,
                with_alpha=False,
            )
            if picked_rgb is None:
                return
            self._apply_active_row_fill(rgb_hex=picked_rgb)
            invalidate_playlist_render_cache()
            self._color_filters.load_settings(self._settings)
            self._sync_color_swatches()
            self.settings_changed.emit()
            return

        hex_color = pick_color_hex(
            self,
            title=f"Pick {PALETTE_SLOT_LABELS.get(key, key)}",
            current=current,
            with_alpha=False,
        )
        if hex_color is None:
            return
        if key == "active_text":
            self._settings.colors["active_text"] = hex_color
        elif is_standalone_track_list_layout(self._settings) and key in PALETTE_SLOT_KEYS:
            layout_style = "forest_mist" if is_forest_mist_layout(self._settings) else "minimal_white"
            self._settings.colors = apply_palette_slot_for_layout(
                self._settings.colors,
                key,
                hex_color,
                layout_style=layout_style,
            )
        else:
            self._settings.colors[key] = hex_color
        self._settings.color_filter_id = "custom"

        invalidate_playlist_render_cache()
        self._color_filters.load_settings(self._settings)
        self._sync_color_swatches()
        self.settings_changed.emit()

    def _on_typo_variant(self, variant_key: str, index: int) -> None:
        combo = self._typo_variant_combos.get(variant_key)
        if combo is None or index < 0:
            return
        variant = combo.itemData(index)
        if not variant:
            return
        setattr(self._settings.typography, variant_key, str(variant))
        invalidate_playlist_render_cache()
        self.settings_changed.emit()

    def _on_font_changed(self, index: int) -> None:
        if self._font_combo is None or index < 0:
            return
        self._settings.typography.font_family = self._font_combo.itemText(index)
        invalidate_playlist_render_cache()
        self.settings_changed.emit()

    def _on_slider(self, key: str, value: int) -> None:
        val_lbl = self._value_labels.get(key)
        if val_lbl is not None:
            val_lbl.setText(str(value))
        if key in ("album_title_size", "now_playing_size", "song_title_size", "song_meta_size"):
            setattr(self._settings.typography, key, value)
        elif key == "cover_size_pct":
            self._settings.cover_size_pct = value
        elif key == "corner_radius":
            self._settings.corner_radius = value
        elif key == "list_row_gap":
            self._settings.list_row_gap = value
        self.settings_changed.emit()

    def _on_show_numbers(self, checked: bool) -> None:
        self._settings.show_track_numbers = checked
        self._settings.row_chrome.numbers.enabled = checked
        invalidate_playlist_render_cache()
        self.settings_changed.emit()

    def _on_show_durations(self, checked: bool) -> None:
        self._settings.show_durations = checked
        self._settings.row_chrome.duration.enabled = checked
        invalidate_playlist_render_cache()
        self.settings_changed.emit()
