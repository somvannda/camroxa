"""Axes-only Studio inspectors (docs Level 2/3 — no legacy Video chrome)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDial,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.studio.lib.scene_document import catalog_options
from features.studio.widgets.axis_combo import populate_combo, set_combo_data
from features.studio.widgets.expert_slider import ExpertFloatSlider
from features.video.lib.spectrum_color_engine import (
    MAX_GRADIENT_COLOR_STOPS,
    normalize_spectrum_gradient_colors,
)
from features.video.widgets.inspector_fields import build_color_field
from shared.icons.lucide_icons import lucide_pixmap
from shared.themes.deep_blue import SETTINGS_FORM_ROW_ID, SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel
from visualizer.logo_mask import CENTER_IMAGE_MASK_OPTIONS
from visualizer.presets.background_motion import background_motion_tuning_ui

_LAYER_ICON_COLOR = "#c4b5fd"
_LAYER_ICON_DANGER = "#fda4af"

_ROT_DIAL_SIZE = 56
_ROT_DIAL_QSS = f"""
QDial {{
    background-color: #0c1230;
    border: 1px solid #2a3566;
    border-radius: {_ROT_DIAL_SIZE // 2}px;
}}
QDial::handle {{
    background-color: #a855f7;
}}
"""


def _compact_dial(parent, *, tooltip: str, on_changed) -> QDial:
    dial = QDial(parent)
    dial.setRange(0, 360)
    dial.setWrapping(True)
    dial.setNotchesVisible(True)
    dial.setFixedSize(_ROT_DIAL_SIZE, _ROT_DIAL_SIZE)
    dial.setToolTip(tooltip)
    dial.setStyleSheet(_ROT_DIAL_QSS)
    dial.valueChanged.connect(on_changed)
    return dial


def _center_mask_for_spectrum_shape(shape: str | None) -> str:
    """Map spectrum shape → center-image mask so the image sits inside the path."""
    try:
        from visualizer.presets.shapes import normalize_spectrum_shape_id

        key = normalize_spectrum_shape_id(shape)
    except Exception:
        key = None
    if key in ("triangle", "diamond", "hexagon", "heart", "circle"):
        return str(key)
    if key in (
        "ring",
        "double_circle",
        "wave",
        "audio_ribbon",
        "starburst",
        "spiral",
        "tunnel",
        "infinity",
    ):
        return "circle"
    if key in ("bars", "soft_eq", "rect"):
        return "square"
    return "auto"


def _expert_slider(
    label: str,
    *,
    minimum: float,
    maximum: float,
    step: float,
    decimals: int = 2,
    value: float = 0.0,
) -> ExpertFloatSlider:
    """Compact Tuning slider for Studio inspectors."""
    return ExpertFloatSlider(
        label,
        minimum=minimum,
        maximum=maximum,
        step=step,
        decimals=decimals,
        value=value,
    )


def _lucide_tool_button(
    parent: QWidget,
    *,
    icon_name: str,
    tooltip: str,
    slot,
    color: str = _LAYER_ICON_COLOR,
) -> QPushButton:
    btn = QPushButton(parent)
    btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
    btn.setIcon(QIcon(lucide_pixmap(icon_name, size=18, color=color)))
    btn.setIconSize(QSize(18, 18))
    btn.setToolTip(tooltip)
    btn.setFixedSize(34, 34)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(slot)
    return btn


def form_row(label: str, widget: QWidget) -> QWidget:
    """Compact Studio form row — grows with control height (never clips)."""
    host = QWidget()
    host.setObjectName(SETTINGS_FORM_ROW_ID)
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 3, 0, 3)
    grid.setHorizontalSpacing(8)
    grid.setColumnStretch(1, 1)
    name = QLabel(label)
    name.setObjectName(SUBTITLE_LABEL_ID)
    name.setMinimumWidth(96)
    name.setMaximumWidth(110)
    name.setWordWrap(False)
    grid.addWidget(name, 0, 0, Qt.AlignmentFlag.AlignVCenter)
    grid.addWidget(widget, 0, 1)
    return host


def asset_row(label: str, line_edit: QLineEdit, *buttons: QPushButton) -> QWidget:
    """Full-width file row — label above controls so Select buttons aren't clipped."""
    host = QWidget()
    host.setObjectName(SETTINGS_FORM_ROW_ID)
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    root = QVBoxLayout(host)
    root.setContentsMargins(0, 4, 0, 6)
    root.setSpacing(4)
    name = QLabel(label)
    name.setObjectName(SUBTITLE_LABEL_ID)
    root.addWidget(name)
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    line_edit.setMinimumHeight(26)
    line_edit.setMaximumHeight(28)
    row.addWidget(line_edit, stretch=1)
    for btn in buttons:
        btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        btn.setMinimumHeight(26)
        btn.setMaximumHeight(28)
        row.addWidget(btn)
    root.addLayout(row)
    return host


def stacked_field(label: str, widget: QWidget) -> QWidget:
    """Label-above field — used for text inputs that need full rail width."""
    host = QWidget()
    host.setObjectName(SETTINGS_FORM_ROW_ID)
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    root = QVBoxLayout(host)
    root.setContentsMargins(0, 4, 0, 4)
    root.setSpacing(4)
    name = QLabel(label)
    name.setObjectName(SUBTITLE_LABEL_ID)
    root.addWidget(name)
    root.addWidget(widget)
    return host


def _compact_panel(panel: SettingsPanel) -> SettingsPanel:
    # Narrow L/R inset so controls use the wider rail; keep top/bottom for title clearance.
    if hasattr(panel, "_root"):
        panel._root.setContentsMargins(10, 12, 10, 12)
        panel._root.setSpacing(8)
    if hasattr(panel, "_body"):
        panel._body.setSpacing(8)
    return panel


class _AxisPanel(QWidget):
    patch_requested = Signal(dict)

    def __init__(self, title: str, *, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("studio_axis_panel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Widget stylesheet beats video_workspace button padding that was clipping rows.
        self.setStyleSheet(
            "QWidget#studio_axis_panel QComboBox,"
            "QWidget#studio_axis_panel QLineEdit {"
            "  min-height: 30px; max-height: 34px;"
            "  padding: 4px 8px; padding-right: 22px;"
            "  font-size: 12px;"
            "}"
            "QWidget#studio_axis_panel QComboBox::drop-down {"
            "  width: 18px; border: none;"
            "}"
            "QWidget#studio_axis_panel QPushButton#settings_secondary_button {"
            "  min-height: 26px; max-height: 28px;"
            "  padding: 2px 6px; min-width: 40px;"
            "  font-size: 11px;"
            "}"
            "QWidget#studio_axis_panel QCheckBox { min-height: 22px; spacing: 6px; }"
        )
        self._binding = False
        self._expert_count = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 8, 2, 8)
        root.setSpacing(8)
        # Short subtitle — avoid ellipsis truncation in the card header.
        short_sub = str(subtitle or "").strip()
        if len(short_sub) > 42:
            short_sub = short_sub[:39].rstrip() + "…"
        self._section = _compact_panel(
            SettingsPanel(title, subtitle=short_sub, fill_available_height=False)
        )
        root.addWidget(self._section, stretch=0)
        self._expert_panel = _compact_panel(SettingsPanel("Tuning", subtitle="", fill_available_height=False))
        self._tuning_host = QWidget()
        self._tuning_layout = QVBoxLayout(self._tuning_host)
        self._tuning_layout.setContentsMargins(0, 0, 0, 0)
        self._tuning_layout.setSpacing(4)
        self._expert_panel.add_widget(self._tuning_host)
        root.addWidget(self._expert_panel, stretch=0)
        self._expert_panel.setVisible(False)
        root.addStretch(1)

    def _emit(self, patch: dict) -> None:
        if not self._binding:
            self.patch_requested.emit(patch)

    def _add_expert(self, widget: QWidget) -> None:
        """Add a tuning control (slider label is built into ExpertFloatSlider)."""
        self._tuning_layout.addWidget(widget)
        self._expert_count += 1
        self._expert_panel.setVisible(True)

    def set_expert_mode(self, _enabled: bool = True) -> None:
        # Kept for call-site compatibility; Studio always shows tuning controls.
        self._expert_panel.setVisible(self._expert_count > 0)

    def bind(self, state: dict) -> None:
        raise NotImplementedError


class PaletteInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Color Palette",
            subtitle="Global tint (particles / lighting). Spectrum can override in its Material card.",
        )
        self._combo = QComboBox()
        populate_combo(self._combo, catalog_options()["palettes"], none_label="None (default)")
        self._combo.currentIndexChanged.connect(
            lambda: self._emit({"compositionColorPalette": self._combo.currentData() or "none"})
        )
        self._section.add_widget(form_row("Palette", self._combo))
        self._intensity = _expert_slider("Intensity", minimum=0.0, maximum=2.0, step=0.05, value=1.0)
        self._intensity.float_changed.connect(
            lambda v: self._emit({"compositionPaletteIntensity": float(v)})
        )
        self._saturation = _expert_slider("Saturation", minimum=0.0, maximum=2.0, step=0.05, value=1.0)
        self._saturation.float_changed.connect(
            lambda v: self._emit({"compositionPaletteSaturation": float(v)})
        )
        self._add_expert(self._intensity)
        self._add_expert(self._saturation)

    def bind(self, state: dict) -> None:
        self._binding = True
        set_combo_data(self._combo, str(state.get("compositionColorPalette") or "none"))
        inten = state.get("compositionPaletteIntensity")
        sat = state.get("compositionPaletteSaturation")
        self._intensity.set_float(1.0 if inten is None else float(inten))
        self._saturation.set_float(1.0 if sat is None else float(sat))
        self._binding = False


class BackgroundInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Background",
            subtitle="Image + Motion + Atmosphere (orthogonal).",
        )
        opts = catalog_options()
        self._enabled = QCheckBox("Background image enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"backgroundEnabled": checked}))
        self._section.add_widget(self._enabled)

        self._path = QLineEdit()
        self._path.setReadOnly(True)
        self._path.setPlaceholderText("No image selected")
        pick = QPushButton("Select")
        pick.clicked.connect(self._pick_image)
        self._section.add_widget(asset_row("Image", self._path, pick))

        self._motion = QComboBox()
        populate_combo(self._motion, opts["background_motions"], include_none=False)
        self._motion.currentIndexChanged.connect(self._on_motion_changed)
        self._section.add_widget(form_row("Motion", self._motion))

        self._atmosphere = QComboBox()
        populate_combo(self._atmosphere, opts["atmosphere"])
        self._atmosphere.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionBackgroundAtmosphere": self._atmosphere.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Atmosphere", self._atmosphere))

        self._video_path = QLineEdit()
        self._video_path.setReadOnly(True)
        self._video_path.setPlaceholderText("No video plate")
        pick_video = QPushButton("Select")
        pick_video.clicked.connect(self._pick_video)
        clear_video = QPushButton("Clear")
        clear_video.clicked.connect(lambda: self._emit({"backgroundVideo": ""}))
        self._section.add_widget(asset_row("Video plate", self._video_path, pick_video, clear_video))

        self._brightness = _expert_slider("Brightness", minimum=0.2, maximum=2.0, step=0.05, value=1.0)
        self._brightness.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundBrightness": float(v)})
        )
        self._contrast = _expert_slider("Contrast", minimum=0.2, maximum=2.0, step=0.05, value=1.0)
        self._contrast.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundContrast": float(v)})
        )
        self._reactivity = _expert_slider("Audio reactivity", minimum=0.0, maximum=1.0, step=0.05, value=0.0)
        self._reactivity.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundReactivity": float(v)})
        )
        self._saturation = _expert_slider("Saturation", minimum=0.0, maximum=2.0, step=0.05, value=1.0)
        self._saturation.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundSaturation": float(v)})
        )
        self._hue = _expert_slider("Hue", minimum=-180.0, maximum=180.0, step=5.0, decimals=0, value=0.0)
        self._hue.float_changed.connect(lambda v: self._emit({"compositionBackgroundHue": float(v)}))
        self._smoothing = _expert_slider("Smoothing", minimum=0.0, maximum=0.99, step=0.01, value=0.8)
        self._smoothing.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundSmoothing": float(v)})
        )
        # Motion knobs — visibility/labels follow the selected Motion catalog id.
        self._motion_speed = _expert_slider("Speed", minimum=0.15, maximum=3.0, step=0.05, value=1.0)
        self._motion_speed.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundMotionSpeed": float(v)})
        )
        self._motion_amp = _expert_slider("Amplitude", minimum=0.15, maximum=3.0, step=0.05, value=1.0)
        self._motion_amp.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundMotionAmplitude": float(v)})
        )
        self._motion_zoom = _expert_slider("Zoom", minimum=0.15, maximum=3.0, step=0.05, value=1.0)
        self._motion_zoom.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundMotionZoom": float(v)})
        )
        self._motion_warp = _expert_slider("Warp", minimum=0.0, maximum=3.0, step=0.05, value=1.0)
        self._motion_warp.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundMotionWarp": float(v)})
        )
        # Atmosphere-style expert knobs (apply to the selected Atmosphere catalog id).
        self._atm_density = _expert_slider(
            "Atmosphere density", minimum=0.0, maximum=2.5, step=0.05, value=1.0
        )
        self._atm_density.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundAtmosphereDensity": float(v)})
        )
        self._atm_speed = _expert_slider("Atmosphere speed", minimum=0.1, maximum=3.0, step=0.05, value=1.0)
        self._atm_speed.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundAtmosphereSpeed": float(v)})
        )
        self._atm_opacity = _expert_slider(
            "Atmosphere opacity", minimum=0.0, maximum=1.0, step=0.05, value=1.0
        )
        self._atm_opacity.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundAtmosphereOpacity": float(v)})
        )
        self._atm_wind = _expert_slider("Atmosphere wind", minimum=0.0, maximum=3.0, step=0.05, value=1.0)
        self._atm_wind.float_changed.connect(
            lambda v: self._emit({"compositionBackgroundAtmosphereWind": float(v)})
        )
        self._add_expert(self._brightness)
        self._add_expert(self._contrast)
        self._add_expert(self._reactivity)
        self._add_expert(self._saturation)
        self._add_expert(self._hue)
        self._add_expert(self._smoothing)
        self._add_expert(self._motion_speed)
        self._add_expert(self._motion_amp)
        self._add_expert(self._motion_zoom)
        self._add_expert(self._motion_warp)
        self._add_expert(self._atm_density)
        self._add_expert(self._atm_speed)
        self._add_expert(self._atm_opacity)
        self._add_expert(self._atm_wind)
        self._sync_motion_tuning_ui(self._motion.currentData() or "static")

    def _on_motion_changed(self, *_args) -> None:
        motion_id = self._motion.currentData() or "static"
        self._sync_motion_tuning_ui(str(motion_id))
        self._emit({"compositionBackgroundMotion": str(motion_id)})

    def _sync_motion_tuning_ui(self, motion_id: str) -> None:
        """Show only knobs that affect the active motion; relabel for context."""
        labels = background_motion_tuning_ui(motion_id)
        knobs = {
            "speed": self._motion_speed,
            "amplitude": self._motion_amp,
            "zoom": self._motion_zoom,
            "warp": self._motion_warp,
        }
        for key, slider in knobs.items():
            caption = labels.get(key)
            if caption:
                slider.set_label(caption)
                slider.setVisible(True)
            else:
                slider.setVisible(False)

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select background image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._emit({"backgroundImage": path, "backgroundEnabled": True, "backgroundVideo": ""})

    def _pick_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select background video",
            "",
            "Video (*.mp4 *.mov *.webm *.mkv *.avi *.m4v)",
        )
        if path:
            self._emit({"backgroundVideo": path, "backgroundEnabled": True})

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("backgroundEnabled")))
        self._path.setText(str(state.get("backgroundImage") or ""))
        self._video_path.setText(str(state.get("backgroundVideo") or ""))
        set_combo_data(
            self._motion, str(state.get("compositionBackgroundMotion") or "static"), fallback="static"
        )
        set_combo_data(self._atmosphere, str(state.get("compositionBackgroundAtmosphere") or "none"))
        self._brightness.set_float(float(state.get("compositionBackgroundBrightness") or 1.0))
        self._contrast.set_float(float(state.get("compositionBackgroundContrast") or 1.0))
        self._reactivity.set_float(float(state.get("compositionBackgroundReactivity") or 0.0))
        self._saturation.set_float(float(state.get("compositionBackgroundSaturation") or 1.0))
        self._hue.set_float(float(state.get("compositionBackgroundHue") or 0.0))
        self._smoothing.set_float(float(state.get("compositionBackgroundSmoothing") or 0.8))
        self._motion_speed.set_float(float(state.get("compositionBackgroundMotionSpeed") or 1.0))
        self._motion_amp.set_float(float(state.get("compositionBackgroundMotionAmplitude") or 1.0))
        self._motion_zoom.set_float(float(state.get("compositionBackgroundMotionZoom") or 1.0))
        self._motion_warp.set_float(float(state.get("compositionBackgroundMotionWarp") or 1.0))
        self._atm_density.set_float(float(state.get("compositionBackgroundAtmosphereDensity") or 1.0))
        self._atm_speed.set_float(float(state.get("compositionBackgroundAtmosphereSpeed") or 1.0))
        self._atm_opacity.set_float(float(state.get("compositionBackgroundAtmosphereOpacity") or 1.0))
        self._atm_wind.set_float(float(state.get("compositionBackgroundAtmosphereWind") or 1.0))
        self._sync_motion_tuning_ui(str(state.get("compositionBackgroundMotion") or "static"))
        self._binding = False


class SpectrumInspector(_AxisPanel):
    """Spectrum with separate Shape / Material / Animation cards + ring layers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Spectrum", subtitle="Drag in preview · layers · bars.")
        # Hide unused single Tuning card — knobs live on section cards.
        self._expert_panel.setVisible(False)
        opts = catalog_options()

        self._enabled = QCheckBox("Spectrum enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"spectrumEnabled": checked}))
        self._section.add_widget(self._enabled)

        self._size = _expert_slider("Shape size", minimum=0.35, maximum=2.5, step=0.05, value=1.0)
        self._size.setToolTip("Spectrum path size only — does not change the center image")
        self._size.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumSizeScale": float(v)})
        )
        self._section.add_widget(self._size)

        reset = QPushButton("Reset center")
        reset.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        reset.clicked.connect(
            lambda: self._emit(
                {"compositionSpectrumOffsetX": 0.0, "compositionSpectrumOffsetY": 0.0}
            )
        )
        self._section.add_widget(reset)

        # Center image (Vizzy-style) — sits in the hollow of the spectrum shape.
        self._center_card = _compact_panel(
            SettingsPanel("Center image", subtitle="", fill_available_height=False)
        )
        self._center_path = QLineEdit()
        self._center_path.setReadOnly(True)
        self._center_path.setPlaceholderText("No image selected")
        pick_center = QPushButton("Select")
        pick_center.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        pick_center.clicked.connect(self._pick_center_image)
        clear_center = QPushButton("Clear")
        clear_center.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        clear_center.clicked.connect(self._clear_center_image)
        self._center_card.add_widget(asset_row("File", self._center_path, pick_center, clear_center))
        self._center_enabled = QCheckBox("Show center image")
        self._center_enabled.toggled.connect(
            lambda checked: self._emit({"logoEnabled": bool(checked)})
        )
        self._center_card.add_widget(self._center_enabled)
        self._center_contain = QCheckBox("Stay inside shape")
        self._center_contain.setToolTip(
            "On: image locks to the spectrum — drag either and they move together; "
            "Image size can grow to the yellow path edge. "
            "Shape rotation spins path + mask only; use Image rotation for the picture."
        )
        self._center_contain.setChecked(False)
        self._center_contain.toggled.connect(self._on_center_contain_toggled)
        self._center_card.add_widget(self._center_contain)
        self._center_mask = QComboBox()
        populate_combo(self._center_mask, CENTER_IMAGE_MASK_OPTIONS, include_none=False)
        self._center_mask.setToolTip(
            "Clip the square image to this silhouette. "
            "Match spectrum follows the Spectrum shape; Square shows the full image."
        )
        self._center_mask.currentIndexChanged.connect(self._on_center_mask_changed)
        self._center_card.add_widget(stacked_field("Mask", self._center_mask))
        self._center_size = _expert_slider(
            "Image size px", minimum=64.0, maximum=512.0, step=8.0, decimals=0, value=192.0
        )
        self._center_size.setToolTip("Center image size only — does not change the spectrum shape")
        self._center_size.float_changed.connect(
            lambda v: self._emit({"compositionLogoSize": float(v)})
        )
        self._center_opacity = _expert_slider(
            "Opacity", minimum=0.1, maximum=1.0, step=0.05, value=1.0
        )
        self._center_opacity.float_changed.connect(
            lambda v: self._emit({"compositionLogoOpacity": float(v)})
        )
        self._center_react = _expert_slider(
            "Reactivity", minimum=0.0, maximum=1.0, step=0.05, value=0.0
        )
        self._center_react.float_changed.connect(
            lambda v: self._emit({"compositionLogoReactivity": float(v)})
        )
        self._center_card.add_widget(self._center_size)
        self._center_card.add_widget(self._center_opacity)
        self._center_card.add_widget(self._center_react)
        self._image_rot_label = QLabel("Image rotation (0°)")
        self._image_rot_label.setObjectName(SUBTITLE_LABEL_ID)
        self._center_card.add_widget(self._image_rot_label)
        self._image_rot_dial = _compact_dial(
            self,
            tooltip="Rotate the picture only (0–360°). Does not spin the spectrum path.",
            on_changed=self._on_image_rotation_dial,
        )
        self._center_card.add_widget(self._image_rot_dial)
        self.layout().insertWidget(1, self._center_card)

        # Layer stack — each selected layer has its own settings below.
        self._layer_combo = QComboBox()
        self._layer_combo.currentIndexChanged.connect(self._on_layer_selected)
        self._section.add_widget(stacked_field("Layer", self._layer_combo))
        self._layer_name = QLineEdit()
        self._layer_name.setPlaceholderText("Layer name")
        self._layer_name.setMaxLength(48)
        self._layer_name.editingFinished.connect(self._on_layer_name_finished)
        self._section.add_widget(stacked_field("Name", self._layer_name))
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)
        for icon_name, tip, slot, color in (
            ("plus", "Add layer", lambda: self._emit({"compositionSpectrumLayerAdd": True}), _LAYER_ICON_COLOR),
            ("copy", "Duplicate layer", lambda: self._emit({"compositionSpectrumLayerDuplicate": True}), _LAYER_ICON_COLOR),
            ("trash-2", "Delete layer", lambda: self._emit({"compositionSpectrumLayerDelete": True}), _LAYER_ICON_DANGER),
            ("arrow-up", "Move layer up", lambda: self._emit({"compositionSpectrumLayerMove": "up"}), _LAYER_ICON_COLOR),
            ("arrow-down", "Move layer down", lambda: self._emit({"compositionSpectrumLayerMove": "down"}), _LAYER_ICON_COLOR),
        ):
            actions.addWidget(
                _lucide_tool_button(self, icon_name=icon_name, tooltip=tip, slot=slot, color=color)
            )
        actions.addStretch(1)
        action_host = QWidget()
        action_host.setLayout(actions)
        self._section.add_widget(action_host)

        self._layer_enabled = QCheckBox("Layer enabled")
        self._layer_enabled.toggled.connect(
            lambda checked: self._layer_patch(enabled=bool(checked))
        )
        self._layer_gap = _expert_slider("Gap", minimum=-80.0, maximum=220.0, step=1.0, decimals=0, value=0.0)
        self._layer_gap.float_changed.connect(lambda v: self._layer_patch(radiusOffset=float(v)))
        self._layer_opacity = _expert_slider("Opacity", minimum=0.05, maximum=1.0, step=0.05, value=1.0)
        self._layer_opacity.float_changed.connect(lambda v: self._layer_patch(opacity=float(v)))
        self._layer_audio_bus = QComboBox()
        populate_combo(self._layer_audio_bus, opts["audio_buses"], none_label="Overall (shared)")
        self._layer_audio_bus.setToolTip(
            "Which frequency band drives this layer. Bass moves low bars; Treble moves high bars. "
            "Overall follows Audio Mapping → Spectrum reaction when set."
        )
        self._layer_audio_bus.currentIndexChanged.connect(self._on_layer_audio_bus)
        self._layer_audio_gain = _expert_slider(
            "Audio gain", minimum=0.0, maximum=3.0, step=0.05, value=1.0
        )
        self._layer_audio_gain.setToolTip("Per-layer audio reactivity for the selected bus")
        self._layer_audio_gain.float_changed.connect(lambda v: self._layer_patch(audioGain=float(v)))
        self._bar_height = _expert_slider("Bar height", minimum=0.25, maximum=4.0, step=0.05, value=1.0)
        self._bar_height.float_changed.connect(lambda v: self._layer_patch(barHeight=float(v)))
        self._bar_width = _expert_slider("Bar width", minimum=0.08, maximum=3.0, step=0.02, value=1.0)
        self._bar_width.setToolTip("How thin/thick each bar is (this layer only)")
        self._bar_width.float_changed.connect(lambda v: self._layer_patch(barWidthScale=float(v)))
        self._thickness = _expert_slider("Thickness", minimum=0.25, maximum=3.0, step=0.05, value=1.0)
        self._thickness.float_changed.connect(lambda v: self._layer_patch(thicknessScale=float(v)))
        self._bar_count = _expert_slider(
            "Bar count", minimum=24.0, maximum=160.0, step=1.0, decimals=0, value=64.0
        )
        self._bar_count.float_changed.connect(
            lambda v: self._layer_patch(barCount=int(round(float(v))))
        )
        self._tip_taper = _expert_slider("Tip taper", minimum=0.0, maximum=1.0, step=0.05, value=0.0)
        self._tip_taper.setToolTip("0 = equal width · 1 = pointed tips (this layer)")
        self._tip_taper.float_changed.connect(lambda v: self._layer_patch(tipTaper=float(v)))
        self._mirror = QComboBox()
        self._mirror.addItem("Shape default", "auto")
        self._mirror.addItem("Full ring", "full")
        self._mirror.addItem("Half / raise", "half")
        self._mirror.currentIndexChanged.connect(self._on_mirror_changed)
        self._mirror_row = stacked_field("Mirror", self._mirror)
        self._raise = QComboBox()
        self._raise.addItem("Shape default", "auto")
        self._raise.addItem("Top", "top")
        self._raise.addItem("Bottom", "bottom")
        self._raise.addItem("Left", "left")
        self._raise.addItem("Right", "right")
        self._raise.addItem("Outside shape", "outward")
        self._raise.addItem("Inside shape", "inward")
        self._raise.setToolTip("Where this layer's bars grow (presets). Cleared when Raise angle dial is used.")
        self._raise.currentIndexChanged.connect(self._on_raise_changed)
        self._raise_row = stacked_field("Raise", self._raise)
        self._raise_angle_label = QLabel("Raise angle (follow)")
        self._raise_angle_label.setObjectName(SUBTITLE_LABEL_ID)
        self._raise_angle_dial = _compact_dial(
            self,
            tooltip=(
                "Point bar growth any direction (0°=right, 90°=up). "
                "Overrides Raise presets. Change Raise to follow presets again. "
                "Preview: Shift+drag a bar to aim."
            ),
            on_changed=self._on_raise_angle_dial,
        )
        self._path_phase = _expert_slider(
            "Path phase", minimum=0.0, maximum=1.0, step=0.01, value=0.0
        )
        self._path_phase.setToolTip(
            "Slide peaks along the path (0–1). Preview: Alt+drag around the shape."
        )
        self._path_phase.float_changed.connect(
            lambda v: self._layer_patch(frequencyScroll=float(v))
        )
        self._peak_caps = QCheckBox("Peak caps")
        self._peak_caps.toggled.connect(lambda checked: self._layer_patch(peakCapsEnabled=bool(checked)))
        self._solid_band = QCheckBox("Solid graph")
        self._solid_band.setToolTip("Filled solid graph instead of discrete bars (this layer)")
        self._solid_band.toggled.connect(lambda checked: self._layer_patch(solidBand=bool(checked)))
        self._glow = _expert_slider("Glow", minimum=0.0, maximum=1.0, step=0.05, value=0.45)
        self._glow.float_changed.connect(lambda v: self._layer_patch(glow=float(v)))
        self._blur = _expert_slider("Blur", minimum=0.0, maximum=8.0, step=0.1, value=0.0)
        self._blur.float_changed.connect(lambda v: self._layer_patch(blur=float(v)))

        self._layer_controls = (
            self._layer_enabled,
            self._layer_gap,
            self._layer_opacity,
            self._layer_audio_gain,
            self._bar_height,
            self._bar_width,
            self._thickness,
            self._bar_count,
            self._tip_taper,
            self._mirror_row,
            self._raise_row,
            self._raise_angle_label,
            self._raise_angle_dial,
            self._path_phase,
            self._peak_caps,
            self._solid_band,
            self._glow,
            self._blur,
        )
        self._layer_audio_bus_row = stacked_field("Audio bus", self._layer_audio_bus)
        self._section.add_widget(self._layer_enabled)
        self._section.add_widget(self._layer_gap)
        self._section.add_widget(self._layer_opacity)
        self._section.add_widget(self._layer_audio_bus_row)
        self._section.add_widget(self._layer_audio_gain)
        self._section.add_widget(self._bar_height)
        self._section.add_widget(self._bar_width)
        self._section.add_widget(self._thickness)
        self._section.add_widget(self._bar_count)
        self._section.add_widget(self._tip_taper)
        self._section.add_widget(self._mirror_row)
        self._section.add_widget(self._raise_row)
        self._section.add_widget(self._raise_angle_label)
        self._section.add_widget(self._raise_angle_dial)
        self._section.add_widget(self._path_phase)
        self._section.add_widget(self._peak_caps)
        self._section.add_widget(self._solid_band)
        self._section.add_widget(self._glow)
        self._section.add_widget(self._blur)

        # Shape card — shared shape only
        self._shape_card = _compact_panel(SettingsPanel("Shape", subtitle="", fill_available_height=False))
        self._shape = QComboBox()
        populate_combo(self._shape, opts["shapes"])
        self._shape.currentIndexChanged.connect(self._on_shape_changed)
        self._shape_card.add_widget(stacked_field("Shape", self._shape))
        self._shape_rot_label = QLabel("Shape rotation (0°)")
        self._shape_rot_label.setObjectName(SUBTITLE_LABEL_ID)
        self._shape_card.add_widget(self._shape_rot_label)
        self._shape_rot_dial = _compact_dial(
            self,
            tooltip="Rotate the spectrum path and crop mask (0–360°). Picture stays put.",
            on_changed=self._on_shape_rotation_dial,
        )
        self._shape_card.add_widget(self._shape_rot_dial)
        self.layout().insertWidget(2, self._shape_card)

        # Material card — shared material + palette
        self._material_card = _compact_panel(
            SettingsPanel("Material", subtitle="", fill_available_height=False)
        )
        self._material = QComboBox()
        populate_combo(self._material, opts["materials"])
        self._material.currentIndexChanged.connect(self._on_material_changed)
        self._material_card.add_widget(stacked_field("Material", self._material))
        self._palette = QComboBox()
        populate_combo(self._palette, opts["palettes"], none_label="Inherit global")
        self._palette.currentIndexChanged.connect(self._on_spectrum_palette_changed)
        self._palette_row = stacked_field("Palette", self._palette)
        self._material_card.add_widget(self._palette_row)
        self._stops_host = QWidget()
        self._stops_layout = QVBoxLayout(self._stops_host)
        self._stops_layout.setContentsMargins(0, 0, 0, 0)
        self._stops_layout.setSpacing(6)
        self._stop_setters: list = []
        self._gradient_colors: list[str] = ["#ff4fd8", "#22d3ee"]
        stop_actions = QHBoxLayout()
        stop_actions.setContentsMargins(0, 0, 0, 0)
        stop_actions.setSpacing(6)
        add_stop = QPushButton("Add color")
        add_stop.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        add_stop.clicked.connect(self._add_gradient_stop)
        remove_stop = QPushButton("Remove")
        remove_stop.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        remove_stop.clicked.connect(self._remove_gradient_stop)
        reset_stops = QPushButton("Use palette")
        reset_stops.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        reset_stops.setToolTip("Clear custom stops and follow the selected palette")
        reset_stops.clicked.connect(self._clear_custom_stops)
        stop_actions.addWidget(add_stop)
        stop_actions.addWidget(remove_stop)
        stop_actions.addWidget(reset_stops)
        stop_actions.addStretch(1)
        stop_actions_host = QWidget()
        stop_actions_host.setLayout(stop_actions)
        self._material_card.add_widget(stop_actions_host)
        self._material_card.add_widget(self._stops_host)
        self._rebuild_gradient_stops(self._gradient_colors)
        self._material_note = QLabel("Edit stops to customize this spectrum palette.")
        self._material_note.setObjectName(SUBTITLE_LABEL_ID)
        self._material_note.setWordWrap(True)
        self._material_card.add_widget(self._material_note)
        self.layout().insertWidget(3, self._material_card)

        # Animation card — full motion dials
        self._animation_card = _compact_panel(
            SettingsPanel("Animation", subtitle="", fill_available_height=False)
        )
        self._animation = QComboBox()
        populate_combo(self._animation, opts["animations"])
        self._animation.currentIndexChanged.connect(self._on_animation_changed)
        self._animation_card.add_widget(stacked_field("Animation", self._animation))
        self._anim_speed = _expert_slider("Motion speed", minimum=0.15, maximum=3.0, step=0.05, value=1.0)
        self._anim_speed.setToolTip("How fast the motion cycles")
        self._anim_speed.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationSpeed": float(v)})
        )
        self._anim_scale = _expert_slider("Scale amount", minimum=0.0, maximum=2.5, step=0.05, value=1.0)
        self._anim_scale.setToolTip("How strongly size pulses / expands")
        self._anim_scale.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationScale": float(v)})
        )
        self._anim_opacity = _expert_slider("Opacity pulse", minimum=0.0, maximum=2.5, step=0.05, value=1.0)
        self._anim_opacity.setToolTip("How strongly opacity breathes / flashes")
        self._anim_opacity.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationOpacity": float(v)})
        )
        self._anim_rotate = _expert_slider("Rotate amount", minimum=0.0, maximum=2.5, step=0.05, value=1.0)
        self._anim_rotate.setToolTip("Rotation / twist strength")
        self._anim_rotate.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationRotate": float(v)})
        )
        self._anim_audio = _expert_slider("Audio drive", minimum=0.0, maximum=2.5, step=0.05, value=1.0)
        self._anim_audio.setToolTip("How much the beat feeds the animation")
        self._anim_audio.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationAudio": float(v)})
        )
        self._anim_kick = _expert_slider("Kick impact", minimum=0.0, maximum=2.5, step=0.05, value=1.0)
        self._anim_kick.setToolTip("Extra punch on spectrum bars from kicks")
        self._anim_kick.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationKick": float(v)})
        )
        self._anim_smooth = _expert_slider("Smoothing", minimum=0.1, maximum=1.0, step=0.05, value=0.65)
        self._anim_smooth.setToolTip("Motion smoothing (higher = smoother / slower response)")
        self._anim_smooth.float_changed.connect(
            lambda v: self._emit({"compositionSpectrumAnimationSmoothing": float(v)})
        )
        self._anim_controls = (
            self._anim_speed,
            self._anim_scale,
            self._anim_opacity,
            self._anim_rotate,
            self._anim_audio,
            self._anim_kick,
            self._anim_smooth,
        )
        for w in self._anim_controls:
            self._animation_card.add_widget(w)
        self._anim_note = QLabel("Tune each motion channel for the selected animation.")
        self._anim_note.setObjectName(SUBTITLE_LABEL_ID)
        self._anim_note.setWordWrap(True)
        self._animation_card.add_widget(self._anim_note)
        self.layout().insertWidget(4, self._animation_card)

        self._layers_cache: list[dict] = []
        self._sync_axis_visibility()

    def _on_shape_rotation_dial(self, value: int) -> None:
        if self._binding:
            return
        deg = int(value) % 360
        self._shape_rot_label.setText(f"Shape rotation ({deg}°)")
        # Path + mask only — picture orientation stays on Image rotation.
        self._emit({"compositionSpectrumRotationDeg": float(deg)})

    def _on_image_rotation_dial(self, value: int) -> None:
        if self._binding:
            return
        deg = int(value) % 360
        self._image_rot_label.setText(f"Image rotation ({deg}°)")
        self._emit({"compositionLogoRotationDeg": float(deg)})

    def _on_shape_changed(self, *_args) -> None:
        if self._binding:
            return
        shape = str(self._shape.currentData() or "none")
        mask = _center_mask_for_spectrum_shape(shape)
        self._emit(
            {
                "compositionSpectrumShape": shape,
                "compositionLogoMaskShape": mask,
                "compositionLogoFitToShape": True,
            }
        )
        if hasattr(self, "_center_mask"):
            self._binding = True
            set_combo_data(self._center_mask, mask, fallback="auto")
            self._binding = False
        self._sync_axis_visibility()

    def _on_center_mask_changed(self, *_args) -> None:
        if self._binding:
            return
        self._emit({"compositionLogoMaskShape": self._center_mask.currentData() or "auto"})

    def _on_center_contain_toggled(self, checked: bool) -> None:
        if self._binding:
            return
        patch: dict = {"compositionLogoContainInShape": bool(checked)}
        if checked:
            # Lock center image to spectrum path (shared drag + size clamp).
            # Shape rotation still spins path/mask only — Image rotation stays independent.
            patch["spectrumAttachToLogo"] = True
            patch["compositionLogoOffsetX"] = 0.0
            patch["compositionLogoOffsetY"] = 0.0
            patch["compositionLogoFitToShape"] = True
            patch["compositionLogoMaskShape"] = "auto"
            self._binding = True
            set_combo_data(self._center_mask, "auto", fallback="auto")
            self._binding = False
        self._emit(patch)
        self._sync_rotation_tips()

    def _sync_rotation_tips(self) -> None:
        self._image_rot_dial.setToolTip(
            "Rotate the picture only (0–360°). Does not spin the spectrum path."
        )
        self._shape_rot_dial.setToolTip(
            "Rotate the spectrum path and crop mask (0–360°). Picture stays put."
        )

    def _pick_center_image(self) -> None:
        if self._binding:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select center image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.svg)",
        )
        if path:
            from pathlib import Path as _Path

            resolved = str(_Path(path).expanduser().resolve())
            self._emit(
                {
                    "logoPath": resolved,
                    "logoEnabled": True,
                    "spectrumAttachToLogo": True,
                    "compositionLogoFitToShape": True,
                    "compositionLogoMaskShape": "auto",
                    "compositionLogoSize": 280.0,
                }
            )

    def _clear_center_image(self) -> None:
        if self._binding:
            return
        self._emit(
            {
                "logoPath": "",
                "logoEnabled": False,
                "spectrumAttachToLogo": False,
            }
        )

    def _on_material_changed(self, *_args) -> None:
        self._emit({"compositionSpectrumMaterial": self._material.currentData() or "none"})
        self._sync_axis_visibility()

    def _on_animation_changed(self, *_args) -> None:
        self._emit({"compositionSpectrumAnimation": self._animation.currentData() or "none"})
        self._sync_axis_visibility()

    def _on_spectrum_palette_changed(self, *_args) -> None:
        if self._binding:
            return
        pal_id = self._palette.currentData() or "none"
        self._emit({"compositionSpectrumColorPalette": pal_id})
        # Seed editable stops from the chosen catalog so users can tweak them.
        try:
            from visualizer.presets.palettes import get_palette

            pal = get_palette(None if pal_id in ("", "none") else str(pal_id))
            stops = list((pal or {}).get("stops") or [])
            if len(stops) >= 2:
                self._emit_gradient_colors([str(c) for c in stops])
                self._rebuild_gradient_stops(self._gradient_colors)
        except Exception:
            pass

    def _emit_gradient_colors(self, colors: list[str]) -> None:
        normalized = normalize_spectrum_gradient_colors(colors, "#ff4fd8")
        self._gradient_colors = list(normalized)
        self._emit({"compositionSpectrumGradientColors": list(normalized)})

    def _rebuild_gradient_stops(self, colors: list[str]) -> None:
        while self._stops_layout.count():
            item = self._stops_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._stop_setters.clear()
        usable = list(colors) if colors else ["#ff4fd8", "#22d3ee"]
        for index, color in enumerate(usable):
            row, setter = build_color_field(
                f"Stop {index + 1}",
                value=str(color),
                on_change=lambda value, stop_index=index: self._patch_gradient_stop(stop_index, value),
                parent=self,
            )
            self._stop_setters.append(setter)
            self._stops_layout.addWidget(row)

    def _patch_gradient_stop(self, stop_index: int, value: str) -> None:
        if self._binding:
            return
        colors = list(self._gradient_colors)
        if stop_index >= len(colors):
            return
        colors[stop_index] = value
        self._emit_gradient_colors(colors)
        self._rebuild_gradient_stops(self._gradient_colors)

    def _add_gradient_stop(self) -> None:
        if self._binding:
            return
        colors = list(self._gradient_colors)
        if len(colors) >= MAX_GRADIENT_COLOR_STOPS:
            return
        colors.append(colors[-1] if colors else "#22d3ee")
        self._emit_gradient_colors(colors)
        self._rebuild_gradient_stops(self._gradient_colors)

    def _remove_gradient_stop(self) -> None:
        if self._binding:
            return
        colors = list(self._gradient_colors)
        if len(colors) <= 2:
            return
        colors = colors[:-1]
        self._emit_gradient_colors(colors)
        self._rebuild_gradient_stops(self._gradient_colors)

    def _clear_custom_stops(self) -> None:
        if self._binding:
            return
        self._emit({"compositionSpectrumGradientColors": None})
        self._gradient_colors = ["#ff4fd8", "#22d3ee"]
        self._rebuild_gradient_stops(self._gradient_colors)

    def _layer_patch(self, **fields) -> None:
        if self._binding or not fields:
            return
        self._emit({"compositionSpectrumLayerPatch": dict(fields)})

    def _on_layer_name_finished(self) -> None:
        if self._binding:
            return
        name = str(self._layer_name.text() or "").strip()
        if not name:
            return
        self._layer_patch(name=name)

    def _on_mirror_changed(self, *_args) -> None:
        data = str(self._mirror.currentData() or "auto")
        if data == "full":
            self._layer_patch(mirrored=True)
        elif data == "half":
            self._layer_patch(mirrored=False)
        else:
            self._layer_patch(mirrored=None)

    def _on_raise_changed(self, *_args) -> None:
        data = str(self._raise.currentData() or "auto")
        # Changing Raise preset clears free angle so dropdown drives growth again.
        self._layer_patch(
            gravity=None if data == "auto" else data,
            raiseAngleDeg=None,
        )
        if not self._binding:
            self._raise_angle_dial.blockSignals(True)
            self._raise_angle_dial.setValue(90)
            self._raise_angle_dial.blockSignals(False)
            self._raise_angle_label.setText("Raise angle (follow)")

    def _on_raise_angle_dial(self, value: int) -> None:
        if self._binding:
            return
        deg = int(value) % 360
        self._raise_angle_label.setText(f"Raise angle ({deg}°)")
        self._layer_patch(raiseAngleDeg=float(deg))

    def _on_layer_audio_bus(self, *_args) -> None:
        self._layer_patch(audioBus=self._layer_audio_bus.currentData() or "none")

    def _sync_axis_visibility(self) -> None:
        shape = str(self._shape.currentData() or "none")
        animation = str(self._animation.currentData() or "none")
        shape_on = shape not in ("", "none")
        for w in self._layer_controls:
            w.setVisible(shape_on)
        self._layer_name.setVisible(shape_on)
        self._layer_audio_bus_row.setVisible(shape_on)
        self._palette_row.setVisible(shape_on)
        self._material_note.setVisible(shape_on)
        self._center_card.setVisible(shape_on)
        anim_on = animation not in ("", "none")
        self._anim_note.setVisible(anim_on)
        for w in self._anim_controls:
            w.setVisible(anim_on)

    def _on_layer_selected(self, index: int) -> None:
        if self._binding:
            return
        self._emit({"compositionSpectrumLayerIndex": int(index)})
        self._bind_selected_layer()

    def _bind_selected_layer(self) -> None:
        if not self._layers_cache:
            return
        idx = max(0, min(self._layer_combo.currentIndex(), len(self._layers_cache) - 1))
        layer = self._layers_cache[idx] if isinstance(self._layers_cache[idx], dict) else {}
        blocked = self._binding
        self._binding = True
        self._layer_name.setText(str(layer.get("name") or f"Ring {idx + 1}"))
        self._layer_gap.set_float(float(layer.get("radiusOffset") or 0.0))
        self._layer_opacity.set_float(float(layer.get("opacity") or 1.0))
        self._layer_enabled.setChecked(bool(layer.get("enabled", True)))
        set_combo_data(self._layer_audio_bus, str(layer.get("audioBus") or "none"))
        try:
            self._layer_audio_gain.set_float(
                float(layer.get("audioGain") if layer.get("audioGain") is not None else 1.0)
            )
        except (TypeError, ValueError):
            self._layer_audio_gain.set_float(1.0)
        self._bar_height.set_float(float(layer.get("barHeight") or 1.0))
        self._bar_width.set_float(float(layer.get("barWidthScale") or 1.0))
        self._thickness.set_float(float(layer.get("thicknessScale") or 1.0))
        self._bar_count.set_float(float(layer.get("barCount") or 64))
        self._tip_taper.set_float(float(0.0 if layer.get("tipTaper") is None else layer.get("tipTaper")))
        mirror = layer.get("mirrored")
        if mirror in (None, "auto", "none", ""):
            set_combo_data(self._mirror, "auto", fallback="auto")
        elif mirror is True or str(mirror).lower() in ("true", "1", "full"):
            set_combo_data(self._mirror, "full", fallback="auto")
        else:
            set_combo_data(self._mirror, "half", fallback="auto")
        raise_mode = layer.get("gravity")
        set_combo_data(
            self._raise,
            "auto" if raise_mode in (None, "", "auto") else str(raise_mode),
            fallback="auto",
        )
        raw_raise_angle = layer.get("raiseAngleDeg")
        if raw_raise_angle in (None, "", "auto", "none"):
            self._raise_angle_dial.blockSignals(True)
            self._raise_angle_dial.setValue(90)
            self._raise_angle_dial.blockSignals(False)
            self._raise_angle_label.setText("Raise angle (follow)")
        else:
            try:
                raise_deg = int(round(float(raw_raise_angle))) % 360
            except (TypeError, ValueError):
                raise_deg = 90
            self._raise_angle_dial.blockSignals(True)
            self._raise_angle_dial.setValue(raise_deg)
            self._raise_angle_dial.blockSignals(False)
            self._raise_angle_label.setText(f"Raise angle ({raise_deg}°)")
        try:
            from visualizer._spectrum_fast import clamp_frequency_scroll

            self._path_phase.set_float(float(clamp_frequency_scroll(layer.get("frequencyScroll"), 0.0)))
        except Exception:
            self._path_phase.set_float(0.0)
        self._peak_caps.setChecked(bool(layer.get("peakCapsEnabled", False)))
        self._solid_band.setChecked(bool(layer.get("solidBand", False)))
        glow_raw = layer.get("glow")
        self._glow.set_float(0.45 if glow_raw is None else float(glow_raw))
        blur_raw = layer.get("blur")
        self._blur.set_float(0.0 if blur_raw is None else float(blur_raw))
        self._binding = blocked

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("spectrumEnabled")))
        self._size.set_float(float(state.get("compositionSpectrumSizeScale") or 1.0))
        self._center_path.setText(str(state.get("logoPath") or ""))
        self._center_enabled.setChecked(bool(state.get("logoEnabled", True)) and bool(state.get("logoPath")))
        self._center_contain.setChecked(bool(state.get("compositionLogoContainInShape", False)))
        set_combo_data(self._center_mask, str(state.get("compositionLogoMaskShape") or "auto"), fallback="auto")
        self._center_size.set_float(float(state.get("compositionLogoSize") or 192.0))
        self._center_opacity.set_float(float(state.get("compositionLogoOpacity") or 1.0))
        self._center_react.set_float(float(state.get("compositionLogoReactivity") or 0.0))
        set_combo_data(self._shape, str(state.get("compositionSpectrumShape") or "none"))
        try:
            rot = int(round(float(state.get("compositionSpectrumRotationDeg") or 0.0))) % 360
        except (TypeError, ValueError):
            rot = 0
        self._shape_rot_dial.blockSignals(True)
        self._shape_rot_dial.setValue(rot)
        self._shape_rot_dial.blockSignals(False)
        self._shape_rot_label.setText(f"Shape rotation ({rot}°)")
        try:
            img_rot = int(round(float(state.get("compositionLogoRotationDeg") or 0.0))) % 360
        except (TypeError, ValueError):
            img_rot = 0
        self._image_rot_dial.blockSignals(True)
        self._image_rot_dial.setValue(img_rot)
        self._image_rot_dial.blockSignals(False)
        self._image_rot_label.setText(f"Image rotation ({img_rot}°)")
        set_combo_data(self._material, str(state.get("compositionSpectrumMaterial") or "none"))
        set_combo_data(self._animation, str(state.get("compositionSpectrumAnimation") or "none"))
        speed_raw = state.get("compositionSpectrumAnimationSpeed")
        self._anim_speed.set_float(1.0 if speed_raw is None else float(speed_raw))
        self._anim_scale.set_float(float(state.get("compositionSpectrumAnimationScale") or 1.0))
        self._anim_opacity.set_float(float(state.get("compositionSpectrumAnimationOpacity") or 1.0))
        self._anim_rotate.set_float(float(state.get("compositionSpectrumAnimationRotate") or 1.0))
        self._anim_audio.set_float(float(state.get("compositionSpectrumAnimationAudio") or 1.0))
        self._anim_kick.set_float(float(state.get("compositionSpectrumAnimationKick") or 1.0))
        smooth_raw = state.get("compositionSpectrumAnimationSmoothing")
        self._anim_smooth.set_float(0.65 if smooth_raw is None else float(smooth_raw))
        set_combo_data(self._palette, str(state.get("compositionSpectrumColorPalette") or "none"))
        raw_stops = state.get("compositionSpectrumGradientColors")
        if isinstance(raw_stops, list) and len(raw_stops) >= 2:
            self._gradient_colors = normalize_spectrum_gradient_colors(
                [str(c) for c in raw_stops], "#ff4fd8"
            )
        else:
            self._gradient_colors = ["#ff4fd8", "#22d3ee"]
        self._rebuild_gradient_stops(self._gradient_colors)
        layers = state.get("compositionSpectrumLayers") if isinstance(state.get("compositionSpectrumLayers"), list) else []
        self._layers_cache = [dict(x) for x in layers if isinstance(x, dict)]
        self._layer_combo.clear()
        for i, layer in enumerate(self._layers_cache):
            self._layer_combo.addItem(str(layer.get("name") or f"Ring {i + 1}"), i)
        idx = int(state.get("compositionSpectrumLayerIndex") or 0)
        if self._layer_combo.count():
            self._layer_combo.setCurrentIndex(max(0, min(idx, self._layer_combo.count() - 1)))
        self._bind_selected_layer()
        self._sync_axis_visibility()
        self._sync_rotation_tips()
        self._binding = False

    def set_expert_mode(self, _enabled: bool = True) -> None:
        self._expert_panel.setVisible(False)


class LogoInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Logo", subtitle="Asset + shared animation behavior.")
        self._enabled = QCheckBox("Logo enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"logoEnabled": checked}))
        self._section.add_widget(self._enabled)

        self._path = QLineEdit()
        self._path.setReadOnly(True)
        self._path.setPlaceholderText("No logo selected")
        pick = QPushButton("Select")
        pick.clicked.connect(self._pick_logo)
        self._section.add_widget(asset_row("File", self._path, pick))

        self._animation = QComboBox()
        populate_combo(self._animation, catalog_options()["animations"])
        self._animation.currentIndexChanged.connect(
            lambda: self._emit({"compositionLogoAnimation": self._animation.currentData() or "none"})
        )
        self._section.add_widget(form_row("Animation", self._animation))

        self._attach = QCheckBox("Logo inside shape")
        self._attach.setToolTip(
            "Place the logo in the hollow center of spectrum shapes. "
            "Set Spectrum → Raise yourself (e.g. Outside shape) if you want bars to grow away from the logo."
        )
        self._attach.toggled.connect(lambda checked: self._emit({"spectrumAttachToLogo": bool(checked)}))
        self._section.add_widget(self._attach)

        self._circle = QCheckBox("Circle mask")
        self._circle.toggled.connect(lambda checked: self._emit({"compositionLogoCircleMask": checked}))
        self._section.add_widget(self._circle)

        self._logo_scale = _expert_slider("Scale", minimum=0.25, maximum=3.0, step=0.05, value=1.0)
        self._logo_scale.float_changed.connect(lambda v: self._emit({"compositionLogoScale": float(v)}))
        self._logo_opacity = _expert_slider("Opacity", minimum=0.1, maximum=1.0, step=0.05, value=1.0)
        self._logo_opacity.float_changed.connect(
            lambda v: self._emit({"compositionLogoOpacity": float(v)})
        )
        self._logo_size = _expert_slider("Size px", minimum=64.0, maximum=512.0, step=8.0, decimals=0, value=192.0)
        self._logo_size.float_changed.connect(lambda v: self._emit({"compositionLogoSize": float(v)}))
        self._logo_react = _expert_slider("Reactivity", minimum=0.0, maximum=1.0, step=0.05, value=0.0)
        self._logo_react.float_changed.connect(
            lambda v: self._emit({"compositionLogoReactivity": float(v)})
        )
        self._logo_ox = _expert_slider("Offset X", minimum=-0.5, maximum=0.5, step=0.01, value=0.0)
        self._logo_ox.float_changed.connect(lambda v: self._emit({"compositionLogoOffsetX": float(v)}))
        self._logo_oy = _expert_slider("Offset Y", minimum=-0.5, maximum=0.5, step=0.01, value=0.0)
        self._logo_oy.float_changed.connect(lambda v: self._emit({"compositionLogoOffsetY": float(v)}))
        self._add_expert(self._logo_scale)
        self._add_expert(self._logo_opacity)
        self._add_expert(self._logo_size)
        self._add_expert(self._logo_react)
        self._add_expert(self._logo_ox)
        self._add_expert(self._logo_oy)

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select logo", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.svg)"
        )
        if path:
            self._emit({"logoPath": path, "logoEnabled": True})

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("logoEnabled", True)))
        self._path.setText(str(state.get("logoPath") or ""))
        set_combo_data(self._animation, str(state.get("compositionLogoAnimation") or "none"))
        self._attach.setChecked(bool(state.get("spectrumAttachToLogo")))
        self._circle.setChecked(bool(state.get("compositionLogoCircleMask")))
        self._logo_scale.set_float(float(state.get("compositionLogoScale") or 1.0))
        self._logo_opacity.set_float(float(state.get("compositionLogoOpacity") or 1.0))
        self._logo_size.set_float(float(state.get("compositionLogoSize") or 192.0))
        self._logo_react.set_float(float(state.get("compositionLogoReactivity") or 0.0))
        self._logo_ox.set_float(float(state.get("compositionLogoOffsetX") or 0.0))
        self._logo_oy.set_float(float(state.get("compositionLogoOffsetY") or 0.0))
        self._binding = False


class TextInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Text", subtitle="Album / playlist overlays.")

        self._enabled = QCheckBox("Text overlays enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"compositionTextEnabled": checked}))
        self._section.add_widget(self._enabled)

        self._album = QCheckBox("Album title")
        self._album.toggled.connect(lambda checked: self._emit({"albumEnabled": checked}))
        self._section.add_widget(self._album)
        self._album_text = QLineEdit()
        self._album_text.setPlaceholderText("Album name")
        self._album_text.editingFinished.connect(
            lambda: self._emit({"albumManualText": self._album_text.text()})
        )
        self._section.add_widget(stacked_field("Album text", self._album_text))

        self._title = QCheckBox("Playlist / titles")
        self._title.toggled.connect(lambda checked: self._emit({"titleEnabled": checked}))
        self._section.add_widget(self._title)
        self._title_text = QLineEdit()
        self._title_text.setPlaceholderText("Track titles (one line)")
        self._title_text.editingFinished.connect(
            lambda: self._emit({"titleManualText": self._title_text.text()})
        )
        self._section.add_widget(stacked_field("Playlist text", self._title_text))

        self._text_opacity = _expert_slider("Opacity", minimum=0.1, maximum=1.0, step=0.05, value=1.0)
        self._text_opacity.float_changed.connect(
            lambda v: self._emit({"compositionTextOpacity": float(v)})
        )
        self._text_scale = _expert_slider("Scale", minimum=0.5, maximum=2.5, step=0.05, value=1.0)
        self._text_scale.float_changed.connect(
            lambda v: self._emit({"compositionTextScale": float(v)})
        )
        self._text_oy = _expert_slider("Offset Y", minimum=-0.4, maximum=0.4, step=0.01, value=0.0)
        self._text_oy.float_changed.connect(
            lambda v: self._emit({"compositionTextOffsetY": float(v)})
        )
        self._add_expert(self._text_opacity)
        self._add_expert(self._text_scale)
        self._add_expert(self._text_oy)

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("compositionTextEnabled")))
        self._album.setChecked(bool(state.get("albumEnabled")))
        self._title.setChecked(bool(state.get("titleEnabled")))
        self._album_text.setText(str(state.get("albumManualText") or ""))
        self._title_text.setText(str(state.get("titleManualText") or ""))
        self._text_opacity.set_float(float(state.get("compositionTextOpacity") or 1.0))
        self._text_scale.set_float(float(state.get("compositionTextScale") or 1.0))
        self._text_oy.set_float(float(state.get("compositionTextOffsetY") or 0.0))
        self._binding = False


_OVERLAY_STYLES: tuple[tuple[str, str], ...] = (
    ("film_grain", "Film Grain"),
    ("vhs", "VHS"),
    ("glitch", "Glitch"),
    ("scanlines", "Scanlines"),
    ("light_leak", "Light Leak"),
    ("dust", "Dust"),
)


class OverlayInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Overlay", subtitle="Top composites — not Text typography.")
        self._enabled = QCheckBox("Overlay enabled")
        self._enabled.toggled.connect(
            lambda checked: self._emit({"compositionOverlayEnabled": checked})
        )
        self._section.add_widget(self._enabled)
        self._style = QComboBox()
        populate_combo(self._style, _OVERLAY_STYLES, include_none=False)
        self._style.currentIndexChanged.connect(
            lambda: self._emit({"overlayStyle": self._style.currentData() or "film_grain"})
        )
        self._section.add_widget(form_row("Style", self._style))
        self._animation = QComboBox()
        populate_combo(self._animation, catalog_options()["animations"])
        self._animation.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionOverlayAnimation": self._animation.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Animation", self._animation))

        self._overlay_amount = _expert_slider("Amount", minimum=0.05, maximum=1.0, step=0.05, value=0.28)
        self._overlay_amount.float_changed.connect(
            lambda v: self._emit({"compositionOverlayAmount": float(v)})
        )
        self._add_expert(self._overlay_amount)

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("compositionOverlayEnabled")))
        set_combo_data(
            self._style, str(state.get("overlayStyle") or "film_grain"), fallback="film_grain"
        )
        set_combo_data(self._animation, str(state.get("compositionOverlayAnimation") or "none"))
        self._overlay_amount.set_float(float(state.get("compositionOverlayAmount") or 0.28))
        self._binding = False


class ParticlesInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Particles", subtitle="Type × Behavior.")
        opts = catalog_options()
        self._enabled = QCheckBox("Particles enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"particlesEnabled": checked}))
        self._section.add_widget(self._enabled)
        self._type = QComboBox()
        populate_combo(self._type, opts["particle_types"])
        self._type.currentIndexChanged.connect(
            lambda: self._emit({"compositionParticleType": self._type.currentData() or "none"})
        )
        self._section.add_widget(form_row("Type", self._type))
        self._behavior = QComboBox()
        populate_combo(self._behavior, opts["animations"])
        self._behavior.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionParticleBehavior": self._behavior.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Behavior", self._behavior))

        self._spawn = _expert_slider("Spawn rate", minimum=0.1, maximum=3.0, step=0.05, value=1.0)
        self._spawn.float_changed.connect(
            lambda v: self._emit({"compositionParticleSpawn": float(v)})
        )
        self._size = _expert_slider("Size", minimum=0.25, maximum=4.0, step=0.05, value=1.0)
        self._size.float_changed.connect(lambda v: self._emit({"compositionParticleSize": float(v)}))
        self._p_opacity = _expert_slider("Opacity", minimum=0.05, maximum=1.0, step=0.05, value=0.35)
        self._p_opacity.float_changed.connect(
            lambda v: self._emit({"compositionParticleOpacity": float(v)})
        )
        self._speed = _expert_slider("Speed", minimum=0.25, maximum=3.0, step=0.05, value=1.0)
        self._speed.float_changed.connect(lambda v: self._emit({"compositionParticleSpeed": float(v)}))
        self._p_react = _expert_slider("Reactivity", minimum=0.0, maximum=1.0, step=0.05, value=0.45)
        self._p_react.float_changed.connect(
            lambda v: self._emit({"compositionParticleReactivity": float(v)})
        )
        self._add_expert(self._spawn)
        self._add_expert(self._size)
        self._add_expert(self._p_opacity)
        self._add_expert(self._speed)
        self._add_expert(self._p_react)

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("particlesEnabled")))
        set_combo_data(self._type, str(state.get("compositionParticleType") or "none"))
        set_combo_data(self._behavior, str(state.get("compositionParticleBehavior") or "none"))
        self._spawn.set_float(float(state.get("compositionParticleSpawn") or 1.0))
        self._size.set_float(float(state.get("compositionParticleSize") or 1.0))
        self._p_opacity.set_float(float(state.get("compositionParticleOpacity") or 0.35))
        self._speed.set_float(float(state.get("compositionParticleSpeed") or 1.0))
        self._p_react.set_float(float(state.get("compositionParticleReactivity") or 0.45))
        self._binding = False


class LightingInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lighting", subtitle="Effect × Trigger (not whole-frame post).")
        opts = catalog_options()
        self._effect = QComboBox()
        populate_combo(self._effect, opts["lighting_effects"])
        self._effect.currentIndexChanged.connect(
            lambda: self._emit({"compositionLightingEffect": self._effect.currentData() or "none"})
        )
        self._section.add_widget(form_row("Effect", self._effect))
        self._trigger = QComboBox()
        populate_combo(self._trigger, opts["lighting_triggers"], include_none=False)
        self._trigger.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionLightingTrigger": self._trigger.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Trigger", self._trigger))

        self._intensity = _expert_slider("Intensity", minimum=0.1, maximum=1.5, step=0.05, value=0.85)
        self._intensity.float_changed.connect(
            lambda v: self._emit({"compositionLightingIntensity": float(v)})
        )
        self._thickness = _expert_slider("Thickness", minimum=0.5, maximum=3.0, step=0.05, value=1.0)
        self._thickness.float_changed.connect(
            lambda v: self._emit({"compositionLightingThickness": float(v)})
        )
        self._l_glow = _expert_slider("Glow", minimum=0.0, maximum=1.0, step=0.05, value=0.55)
        self._l_glow.float_changed.connect(lambda v: self._emit({"compositionLightingGlow": float(v)}))
        self._flash = _expert_slider("Flash rate", minimum=0.1, maximum=2.0, step=0.05, value=0.85)
        self._flash.float_changed.connect(
            lambda v: self._emit({"compositionLightingFlashRate": float(v)})
        )
        self._l_speed = _expert_slider("Speed", minimum=0.25, maximum=3.0, step=0.05, value=1.0)
        self._l_speed.float_changed.connect(
            lambda v: self._emit({"compositionLightingSpeed": float(v)})
        )
        self._add_expert(self._intensity)
        self._add_expert(self._thickness)
        self._add_expert(self._l_glow)
        self._add_expert(self._flash)
        self._add_expert(self._l_speed)

    def bind(self, state: dict) -> None:
        self._binding = True
        set_combo_data(self._effect, str(state.get("compositionLightingEffect") or "none"))
        set_combo_data(self._trigger, str(state.get("compositionLightingTrigger") or "none"))
        self._intensity.set_float(float(state.get("compositionLightingIntensity") or 0.85))
        self._thickness.set_float(float(state.get("compositionLightingThickness") or 1.0))
        self._l_glow.set_float(float(state.get("compositionLightingGlow") or 0.55))
        self._flash.set_float(float(state.get("compositionLightingFlashRate") or 0.85))
        self._l_speed.set_float(float(state.get("compositionLightingSpeed") or 1.0))
        self._binding = False


class CameraInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Camera", subtitle="Scene-level behavior.")
        self._behavior = QComboBox()
        populate_combo(self._behavior, catalog_options()["camera_behaviors"])
        self._behavior.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionCameraBehavior": self._behavior.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Behavior", self._behavior))

        self._zoom = _expert_slider("Zoom bias", minimum=0.7, maximum=1.6, step=0.02, value=1.0)
        self._zoom.float_changed.connect(lambda v: self._emit({"compositionCameraZoomBias": float(v)}))
        self._pan_x = _expert_slider("Pan X", minimum=-0.5, maximum=0.5, step=0.01, value=0.0)
        self._pan_x.float_changed.connect(lambda v: self._emit({"compositionCameraPanX": float(v)}))
        self._pan_y = _expert_slider("Pan Y", minimum=-0.5, maximum=0.5, step=0.01, value=0.0)
        self._pan_y.float_changed.connect(lambda v: self._emit({"compositionCameraPanY": float(v)}))
        self._shake = _expert_slider("Shake amount", minimum=0.0, maximum=1.0, step=0.05, value=0.5)
        self._shake.float_changed.connect(
            lambda v: self._emit({"compositionCameraShakeAmount": float(v)})
        )
        self._roll = _expert_slider("Roll bias", minimum=-15.0, maximum=15.0, step=0.5, decimals=1, value=0.0)
        self._roll.float_changed.connect(
            lambda v: self._emit({"compositionCameraRollBias": float(v)})
        )
        self._add_expert(self._zoom)
        self._add_expert(self._pan_x)
        self._add_expert(self._pan_y)
        self._add_expert(self._shake)
        self._add_expert(self._roll)

    def bind(self, state: dict) -> None:
        self._binding = True
        set_combo_data(self._behavior, str(state.get("compositionCameraBehavior") or "none"))
        self._zoom.set_float(float(state.get("compositionCameraZoomBias") or 1.0))
        self._pan_x.set_float(float(state.get("compositionCameraPanX") or 0.0))
        self._pan_y.set_float(float(state.get("compositionCameraPanY") or 0.0))
        self._shake.set_float(float(state.get("compositionCameraShakeAmount") or 0.5))
        self._roll.set_float(float(state.get("compositionCameraRollBias") or 0.0))
        self._binding = False


class PostInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Post Processing", subtitle="Whole-frame stack.")
        self._checks: dict[str, QCheckBox] = {}
        checks_host = QWidget()
        checks_grid = QGridLayout(checks_host)
        checks_grid.setContentsMargins(0, 0, 0, 0)
        checks_grid.setHorizontalSpacing(8)
        checks_grid.setVerticalSpacing(2)
        for i, (eid, label) in enumerate(catalog_options()["post_effects"]):
            box = QCheckBox(label)
            box.toggled.connect(self._emit_stack)
            self._checks[eid] = box
            checks_grid.addWidget(box, i // 2, i % 2)
        self._section.add_widget(checks_host)

        self._amount = _expert_slider("Stack amount", minimum=0.05, maximum=1.0, step=0.05, value=0.35)
        self._amount.float_changed.connect(
            lambda v: self._emit({"compositionPostAmount": float(v)})
        )
        self._quality = QComboBox()
        populate_combo(
            self._quality,
            (("low", "Low"), ("medium", "Medium"), ("high", "High")),
            include_none=False,
        )
        self._quality.currentIndexChanged.connect(
            lambda: self._emit({"compositionPerformanceQuality": self._quality.currentData() or "medium"})
        )
        self._lod = QCheckBox("LOD / GPU cache prefer")
        self._lod.toggled.connect(lambda checked: self._emit({"compositionPerformanceLod": checked}))
        self._add_expert(self._amount)
        self._add_expert(form_row("Render quality", self._quality))
        self._add_expert(self._lod)

    def _emit_stack(self) -> None:
        enabled = [eid for eid, box in self._checks.items() if box.isChecked()]
        self._emit({"compositionPostEffects": enabled})

    def bind(self, state: dict) -> None:
        self._binding = True
        selected = set(state.get("compositionPostEffects") or [])
        for eid, box in self._checks.items():
            box.setChecked(eid in selected)
        self._amount.set_float(float(state.get("compositionPostAmount") or 0.35))
        set_combo_data(
            self._quality,
            str(state.get("compositionPerformanceQuality") or "medium"),
            fallback="medium",
        )
        self._lod.setChecked(bool(state.get("compositionPerformanceLod", True)))
        self._binding = False


class AudioMappingInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Audio Mapping",
            subtitle="Spectrum reaction drives rings with Overall bus. Per-layer Audio bus overrides it. Vocals / Melody / Snare are FFT heuristics.",
        )
        self._audio_path = QLineEdit()
        self._audio_path.setReadOnly(True)
        self._audio_path.setPlaceholderText("No audio selected")
        pick_audio = QPushButton("Select")
        pick_audio.clicked.connect(self._pick_audio)
        self._section.add_widget(asset_row("Track", self._audio_path, pick_audio))

        opts = catalog_options()
        self._combos: dict[str, QComboBox] = {}
        for target, label in opts["audio_targets"]:
            combo = QComboBox()
            populate_combo(combo, opts["audio_buses"])
            combo.currentIndexChanged.connect(self._emit_matrix)
            self._combos[target] = combo
            self._section.add_widget(form_row(label, combo))

        self._gain = _expert_slider("Input gain", minimum=0.25, maximum=3.0, step=0.05, value=1.0)
        self._gain.float_changed.connect(lambda v: self._emit({"compositionAudioGain": float(v)}))
        self._smooth = _expert_slider("Smoothing", minimum=0.0, maximum=0.99, step=0.01, value=0.65)
        self._smooth.float_changed.connect(
            lambda v: self._emit({"compositionAudioSmoothing": float(v)})
        )
        self._bass = _expert_slider("Bass emphasis", minimum=0.5, maximum=2.0, step=0.05, value=1.0)
        self._bass.float_changed.connect(
            lambda v: self._emit({"compositionAudioBassEmphasis": float(v)})
        )
        self._add_expert(self._gain)
        self._add_expert(self._smooth)
        self._add_expert(self._bass)

    def _pick_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select audio track", "", "Audio (*.mp3 *.wav *.m4a *.flac)"
        )
        if path:
            self._emit({"audioPath": path})

    def _emit_matrix(self, *_args) -> None:
        self._emit(
            {
                "compositionAudioMapping": {
                    target: combo.currentData() or "none"
                    for target, combo in self._combos.items()
                }
            }
        )

    def bind(self, state: dict) -> None:
        self._binding = True
        self._audio_path.setText(str(state.get("audioPath") or ""))
        mapping = state.get("compositionAudioMapping")
        mapping = mapping if isinstance(mapping, dict) else {}
        for target, combo in self._combos.items():
            set_combo_data(combo, str(mapping.get(target) or "none"))
        self._gain.set_float(float(state.get("compositionAudioGain") or 1.0))
        self._smooth.set_float(float(state.get("compositionAudioSmoothing") or 0.65))
        self._bass.set_float(float(state.get("compositionAudioBassEmphasis") or 1.0))
        self._binding = False


def build_studio_inspectors() -> dict[str, _AxisPanel]:
    return {
        "palette": PaletteInspector(),
        "background": BackgroundInspector(),
        "spectrum": SpectrumInspector(),
        "text": TextInspector(),
        "overlay": OverlayInspector(),
        "particles": ParticlesInspector(),
        "lighting": LightingInspector(),
        "camera": CameraInspector(),
        "post": PostInspector(),
        "audio_mapping": AudioMappingInspector(),
    }
