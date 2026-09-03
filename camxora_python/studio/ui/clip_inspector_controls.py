"""Alignment, remove-background, and mask controls for the clip inspector."""

from __future__ import annotations

from collections.abc import Callable

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from studio.core.models import Clip, MediaAsset
from studio.core.project_state import ProjectState
from studio.media.remove_bg import process_remove_background, rembg_available
from studio.render.clip_geometry import IMAGE_FIT_MODES, align_clip_transform, distribute_selected_clips
from studio.render.compositor import clear_image_cache
from studio.ui.icons.lucide_icons import (
    ICON_COLOR,
    ICON_COLOR_DIM,
    ICON_SZ_INSPECTOR_ALIGN,
    ICON_SZ_MASK_SHAPE,
    set_button_lucide_icon,
)
from studio.app.theme import PALETTE
from studio.ui.inspector_layout import (
    FIELD_GAP,
    FIELD_ROW_GAP,
    SECTION_GAP,
    SLIDER_BLOCK_GAP,
    SPIN_INPUT_WIDTH,
    SPIN_LABEL_WIDTH,
    add_section_spacer,
    apply_page_layout,
    configure_field_row,
    configure_shape_grid,
    configure_slider_column,
)

logger = logging.getLogger(__name__)


class _NoScrollSlider(QSlider):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class _NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class _AlignButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorAlignButton")
        self.setToolTip(tooltip)
        self.setFixedSize(30, 26)
        set_button_lucide_icon(
            self,
            icon_name,
            size=ICON_SZ_INSPECTOR_ALIGN,
            color=ICON_COLOR,
        )
        self._icon_name = icon_name

    def set_dimmed(self, dimmed: bool) -> None:
        set_button_lucide_icon(
            self,
            self._icon_name,
            size=ICON_SZ_INSPECTOR_ALIGN,
            color=ICON_COLOR_DIM if dimmed else ICON_COLOR,
        )


class _MaskShapeButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorMaskShapeButton")
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(40, 36)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoDefault(False)
        self.setDefault(False)
        self._icon_name = icon_name
        self._apply_style()

    def _apply_style(self) -> None:
        if self.isChecked():
            self.setStyleSheet(
                f"QPushButton {{ background-color: {PALETTE.accent};"
                f" border: 1px solid {PALETTE.accent}; border-radius: 6px; padding: 0; }}"
                f"QPushButton:hover {{ background-color: #8a70ff; border-color: #8a70ff; }}"
            )
            icon_color = "#ffffff"
        else:
            self.setStyleSheet(
                f"QPushButton {{ background-color: {PALETTE.panel2};"
                f" border: 1px solid {PALETTE.border}; border-radius: 6px; padding: 0; }}"
                f"QPushButton:hover {{ border-color: {PALETTE.accent}; background-color: {PALETTE.panel2}; }}"
            )
            icon_color = ICON_COLOR
        set_button_lucide_icon(
            self,
            self._icon_name,
            size=ICON_SZ_MASK_SHAPE,
            color=icon_color,
        )

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._apply_style()


class AlignmentToolbar(QFrame):
    """CapCut-style align + distribute row."""

    def __init__(
        self,
        project_state: ProjectState,
        clip: Clip,
        on_preview: Callable[..., None],
        on_change: Callable[..., None],
        on_preview_for: Callable[[str], Callable[..., None]] | None = None,
        on_change_for: Callable[[str], Callable[..., None]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = project_state
        self._clip = clip
        self._on_preview = on_preview
        self._on_change = on_change
        self._on_preview_for = on_preview_for or (lambda _cid: on_preview)
        self._on_change_for = on_change_for or (lambda _cid: on_change)
        self.setObjectName("InspectorAlignToolbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        align_specs = (
            ("align-left", "left", "Align left"),
            ("align-h-center", "center_h", "Align horizontal center"),
            ("align-right", "right", "Align right"),
            ("|", "sep1", ""),
            ("align-top", "top", "Align top"),
            ("align-v-center", "center_v", "Align vertical center"),
            ("align-bottom", "bottom", "Align bottom"),
        )
        for icon_name, key, tip in align_specs:
            if key.startswith("sep"):
                sep = QFrame(self)
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setObjectName("InspectorAlignSeparator")
                layout.addWidget(sep)
                continue
            btn = _AlignButton(icon_name, tip, self)
            btn.setProperty("alignIcon", icon_name)
            btn.clicked.connect(lambda _checked, k=key: self._align(k))
            layout.addWidget(btn)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("InspectorAlignSeparator")
        layout.addWidget(sep)

        dist_h = _AlignButton("distribute-h", "Distribute horizontally", self)
        dist_v = _AlignButton("distribute-v", "Distribute vertically", self)
        dist_h.setProperty("alignIcon", "distribute-h")
        dist_v.setProperty("alignIcon", "distribute-v")
        dist_h.clicked.connect(lambda: self._distribute("horizontal"))
        dist_v.clicked.connect(lambda: self._distribute("vertical"))
        can_distribute = len(self._state._effective_selection()) >= 2
        dist_h.setEnabled(can_distribute)
        dist_v.setEnabled(can_distribute)
        dist_h.set_dimmed(not can_distribute)
        dist_v.set_dimmed(not can_distribute)
        layout.addWidget(dist_h)
        layout.addWidget(dist_v)
        layout.addStretch(1)

    def _frame_size(self, clip: Clip) -> tuple[int, int]:
        media = self._state.get_media(clip.media_id)
        if media and media.width and media.height:
            return int(media.width), int(media.height)
        if media and media.type == "image":
            import cv2

            img = cv2.imread(media.path)
            if img is not None:
                h, w = img.shape[:2]
                return w, h
        return self._state.canvas_size()

    def _align(self, alignment: str) -> None:
        clip = self._live_clip()
        if clip is None:
            return
        src_w, src_h = self._frame_size(clip)
        canvas_w, canvas_h = self._state.canvas_size()
        tx, ty = align_clip_transform(
            clip, alignment, src_w, src_h, canvas_w, canvas_h
        )
        self._on_preview(transform_x=tx, transform_y=ty)
        self._on_change(transform_x=tx, transform_y=ty)

    def _live_clip(self) -> Clip | None:
        ref = self._state.get_clip(self._clip.id)
        return ref[1] if ref else None

    def _distribute(self, axis: str) -> None:
        ids = self._state._effective_selection()
        clips = [c for cid in ids if (c := self._state.get_clip(cid)) is not None]
        visual = [c for c in clips if c.kind in ("image", "video")]
        if len(visual) < 2:
            return

        updates = distribute_selected_clips(
            self._state,
            axis,
            visual,
            self._state.canvas_size()[0],
            self._state.canvas_size()[1],
            self._frame_size,
        )
        for clip_id, (tx, ty) in updates.items():
            self._on_preview_for(clip_id)(transform_x=tx, transform_y=ty)
            self._on_change_for(clip_id)(transform_x=tx, transform_y=ty)


class _FitModeButton(QPushButton):
    """Purple highlight when active — matches mask shape buttons."""

    def __init__(self, label: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("InspectorFitButton")
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setMinimumWidth(52)
        self.setFixedHeight(28)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoDefault(False)
        self.setDefault(False)
        self._apply_style()

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._apply_style()

    def _apply_style(self) -> None:
        if self.isChecked():
            self.setStyleSheet(
                f"QPushButton {{ background-color: {PALETTE.accent};"
                f" border: 1px solid {PALETTE.accent}; border-radius: 6px;"
                f" color: #ffffff; font-size: 11px; font-weight: 600; padding: 0 8px; }}"
                f"QPushButton:hover {{ background-color: #8a70ff; border-color: #8a70ff;"
                f" color: #ffffff; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background-color: {PALETTE.panel2};"
                f" border: 1px solid {PALETTE.border}; border-radius: 6px;"
                f" color: {PALETTE.text_dim}; font-size: 11px; font-weight: 600; padding: 0 8px; }}"
                f"QPushButton:hover {{ color: {PALETTE.text}; border-color: {PALETTE.accent};"
                f" background-color: {PALETTE.panel2}; }}"
            )


class ImageFitModeRow(QFrame):
    """Fit / Cover / Fill — how the image maps to the project canvas."""

    _MODES: tuple[tuple[str, str, str], ...] = (
        ("fit", "Fit", "Show entire image (letterbox)"),
        ("cover", "Cover", "Fill canvas, crop edges if needed"),
        ("fill", "Fill", "Stretch to canvas size"),
    )

    def __init__(
        self,
        clip: Clip,
        on_preview: Callable[..., None],
        on_change: Callable[..., None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorFitToolbar")
        self._clip = clip
        self._on_preview = on_preview
        self._on_change = on_change
        self._active_mode: str | None = clip.fit_mode if clip.fit_mode in IMAGE_FIT_MODES else None
        self._pre_fit: tuple[float, float, float] | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        self._buttons: dict[str, _FitModeButton] = {}
        for mode_id, label, tooltip in self._MODES:
            btn = _FitModeButton(label, tooltip)
            btn.setChecked(mode_id == self._active_mode)
            btn.clicked.connect(lambda _c, mid=mode_id: self._select(mid))
            layout.addWidget(btn)
            self._buttons[mode_id] = btn
        layout.addStretch(1)

    def _select(self, mode_id: str) -> None:
        if self._active_mode == mode_id:
            self._active_mode = None
            for btn in self._buttons.values():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            fields: dict[str, object] = {"fit_mode": "free"}
            if self._pre_fit is not None:
                tx, ty, ts = self._pre_fit
                fields.update(
                    {
                        "transform_x": tx,
                        "transform_y": ty,
                        "transform_scale": ts,
                    }
                )
                self._pre_fit = None
            logger.info("fit_mode deselect → free fields=%s", fields)
            self._on_change(**fields)
            return

        if self._active_mode is None:
            self._pre_fit = (
                float(self._clip.transform_x if self._clip.transform_x is not None else 0.5),
                float(self._clip.transform_y if self._clip.transform_y is not None else 0.5),
                float(self._clip.transform_scale or 1.0),
            )

        self._active_mode = mode_id
        for mid, btn in self._buttons.items():
            btn.blockSignals(True)
            btn.setChecked(mid == mode_id)
            btn.blockSignals(False)
        fields = {
            "fit_mode": mode_id,
            "transform_x": 0.5,
            "transform_y": 0.5,
            "transform_scale": 1.0,
        }
        logger.info("fit_mode select → %s fields=%s", mode_id, fields)
        self._on_change(**fields)


class _RemoveBgWorker(QThread):
    finished = Signal(str, str)  # output path or "", message

    def __init__(self, source_path: str) -> None:
        super().__init__()
        self._source_path = source_path

    def run(self) -> None:
        path, message = process_remove_background(self._source_path)
        self.finished.emit(path or "", message)


class RemoveBgSection(QWidget):
    def __init__(
        self,
        clip: Clip,
        media: MediaAsset | None,
        on_preview: Callable[..., None],
        on_change: Callable[..., None],
        on_media_path: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._clip = clip
        self._media = media
        self._on_preview = on_preview
        self._on_change = on_change
        self._on_media_path = on_media_path
        self._worker: _RemoveBgWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self._toggle = QCheckBox("Remove background")
        self._toggle.blockSignals(True)
        self._toggle.setChecked(clip.remove_bg_enabled)
        self._toggle.blockSignals(False)
        self._toggle.setEnabled(media is not None and media.type == "image")
        self._toggle.toggled.connect(self._on_toggle)
        row.addWidget(self._toggle)
        row.addStretch(1)
        layout.addLayout(row)

        hint_parts = ["Runs locally on your machine."]
        if rembg_available():
            hint_parts.append("Using rembg AI model.")
        else:
            hint_parts.append("OpenCV fallback — pip install rembg for better edges.")
        if media is not None and media.type != "image":
            hint_parts.append("Images only in this build.")

        hint = QLabel(" ".join(hint_parts))
        hint.setObjectName("EmptyHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._status = QLabel("Cached cutout ready." if media and media.remove_bg_path else "")
        self._status.setObjectName("EmptyHint")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    def _on_toggle(self, checked: bool) -> None:
        if not self._media or self._media.type != "image":
            return
        if checked and not self._media.remove_bg_path:
            self._status.setText("Processing…")
            self._worker = _RemoveBgWorker(self._media.path)
            self._worker.setParent(self)
            self._worker.finished.connect(self._on_worker_finished)
            self._worker.finished.connect(self._worker.deleteLater)
            self._worker.start()
            return
        self._on_change(remove_bg_enabled=checked)

    def _on_worker_finished(self, output_path: str, message: str) -> None:
        try:
            import shiboken6

            if not shiboken6.isValid(self):
                return
        except RuntimeError:
            return
        self._status.setText(message)
        if output_path and self._media is not None:
            clear_image_cache()
            self._on_media_path(self._media.id, output_path)
            self._on_change(remove_bg_enabled=True)
        else:
            self._toggle.blockSignals(True)
            self._toggle.setChecked(False)
            self._toggle.blockSignals(False)


class MaskSettingsPanel(QWidget):
    _SHAPES: tuple[tuple[str, str, str], ...] = (
        ("split", "Split", "mask-split"),
        ("filmstrip", "Filmstrip", "mask-filmstrip"),
        ("circle", "Circle", "mask-circle"),
        ("rectangle", "Rectangle", "mask-rectangle"),
        ("stars", "Stars", "mask-star"),
        ("heart", "Heart", "mask-heart"),
        ("text", "Text", "type"),
        ("brush", "Brush", "mask-brush"),
        ("pen", "Pen", "mask-pen"),
    )

    _DEFAULTS: dict[str, float | bool | str] = {
        "mask_enabled": True,
        "mask_shape": "rectangle",
        "mask_x": 0.5,
        "mask_y": 0.5,
        "mask_width": 1.0,
        "mask_height": 1.0,
        "mask_rotation": 0.0,
        "mask_feather": 0.0,
        "mask_round_corners": 0.0,
        "mask_invert": False,
    }

    def __init__(
        self,
        clip: Clip,
        project_state: ProjectState,
        on_preview: Callable[..., None],
        on_change: Callable[..., None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._clip_id = clip.id
        self._state = project_state
        self._on_preview = on_preview
        self._on_change = on_change
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._slider_headers: dict[str, QLabel] = {}
        self._sliders: dict[str, _NoScrollSlider] = {}
        layout = QVBoxLayout(self)
        apply_page_layout(layout)

        enable_row = QHBoxLayout()
        enable_row.setContentsMargins(0, 0, 0, 0)
        enable_row.setSpacing(FIELD_GAP)
        self._enable = QCheckBox("Mask")
        self._enable.setObjectName("InspectorSectionCheck")
        self._enable.setChecked(clip.mask_enabled)
        self._enable.toggled.connect(self._on_mask_enabled)
        enable_row.addWidget(self._enable)
        invert_btn = QPushButton("Invert")
        invert_btn.setObjectName("InspectorGhostButton")
        invert_btn.clicked.connect(self._toggle_invert)
        reset_btn = QPushButton("Reset")
        reset_btn.setObjectName("InspectorGhostButton")
        reset_btn.clicked.connect(self._reset_mask)
        enable_row.addWidget(invert_btn)
        enable_row.addWidget(reset_btn)
        enable_row.addStretch(1)
        layout.addLayout(enable_row)

        add_section_spacer(layout)
        shape_label = QLabel("Shape")
        shape_label.setObjectName("FieldLabel")
        layout.addWidget(shape_label)
        layout.addSpacing(FIELD_GAP)
        shape_grid = QGridLayout()
        configure_shape_grid(shape_grid)
        self._shape_buttons: dict[str, _MaskShapeButton] = {}
        for index, (shape_id, label, icon_name) in enumerate(self._SHAPES):
            btn = _MaskShapeButton(icon_name, label)
            btn.setChecked(clip.mask_shape == shape_id)
            btn.clicked.connect(lambda _c, sid=shape_id: self._select_shape(sid))
            if shape_id in ("text", "brush", "pen"):
                btn.setEnabled(False)
                btn.setToolTip("Coming soon")
            shape_grid.addWidget(btn, index // 3, index % 3)
            self._shape_buttons[shape_id] = btn
        layout.addLayout(shape_grid)

        add_section_spacer(layout)
        layout.addWidget(self._section_label("Mask settings"))
        layout.addSpacing(FIELD_GAP)
        for spin_layout in (
            self._spin_row("Position X", clip.mask_x, 0.0, 1.0, "mask_x"),
            self._spin_row("Position Y", clip.mask_y, 0.0, 1.0, "mask_y"),
            self._spin_row("Rotation", clip.mask_rotation, -180.0, 180.0, "mask_rotation", suffix="°"),
            self._spin_row("Width", clip.mask_width, 0.05, 2.0, "mask_width", step=0.01),
            self._spin_row("Height", clip.mask_height, 0.05, 2.0, "mask_height", step=0.01),
        ):
            layout.addLayout(spin_layout)
            layout.addSpacing(FIELD_ROW_GAP)

        layout.addSpacing(SLIDER_BLOCK_GAP - FIELD_ROW_GAP)
        layout.addLayout(self._slider_row("Feather", clip.mask_feather, 0, 100, "mask_feather"))
        layout.addSpacing(SLIDER_BLOCK_GAP)
        layout.addLayout(
            self._slider_row("Round corners", clip.mask_round_corners, 0, 100, "mask_round_corners")
        )

        add_section_spacer(layout)
        track_label = QLabel("Track mask — coming soon")
        track_label.setObjectName("EmptyHint")
        layout.addWidget(track_label)
        layout.addStretch(1)

    def _live_clip(self) -> Clip | None:
        ref = self._state.get_clip(self._clip_id)
        return ref[1] if ref else None

    def _on_mask_enabled(self, enabled: bool) -> None:
        self._on_change(mask_enabled=enabled)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _toggle_invert(self) -> None:
        clip = self._live_clip()
        if clip is None:
            return
        self._on_change(mask_invert=not clip.mask_invert)

    def _select_shape(self, shape_id: str) -> None:
        for sid, btn in self._shape_buttons.items():
            btn.setChecked(sid == shape_id)
        if not self._enable.isChecked():
            self._enable.blockSignals(True)
            self._enable.setChecked(True)
            self._enable.blockSignals(False)
        self._on_change(mask_enabled=True, mask_shape=shape_id)

    def _reset_mask(self) -> None:
        fields = dict(self._DEFAULTS)
        self._apply_fields_to_widgets(fields)
        self._on_change(**fields)

    def _apply_fields_to_widgets(self, fields: dict[str, float | bool | str]) -> None:
        if "mask_enabled" in fields:
            self._enable.blockSignals(True)
            self._enable.setChecked(bool(fields["mask_enabled"]))
            self._enable.blockSignals(False)
        if "mask_shape" in fields:
            shape = str(fields["mask_shape"])
            for sid, btn in self._shape_buttons.items():
                btn.setChecked(sid == shape)
        for key, spin in self._spins.items():
            if key in fields:
                spin.blockSignals(True)
                spin.setValue(float(fields[key]))  # type: ignore[arg-type]
                spin.blockSignals(False)
        for key, slider in self._sliders.items():
            if key in fields:
                value = int(float(fields[key]))  # type: ignore[arg-type]
                slider.blockSignals(True)
                slider.setValue(value)
                slider.blockSignals(False)
                header = self._slider_headers.get(key)
                if header is not None:
                    title = header.text().split("   ")[0]
                    header.setText(f"{title}   {value}")

    def _spin_row(
        self,
        title: str,
        value: float,
        minimum: float,
        maximum: float,
        field: str,
        *,
        step: float = 0.01,
        suffix: str = "",
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        configure_field_row(row)
        label = QLabel(title)
        label.setObjectName("FieldLabel")
        label.setMinimumWidth(SPIN_LABEL_WIDTH)
        row.addWidget(label)
        row.addStretch(1)
        spin = _NoScrollDoubleSpinBox()
        spin.setObjectName("InspectorValueSpin")
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(2 if step < 1 else 1)
        spin.setValue(float(value))
        spin.setFixedWidth(SPIN_INPUT_WIDTH)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        if suffix:
            spin.setSuffix(suffix)
        spin.valueChanged.connect(lambda v, f=field: self._on_preview(**{f: v}))
        spin.editingFinished.connect(lambda f=field, s=spin: self._on_change(**{f: s.value()}))
        row.addWidget(spin)
        self._spins[field] = spin
        return row

    def _slider_row(
        self, title: str, value: float, minimum: int, maximum: int, field: str
    ) -> QVBoxLayout:
        col = QVBoxLayout()
        configure_slider_column(col)
        header = QLabel(f"{title}   {int(value)}")
        header.setObjectName("FieldLabel")
        slider = _NoScrollSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(int(value))

        def _preview(pos: int) -> None:
            header.setText(f"{title}   {pos}")
            self._on_preview(**{field: float(pos)})

        def _commit() -> None:
            self._on_change(**{field: float(slider.value())})

        slider.valueChanged.connect(_preview)
        slider.sliderReleased.connect(_commit)
        col.addWidget(header)
        col.addWidget(slider)
        self._slider_headers[field] = header
        self._sliders[field] = slider
        return col
