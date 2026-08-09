"""Axes-only Studio inspectors (docs Level 2 — no legacy Video chrome)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.studio.lib.scene_document import catalog_options
from features.studio.widgets.axis_combo import populate_combo, set_combo_data
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel, form_row


class _AxisPanel(QWidget):
    patch_requested = Signal(dict)

    def __init__(self, title: str, *, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)
        self._section = SettingsPanel(title, subtitle=subtitle, fill_available_height=False)
        root.addWidget(self._section)
        root.addStretch()

    def _emit(self, patch: dict) -> None:
        if not self._binding:
            self.patch_requested.emit(patch)

    def bind(self, state: dict) -> None:
        raise NotImplementedError


class PaletteInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Color Palette", subtitle="Global tint for spectrum / particles / lighting.")
        self._combo = QComboBox()
        populate_combo(self._combo, catalog_options()["palettes"], none_label="None (default)")
        self._combo.currentIndexChanged.connect(
            lambda: self._emit({"compositionColorPalette": self._combo.currentData() or "none"})
        )
        self._section.add_widget(form_row("Palette", self._combo))

    def bind(self, state: dict) -> None:
        self._binding = True
        set_combo_data(self._combo, str(state.get("compositionColorPalette") or "none"))
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

        path_row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setReadOnly(True)
        self._path.setPlaceholderText("No image selected")
        pick = QPushButton("Select image")
        pick.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        pick.clicked.connect(self._pick_image)
        path_row.addWidget(self._path, stretch=1)
        path_row.addWidget(pick)
        host = QWidget()
        host.setLayout(path_row)
        self._section.add_widget(form_row("Image", host))

        self._motion = QComboBox()
        populate_combo(self._motion, opts["background_motions"], include_none=False)
        self._motion.currentIndexChanged.connect(
            lambda: self._emit({"compositionBackgroundMotion": self._motion.currentData() or "static"})
        )
        self._section.add_widget(form_row("Motion", self._motion))

        self._atmosphere = QComboBox()
        populate_combo(self._atmosphere, opts["atmosphere"])
        self._atmosphere.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionBackgroundAtmosphere": self._atmosphere.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Atmosphere", self._atmosphere))

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select background image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._emit({"backgroundImage": path, "backgroundEnabled": True})

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("backgroundEnabled")))
        self._path.setText(str(state.get("backgroundImage") or ""))
        set_combo_data(self._motion, str(state.get("compositionBackgroundMotion") or "static"), fallback="static")
        set_combo_data(self._atmosphere, str(state.get("compositionBackgroundAtmosphere") or "none"))
        self._binding = False


class SpectrumInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Spectrum", subtitle="Shape × Material × Animation.")
        opts = catalog_options()
        self._enabled = QCheckBox("Spectrum enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"spectrumEnabled": checked}))
        self._section.add_widget(self._enabled)

        self._shape = QComboBox()
        populate_combo(self._shape, opts["shapes"])
        self._shape.currentIndexChanged.connect(
            lambda: self._emit({"compositionSpectrumShape": self._shape.currentData() or "none"})
        )
        self._section.add_widget(form_row("Shape", self._shape))

        self._material = QComboBox()
        populate_combo(self._material, opts["materials"])
        self._material.currentIndexChanged.connect(
            lambda: self._emit({"compositionSpectrumMaterial": self._material.currentData() or "none"})
        )
        self._section.add_widget(form_row("Material", self._material))

        self._animation = QComboBox()
        populate_combo(self._animation, opts["animations"])
        self._animation.currentIndexChanged.connect(
            lambda: self._emit(
                {"compositionSpectrumAnimation": self._animation.currentData() or "none"}
            )
        )
        self._section.add_widget(form_row("Animation", self._animation))

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("spectrumEnabled")))
        set_combo_data(self._shape, str(state.get("compositionSpectrumShape") or "none"))
        set_combo_data(self._material, str(state.get("compositionSpectrumMaterial") or "none"))
        set_combo_data(self._animation, str(state.get("compositionSpectrumAnimation") or "none"))
        self._binding = False


class LogoInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Logo", subtitle="Asset + shared animation behavior.")
        self._enabled = QCheckBox("Logo enabled")
        self._enabled.toggled.connect(lambda checked: self._emit({"logoEnabled": checked}))
        self._section.add_widget(self._enabled)

        path_row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setReadOnly(True)
        pick = QPushButton("Select logo")
        pick.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        pick.clicked.connect(self._pick_logo)
        path_row.addWidget(self._path, stretch=1)
        path_row.addWidget(pick)
        host = QWidget()
        host.setLayout(path_row)
        self._section.add_widget(form_row("File", host))

        self._animation = QComboBox()
        populate_combo(self._animation, catalog_options()["animations"])
        self._animation.currentIndexChanged.connect(
            lambda: self._emit({"compositionLogoAnimation": self._animation.currentData() or "none"})
        )
        self._section.add_widget(form_row("Animation", self._animation))

        self._attach = QCheckBox("Attach spectrum to logo")
        self._attach.toggled.connect(lambda checked: self._emit({"spectrumAttachToLogo": checked}))
        self._section.add_widget(self._attach)

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
        self._binding = False


class TextInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Text",
            subtitle="Typography enable + content. Style packs live on Video only.",
        )
        note = QLabel("Album / Playlist content only — no legacy style presets.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        self._section.add_widget(note)

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
        self._section.add_widget(form_row("Album text", self._album_text))

        self._title = QCheckBox("Playlist / titles")
        self._title.toggled.connect(lambda checked: self._emit({"titleEnabled": checked}))
        self._section.add_widget(self._title)
        self._title_text = QLineEdit()
        self._title_text.setPlaceholderText("Track titles (one line)")
        self._title_text.editingFinished.connect(
            lambda: self._emit({"titleManualText": self._title_text.text()})
        )
        self._section.add_widget(form_row("Playlist text", self._title_text))

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("compositionTextEnabled")))
        self._album.setChecked(bool(state.get("albumEnabled")))
        self._title.setChecked(bool(state.get("titleEnabled")))
        self._album_text.setText(str(state.get("albumManualText") or ""))
        self._title_text.setText(str(state.get("titleManualText") or ""))
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

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("compositionOverlayEnabled")))
        set_combo_data(self._style, str(state.get("overlayStyle") or "film_grain"), fallback="film_grain")
        set_combo_data(self._animation, str(state.get("compositionOverlayAnimation") or "none"))
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

    def bind(self, state: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(state.get("particlesEnabled")))
        set_combo_data(self._type, str(state.get("compositionParticleType") or "none"))
        set_combo_data(self._behavior, str(state.get("compositionParticleBehavior") or "none"))
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

    def bind(self, state: dict) -> None:
        self._binding = True
        set_combo_data(self._effect, str(state.get("compositionLightingEffect") or "none"))
        set_combo_data(self._trigger, str(state.get("compositionLightingTrigger") or "none"))
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

    def bind(self, state: dict) -> None:
        self._binding = True
        set_combo_data(self._behavior, str(state.get("compositionCameraBehavior") or "none"))
        self._binding = False


class PostInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Post Processing", subtitle="Whole-frame stack.")
        self._checks: dict[str, QCheckBox] = {}
        for eid, label in catalog_options()["post_effects"]:
            box = QCheckBox(label)
            box.toggled.connect(self._emit_stack)
            self._checks[eid] = box
            self._section.add_widget(box)

    def _emit_stack(self) -> None:
        enabled = [eid for eid, box in self._checks.items() if box.isChecked()]
        self._emit({"compositionPostEffects": enabled})

    def bind(self, state: dict) -> None:
        self._binding = True
        selected = set(state.get("compositionPostEffects") or [])
        for eid, box in self._checks.items():
            box.setChecked(eid in selected)
        self._binding = False


class AudioMappingInspector(_AxisPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Audio Mapping",
            subtitle="Vocals / Melody / Snare are v1 FFT heuristics.",
        )
        note = QLabel("Route buses → Lighting / Particles / Camera / Logo.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        self._section.add_widget(note)

        path_row = QHBoxLayout()
        self._audio_path = QLineEdit()
        self._audio_path.setReadOnly(True)
        self._audio_path.setPlaceholderText("No audio selected")
        pick_audio = QPushButton("Select audio")
        pick_audio.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        pick_audio.clicked.connect(self._pick_audio)
        path_row.addWidget(self._audio_path, stretch=1)
        path_row.addWidget(pick_audio)
        audio_host = QWidget()
        audio_host.setLayout(path_row)
        self._section.add_widget(form_row("Track", audio_host))

        opts = catalog_options()
        self._combos: dict[str, QComboBox] = {}
        for target, label in opts["audio_targets"]:
            combo = QComboBox()
            populate_combo(combo, opts["audio_buses"])
            combo.currentIndexChanged.connect(self._emit_matrix)
            self._combos[target] = combo
            self._section.add_widget(form_row(label, combo))

    def _pick_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select audio track", "", "Audio (*.mp3 *.wav *.m4a *.flac)"
        )
        if path:
            self._emit({"audioPath": path})

    def _emit_matrix(self) -> None:
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
        self._binding = False


def build_studio_inspectors() -> dict[str, _AxisPanel]:
    return {
        "palette": PaletteInspector(),
        "background": BackgroundInspector(),
        "spectrum": SpectrumInspector(),
        "logo": LogoInspector(),
        "text": TextInspector(),
        "overlay": OverlayInspector(),
        "particles": ParticlesInspector(),
        "lighting": LightingInspector(),
        "camera": CameraInspector(),
        "post": PostInspector(),
        "audio_mapping": AudioMappingInspector(),
    }
