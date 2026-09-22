"""Right inspector panel — dynamic per-selection property form.

Port of the reference app's `renderInspector()`. Universal fields (opacity,
volume, fade in/out, duplicate/delete) plus filter swatches, text fields,
and the visualizer picker are all built here since they're all driven by
the same small metadata registries (`core/registries.py`) — later phases
(filters/text-overlays/visualizer) implement the actual pixel/paint logic
behind these ids, not new UI.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.core.models import Clip, Track
from studio.core.project_state import ProjectState
from studio.core.registries import FILTERS, VIZ_STYLES
from studio.render.compositor import DEFAULT_HEIGHT, DEFAULT_WIDTH
from studio.ui.clip_inspector_controls import AlignmentToolbar, ImageFitModeRow, MaskSettingsPanel, RemoveBgSection
from studio.ui.animation_preset_grid import AnimationPresetGrid
from studio.ui.clip_inspector_tabs import InspectorTabRow
from studio.ui.inspector_layout import (
    FIELD_GAP,
    FIELD_ROW_GAP,
    HEADER_SUBTITLE_GAP,
    SECTION_GAP,
    SLIDER_BLOCK_GAP,
    TAB_TIER_GAP,
    add_section_spacer,
    apply_page_layout,
)


logger = logging.getLogger(__name__)


def _field_label(text: str, value_text: str = "") -> QLabel:
    label = QLabel(f"{text}" + (f"   {value_text}" if value_text else ""))
    label.setObjectName("FieldLabel")
    return label


class _ClipTextEdit(QTextEdit):
    """A QTextEdit that reports when it loses focus — mirrors `SliderField`'s
    "commit on release" pattern so typing a title/caption commits once when
    the user is done, not once per keystroke (see `InspectorPanel._on_text_edited`
    for why: committing on every keystroke used to push one undo step per
    character AND rebuild this whole panel — including this very widget —
    out from under the user's cursor)."""

    focus_lost = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.focus_lost.emit()


class _NoScrollSlider(QSlider):
    """Pass wheel events to the parent scroll area — avoids laggy accidental slider drags."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class SliderField(QWidget):
    """A label + slider row that maps an int slider range to a float value."""

    value_committed = Signal(float)
    value_preview = Signal(float)

    def __init__(
        self,
        title: str,
        minimum: float,
        maximum: float,
        value: float,
        step: float = 1.0,
        suffix: str = "",
        decimals: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = minimum
        self._step = step
        self._suffix = suffix
        self._decimals = decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(FIELD_ROW_GAP)

        self.title = title
        self.label = QLabel()
        self.label.setObjectName("FieldLabel")
        layout.addWidget(self.label)

        self.slider = _NoScrollSlider(Qt.Orientation.Horizontal)
        steps = max(1, int(round((maximum - minimum) / step)))
        self.slider.setRange(0, steps)
        self.slider.setValue(self._to_slider(value))
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.sliderReleased.connect(self._on_released)
        layout.addWidget(self.slider)

        self._value = value
        self._update_label()

    def _to_slider(self, value: float) -> int:
        return int(round((value - self._minimum) / self._step))

    def _from_slider(self, pos: int) -> float:
        return self._minimum + pos * self._step

    def _on_slider_changed(self, pos: int) -> None:
        self._value = self._from_slider(pos)
        self._update_label()
        self.value_preview.emit(self._value)

    def _on_released(self) -> None:
        self.value_committed.emit(self._value)

    def _update_label(self) -> None:
        if self._decimals == 0:
            text = f"{self._value:.0f}{self._suffix}"
        else:
            text = f"{self._value:.{self._decimals}f}{self._suffix}"
        self.label.setText(f"{self.title}   {text}")

    def value(self) -> float:
        return self._value

    def set_value(self, value: float, *, block_signals: bool = True) -> None:
        """Update slider + label without emitting preview/change signals."""
        self._value = value
        self.slider.blockSignals(block_signals)
        self.slider.setValue(self._to_slider(value))
        self.slider.blockSignals(False)
        self._update_label()


class FilterSwatchGrid(QWidget):
    filter_selected = Signal(str)

    def __init__(self, active_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_id = active_id
        self._buttons: dict[str, QPushButton] = {}
        self._swatches: dict[str, tuple[str, str]] = {}
        grid = QGridLayout(self)
        grid.setSpacing(6)
        for i, info in enumerate(FILTERS):
            btn = QPushButton(info.name)
            btn.setCheckable(True)
            btn.setChecked(info.id == active_id)
            btn.setFixedHeight(38)
            self._apply_btn_style(btn, info.id == active_id, info.swatch_from, info.swatch_to)
            btn.clicked.connect(lambda _checked, fid=info.id: self.filter_selected.emit(fid))
            grid.addWidget(btn, i // 4, i % 4)
            self._buttons[info.id] = btn
            self._swatches[info.id] = (info.swatch_from, info.swatch_to)

    @staticmethod
    def _apply_btn_style(btn: QPushButton, active: bool, swatch_from: str, swatch_to: str) -> None:
        border = "#7c5cff" if active else "transparent"
        btn.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 {swatch_from}, stop:1 {swatch_to}); color: white;"
            f" font-size: 9px; border-radius: 8px; border: 2px solid {border}; }}"
        )

    def set_active(self, filter_id: str) -> None:
        self._active_id = filter_id
        for fid, btn in self._buttons.items():
            btn.setChecked(fid == filter_id)
            sw_from, sw_to = self._swatches[fid]
            self._apply_btn_style(btn, fid == filter_id, sw_from, sw_to)


class VizStyleGrid(QWidget):
    viz_selected = Signal(str)

    def __init__(self, active_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_id = active_id
        self._buttons: dict[str, QPushButton] = {}
        self._swatches: dict[str, tuple[str, str]] = {}
        grid = QGridLayout(self)
        grid.setSpacing(6)
        for i, info in enumerate(VIZ_STYLES):
            btn = QPushButton(info.name)
            btn.setCheckable(True)
            btn.setFixedHeight(38)
            self._apply_btn_style(btn, info.id == active_id, info.swatch_from, info.swatch_to)
            btn.clicked.connect(lambda _checked, vid=info.id: self.viz_selected.emit(vid))
            btn.blockSignals(True)
            btn.setChecked(info.id == active_id)
            btn.blockSignals(False)
            grid.addWidget(btn, i // 2, i % 2)
            self._buttons[info.id] = btn
            self._swatches[info.id] = (info.swatch_from, info.swatch_to)

    @staticmethod
    def _apply_btn_style(btn: QPushButton, active: bool, swatch_from: str, swatch_to: str) -> None:
        border = "#7c5cff" if active else "transparent"
        btn.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 {swatch_from}, stop:1 {swatch_to}); color: white;"
            f" font-size: 9px; border-radius: 8px; border: 2px solid {border}; }}"
        )

    def set_active(self, viz_id: str) -> None:
        self._active_id = viz_id
        for vid, btn in self._buttons.items():
            btn.blockSignals(True)
            btn.setChecked(vid == viz_id)
            btn.blockSignals(False)
            sw_from, sw_to = self._swatches[vid]
            self._apply_btn_style(btn, vid == viz_id, sw_from, sw_to)


class InspectorPanel(QWidget):
    changed = Signal()  # structural / undo-worthy edit
    preview_changed = Signal()  # live transform preview — no timeline rebuild

    def __init__(self, project_state: ProjectState | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._pending_text_edit: tuple[str, str] | None = None
        self._filter_grid: FilterSwatchGrid | None = None
        self._viz_grid: VizStyleGrid | None = None
        self._clip_tier1_index = 0
        self._clip_tier2_index = 0
        self._clip_anim_tier_index = 0
        self._tier1_row: InspectorTabRow | None = None
        self._tier2_row: InspectorTabRow | None = None
        self._anim_grid: AnimationPresetGrid | None = None
        self._scale_field: SliderField | None = None
        self._pos_x_field: SliderField | None = None
        self._pos_y_field: SliderField | None = None
        self.refresh()

    def set_project_state(self, project_state: ProjectState) -> None:
        self.project_state = project_state
        self.refresh()

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _clear(self) -> None:
        self._commit_pending_text_edit()
        self._filter_grid = None
        self._viz_grid = None
        self._anim_grid = None
        self._tier1_row = None
        self._tier2_row = None
        self._scale_field = None
        self._pos_x_field = None
        self._pos_y_field = None
        self._clear_layout(self._layout)

    def refresh(self) -> None:
        if self._tier1_row is not None:
            self._clip_tier1_index = self._tier1_row.active_index()
        if self._tier2_row is not None:
            self._clip_tier2_index = self._tier2_row.active_index()
        if self._anim_grid is not None:
            self._clip_anim_tier_index = self._anim_grid.active_tab_index()
        self._clear()
        ref = self.project_state.get_clip(self.project_state.selected_clip_id) if self.project_state else None
        if ref is None:
            self._build_project_details()
        else:
            track, clip = ref
            self._build_for_clip(track, clip)

    def _details_row(self, label: str, value: str) -> None:
        row = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("FieldLabel")
        val = QLabel(value)
        val.setObjectName("DetailsFieldValue")
        val.setWordWrap(True)
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(name, 1)
        row.addWidget(val, 2)
        self._layout.addLayout(row)

    def _build_project_details(self) -> None:
        """CapCut-style Details panel when nothing is selected on the timeline."""
        project = self.project_state.project if self.project_state else None
        title = QLabel("Details")
        title.setObjectName("DetailsSectionTitle")
        self._layout.addWidget(title)

        if project is None:
            self._layout.addStretch(1)
            return

        fps = project.snap_settings.frame_rate or 30.0
        self._details_row("Timeline name", project.name)
        self._details_row("Aspect ratio", "16:9")
        self._details_row("Resolution", f"{DEFAULT_WIDTH}\u00d7{DEFAULT_HEIGHT}")
        self._details_row("Frame rate", f"{fps:.2f} fps")
        self._details_row("Duration", f"{project.duration:.2f}s")
        self._details_row("Tracks", str(len(project.tracks)))
        self._details_row("Media items", str(len(project.media_library)))

        hint = QLabel("Select a clip on the timeline to edit its properties.")
        hint.setObjectName("EmptyHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addSpacing(12)
        self._layout.addWidget(hint)
        self._layout.addStretch(1)

    def _build_for_clip(self, track: Track, clip: Clip) -> None:
        state = self.project_state
        assert state is not None

        if clip.kind == "playlist":
            title = QLabel("Playlist card")
            title.setObjectName("InspTitle")
            hint = QLabel(
                "This clip is auto-managed from your playlist template. "
                "Edit styles in Playlist → Settings, or click this clip again "
                "to jump there."
            )
            hint.setObjectName("EmptyHint")
            hint.setWordWrap(True)
            self._layout.addWidget(title)
            self._layout.addWidget(hint)
            self._layout.addStretch(1)
            return

        if clip.kind in ("image", "video"):
            self._build_visual_clip_inspector(track, clip)
            return

        title = QLabel("Text Clip" if clip.kind == "text" else clip.label)
        title.setObjectName("InspTitle")
        title.setWordWrap(True)

        sub = QLabel(f"{track.type.upper()} \u00b7 {clip.duration:.2f}s")
        sub.setObjectName("InspSub")

        header = QWidget(self)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(HEADER_SUBTITLE_GAP)
        header_layout.addWidget(title)
        header_layout.addWidget(sub)
        self._layout.addWidget(header)
        self._layout.addSpacing(SECTION_GAP)

        if clip.kind == "text":
            self._build_text_clip_fields(clip)
        if track.type == "video" or clip.kind == "image":
            self._add_filter_section(clip)
        if track.type in ("video", "audio"):
            self._add_volume_field(clip)
        self._add_opacity_and_fade(clip)
        if track.type == "audio":
            self._add_audio_viz_section(clip)
        self._add_clip_actions(clip)
        self._layout.addStretch(1)

    def _build_visual_clip_inspector(self, track: Track, clip: Clip) -> None:
        state = self.project_state
        assert state is not None

        tier1 = InspectorTabRow(("Video", "Animation", "Retouch"), self)
        self._tier1_row = tier1

        tier2 = InspectorTabRow(("Basic", "Mask"), self)
        tier2.setObjectName("InspectorTier2TabRow")
        self._tier2_row = tier2

        tabs_wrap = QWidget(self)
        tabs_layout = QVBoxLayout(tabs_wrap)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(TAB_TIER_GAP)
        tabs_layout.addWidget(tier1)
        tabs_layout.addWidget(tier2)
        self._layout.addWidget(tabs_wrap)
        self._layout.addSpacing(SECTION_GAP)

        stack = QStackedWidget(self)

        basic_page = QWidget(stack)
        basic_layout = QVBoxLayout(basic_page)
        apply_page_layout(basic_layout)

        clip_id = clip.id

        def preview_cb(**fields):
            self._on_preview(clip_id, **fields)

        def change_cb(**fields):
            self._on_change(clip_id, **fields)

        def preview_for(cid: str):
            return lambda **fields: self._on_preview(cid, **fields)

        def change_for(cid: str):
            return lambda **fields: self._on_change(cid, **fields)

        basic_layout.addWidget(_field_label("Align"))
        basic_layout.addSpacing(FIELD_GAP)
        basic_layout.addWidget(
            AlignmentToolbar(
                state,
                clip,
                preview_cb,
                change_cb,
                on_preview_for=preview_for,
                on_change_for=change_for,
            )
        )

        if clip.kind == "image":
            add_section_spacer(basic_layout)
            basic_layout.addWidget(_field_label("Canvas fit"))
            basic_layout.addSpacing(FIELD_GAP)
            basic_layout.addWidget(ImageFitModeRow(clip, preview_cb, change_cb))

        media = state.get_media(clip.media_id)

        def _on_remove_bg_path(media_id: str, path: str) -> None:
            state.update_media(media_id, remove_bg_path=path)

        add_section_spacer(basic_layout)
        basic_layout.addWidget(
            RemoveBgSection(clip, media, preview_cb, change_cb, _on_remove_bg_path)
        )

        add_section_spacer(basic_layout)
        self._add_transform_fields(basic_layout, clip)
        if track.type == "video":
            self._add_volume_field_to(clip, basic_layout)
        self._add_opacity_and_fade_to(clip, basic_layout)
        self._add_clip_actions_to(clip, basic_layout)
        basic_layout.addStretch(1)

        mask_page = MaskSettingsPanel(clip, state, preview_cb, change_cb, stack)
        self._anim_grid = AnimationPresetGrid(
            for_image=clip.kind == "image",
            initial_tab=self._clip_anim_tier_index,
            parent=stack,
        )
        anim_page = self._anim_grid
        retouch_page = QWidget(stack)
        retouch_layout = QVBoxLayout(retouch_page)
        apply_page_layout(retouch_layout)
        self._add_filter_section_to(clip, retouch_layout)
        retouch_layout.addStretch(1)

        stack.addWidget(basic_page)
        stack.addWidget(mask_page)
        stack.addWidget(anim_page)
        stack.addWidget(retouch_page)
        self._layout.addWidget(stack, 1)

        tier2_index = [self._clip_tier2_index]

        def _show_video_sub(index: int) -> None:
            tier2_index[0] = index
            self._clip_tier2_index = index
            stack.setCurrentIndex(0 if index == 0 else 1)

        def _show_tier1(index: int) -> None:
            self._clip_tier1_index = index
            if index == 0:
                tier2.show()
                _show_video_sub(tier2_index[0])
            elif index == 1:
                tier2.hide()
                stack.setCurrentIndex(2)
            else:
                tier2.hide()
                stack.setCurrentIndex(3)

        tier1.tab_changed.connect(_show_tier1)
        tier2.tab_changed.connect(_show_video_sub)
        tier1.set_active_index(self._clip_tier1_index)
        tier2.set_active_index(self._clip_tier2_index)
        _show_tier1(self._clip_tier1_index)

    def _build_text_clip_fields(self, clip: Clip) -> None:
        self._layout.addWidget(_field_label("Text"))
        text_edit = _ClipTextEdit()
        text_edit.setPlainText(clip.text or "")
        text_edit.setFixedHeight(54)
        text_edit.textChanged.connect(lambda: self._on_text_edited(clip.id, text_edit))
        text_edit.focus_lost.connect(self._commit_pending_text_edit)
        self._layout.addWidget(text_edit)

        color_row = QHBoxLayout()
        color_btn = QPushButton()
        color_btn.setFixedSize(28, 28)
        color_btn.setStyleSheet(f"background: {clip.color or '#ffffff'}; border-radius: 6px;")
        color_btn.clicked.connect(lambda: self._pick_color(clip))
        color_row.addWidget(_field_label("Color"))
        color_row.addWidget(color_btn)
        color_row.addStretch(1)
        self._layout.addLayout(color_row)

        size_field = SliderField("Size", 12, 120, float(clip.size or 40), step=1, suffix="px")
        size_field.value_committed.connect(lambda v: self._on_change(clip.id, size=v))
        self._layout.addWidget(size_field)

        x_field = SliderField("Position X", 0, 100, (clip.x or 0.5) * 100, step=1, suffix="%")
        x_field.value_committed.connect(lambda v: self._on_change(clip.id, x=v / 100.0))
        self._layout.addWidget(x_field)

        y_field = SliderField("Position Y", 0, 100, (clip.y or 0.5) * 100, step=1, suffix="%")
        y_field.value_committed.connect(lambda v: self._on_change(clip.id, y=v / 100.0))
        self._layout.addWidget(y_field)

    def _add_filter_section(self, clip: Clip) -> None:
        self._add_filter_section_to(clip, self._layout)

    def _add_filter_section_to(self, clip: Clip, layout) -> None:
        layout.addWidget(_field_label("Filter"))
        self._filter_grid = FilterSwatchGrid(clip.filter, self)
        self._filter_grid.filter_selected.connect(lambda fid: self._on_change(clip.id, filter=fid))
        layout.addWidget(self._filter_grid)

    def _add_transform_fields(self, layout, clip: Clip) -> None:
        layout.addWidget(_field_label("Transform"))
        layout.addSpacing(FIELD_GAP)
        scale_field = SliderField(
            "Scale", 10, 300, float(clip.transform_scale or 1.0) * 100, step=1, suffix="%"
        )
        self._scale_field = scale_field
        scale_field.value_preview.connect(
            lambda v, cid=clip.id: self._on_preview(cid, transform_scale=v / 100.0)
        )
        scale_field.value_committed.connect(
            lambda v, cid=clip.id: self._on_change(cid, transform_scale=v / 100.0)
        )
        layout.addWidget(scale_field)
        layout.addSpacing(SLIDER_BLOCK_GAP)

        pos_x = SliderField(
            "Position X",
            0,
            100,
            float(clip.transform_x if clip.transform_x is not None else 0.5) * 100,
            step=1,
            suffix="%",
        )
        self._pos_x_field = pos_x
        pos_x.value_preview.connect(lambda v, cid=clip.id: self._on_preview(cid, transform_x=v / 100.0))
        pos_x.value_committed.connect(lambda v, cid=clip.id: self._on_change(cid, transform_x=v / 100.0))
        layout.addWidget(pos_x)
        layout.addSpacing(SLIDER_BLOCK_GAP)

        pos_y = SliderField(
            "Position Y",
            0,
            100,
            float(clip.transform_y if clip.transform_y is not None else 0.5) * 100,
            step=1,
            suffix="%",
        )
        self._pos_y_field = pos_y
        pos_y.value_preview.connect(lambda v, cid=clip.id: self._on_preview(cid, transform_y=v / 100.0))
        pos_y.value_committed.connect(lambda v, cid=clip.id: self._on_change(cid, transform_y=v / 100.0))
        layout.addWidget(pos_y)
        layout.addSpacing(SLIDER_BLOCK_GAP)

        crop_field = SliderField("Crop", 0, 40, float(clip.crop_inset or 0.0) * 100, step=1, suffix="%")
        crop_field.value_preview.connect(lambda v, cid=clip.id: self._on_preview(cid, crop_inset=v / 100.0))
        crop_field.value_committed.connect(lambda v, cid=clip.id: self._on_change(cid, crop_inset=v / 100.0))
        layout.addWidget(crop_field)

        hint = QLabel("Tip: drag the clip in the preview to move or scale.")
        hint.setObjectName("EmptyHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _add_volume_field(self, clip: Clip) -> None:
        self._add_volume_field_to(clip, self._layout)

    def _add_volume_field_to(self, clip: Clip, layout) -> None:
        volume_field = SliderField("Volume", 0, 150, clip.volume * 100, step=1, suffix="%")
        volume_field.value_committed.connect(lambda v: self._on_change(clip.id, volume=v / 100.0))
        layout.addWidget(volume_field)

    def _add_opacity_and_fade(self, clip: Clip) -> None:
        self._add_opacity_and_fade_to(clip, self._layout)

    def _add_opacity_and_fade_to(self, clip: Clip, layout) -> None:
        opacity_field = SliderField("Opacity", 0, 100, clip.opacity * 100, step=1, suffix="%")
        opacity_field.value_committed.connect(lambda v: self._on_change(clip.id, opacity=v / 100.0))
        layout.addWidget(opacity_field)

        fade_row = QHBoxLayout()
        fade_in_field = SliderField("Fade in", 0, 3, clip.fade_in, step=0.1, suffix="s", decimals=1)
        fade_in_field.value_committed.connect(lambda v: self._on_change(clip.id, fade_in=v))
        fade_out_field = SliderField("Fade out", 0, 3, clip.fade_out, step=0.1, suffix="s", decimals=1)
        fade_out_field.value_committed.connect(lambda v: self._on_change(clip.id, fade_out=v))
        fade_row.addWidget(fade_in_field)
        fade_row.addWidget(fade_out_field)
        layout.addLayout(fade_row)

    def _add_audio_viz_section(self, clip: Clip) -> None:
        self._layout.addWidget(_field_label("Music Visualizer"))
        viz_row = QHBoxLayout()
        viz_checkbox = QCheckBox("Show on video preview")
        viz_checkbox.blockSignals(True)
        viz_checkbox.setChecked(clip.viz_enabled)
        viz_checkbox.blockSignals(False)
        viz_checkbox.toggled.connect(lambda checked: self._on_change(clip.id, viz_enabled=checked))
        viz_row.addWidget(viz_checkbox)
        self._layout.addLayout(viz_row)
        self._viz_grid = VizStyleGrid(clip.viz)
        self._viz_grid.viz_selected.connect(lambda vid: self._on_change(clip.id, viz=vid))
        self._layout.addWidget(self._viz_grid)

    def _add_clip_actions(self, clip: Clip) -> None:
        self._add_clip_actions_to(clip, self._layout)

    def _add_clip_actions_to(self, clip: Clip, layout) -> None:
        actions = QHBoxLayout()
        dup_btn = QPushButton("\u2398 Duplicate")
        dup_btn.clicked.connect(lambda: self._duplicate(clip.id))
        del_btn = QPushButton("\U0001f5d1 Delete")
        del_btn.setObjectName("DangerButton")
        del_btn.clicked.connect(lambda: self._delete(clip.id))
        actions.addWidget(dup_btn)
        actions.addWidget(del_btn)
        layout.addLayout(actions)

    def _pick_color(self, clip: Clip) -> None:
        color = QColorDialog.getColor(QColor(clip.color or "#ffffff"), self, "Text color")
        if color.isValid():
            self._on_change(clip.id, color=color.name())

    def _on_preview(self, clip_id: str, **fields) -> None:
        if self.project_state is None:
            return
        logger.debug("inspector preview clip=%s fields=%s", clip_id, fields)
        self.project_state.update_clip(clip_id, record_undo=False, **fields)
        self.preview_changed.emit()

    def _on_change(self, clip_id: str, **fields) -> None:
        if self.project_state is None:
            return
        logger.info("inspector change clip=%s fields=%s", clip_id, fields)
        self.project_state.update_clip(clip_id, **fields)
        if "filter" in fields and self._filter_grid is not None:
            self._filter_grid.set_active(str(fields["filter"]))
            self.preview_changed.emit()
        elif "viz" in fields and self._viz_grid is not None:
            self._viz_grid.set_active(str(fields["viz"]))
            self.preview_changed.emit()
        elif "viz_enabled" in fields:
            self.preview_changed.emit()
        elif fields.keys() & {"opacity", "fade_in", "fade_out", "volume"}:
            self.preview_changed.emit()
        elif fields.keys() & {
            "mask_enabled",
            "mask_shape",
            "mask_invert",
            "remove_bg_enabled",
            "fit_mode",
            "transform_scale",
            "transform_x",
            "transform_y",
        }:
            self._sync_transform_sliders(**fields)
            self.preview_changed.emit()
        self.changed.emit()

    def _sync_transform_sliders(self, **fields) -> None:
        if self._scale_field is not None and "transform_scale" in fields:
            self._scale_field.set_value(float(fields["transform_scale"]) * 100)
        if self._pos_x_field is not None and "transform_x" in fields:
            self._pos_x_field.set_value(float(fields["transform_x"]) * 100)
        if self._pos_y_field is not None and "transform_y" in fields:
            self._pos_y_field.set_value(float(fields["transform_y"]) * 100)

    def _on_text_edited(self, clip_id: str, text_edit: QTextEdit) -> None:
        """Lightweight per-keystroke bookkeeping only — no undo push, no
        panel rebuild. The actual commit happens once, in
        `_commit_pending_text_edit`, when the field loses focus (or the
        panel is about to be rebuilt for any other reason)."""
        self._pending_text_edit = (clip_id, text_edit.toPlainText())

    def _commit_pending_text_edit(self) -> None:
        if self._pending_text_edit is None:
            return
        clip_id, text = self._pending_text_edit
        self._pending_text_edit = None
        if self.project_state is not None and self.project_state.get_clip(clip_id) is not None:
            self.project_state.update_clip(clip_id, text=text)
            self.changed.emit()

    def _duplicate(self, clip_id: str) -> None:
        if self.project_state is None:
            return
        self.project_state.duplicate_clip(clip_id)
        self.refresh()
        self.changed.emit()

    def _delete(self, clip_id: str) -> None:
        if self.project_state is None:
            return
        self.project_state.delete_clip(clip_id)
        self.refresh()
        self.changed.emit()
