"""Studio shell — Video-style left / stage / right workspace."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from features.studio.widgets.asset_browser_dialog import AssetBrowserDialog
from features.studio.widgets.left_rail import StudioLeftRail
from features.studio.widgets.preview_stage import StudioPreviewStage
from features.studio.widgets.right_rail import StudioRightRail
from features.studio.widgets.stage_panel import StudioStagePanel

# Narrower than Video — Studio center needs preview + tracks + export.
STUDIO_LEFT_RAIL_WIDTH = 300
STUDIO_RIGHT_RAIL_WIDTH = 360


class StudioShell(QWidget):
    new_requested = Signal()
    save_requested = Signal()
    undo_requested = Signal()
    project_selected = Signal(str)
    name_changed = Signal(str)
    patch_requested = Signal(dict)
    export_json_requested = Signal()
    export_video_requested = Signal()
    select_audio_requested = Signal()
    add_tracks_requested = Signal()
    track_selected = Signal(str)
    remove_track_requested = Signal(str)
    template_save_requested = Signal()
    ai_generate_requested = Signal(str)
    ai_modify_requested = Signal(str)
    ai_improve_requested = Signal()
    json_apply_requested = Signal(dict)
    timeline_play_toggled = Signal(bool)
    timeline_stop_requested = Signal()
    timeline_seek_requested = Signal(float)
    timeline_seek_relative_requested = Signal(float)
    favorite_toggled = Signal(str, bool)
    node_selected = Signal(str)
    export_options_changed = Signal(dict)
    spectrum_position_changed = Signal(int, int)
    logo_position_changed = Signal(int, int)
    spectrum_size_delta_requested = Signal(float)
    spectrum_layer_patch_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)

        self._left = StudioLeftRail()
        self._left.name_changed.connect(self.name_changed.emit)
        self._left.project_selected.connect(self.project_selected.emit)
        self._left.new_requested.connect(self.new_requested.emit)
        self._left.save_requested.connect(self.save_requested.emit)
        self._left.undo_requested.connect(self.undo_requested.emit)
        self._left.template_save_requested.connect(self.template_save_requested.emit)
        self._left.node_selected.connect(self._on_node)
        self._left.ai_generate_requested.connect(self.ai_generate_requested.emit)
        self._left.ai_modify_requested.connect(self.ai_modify_requested.emit)
        self._left.ai_improve_requested.connect(self.ai_improve_requested.emit)
        self._fix_rail(self._left, STUDIO_LEFT_RAIL_WIDTH)
        content.addWidget(self._left, stretch=0)

        self._stage = StudioStagePanel()
        self._stage.play_toggled.connect(self.timeline_play_toggled.emit)
        self._stage.stop_requested.connect(self.timeline_stop_requested.emit)
        self._stage.seek_requested.connect(self.timeline_seek_requested.emit)
        self._stage.seek_relative_requested.connect(self.timeline_seek_relative_requested.emit)
        self._stage.track_selected.connect(self.track_selected.emit)
        self._stage.add_tracks_requested.connect(self.add_tracks_requested.emit)
        self._stage.remove_track_requested.connect(self.remove_track_requested.emit)
        self._stage.export_json_requested.connect(self.export_json_requested.emit)
        self._stage.export_video_requested.connect(self.export_video_requested.emit)
        self._stage.export_options_changed.connect(self.export_options_changed.emit)
        self._stage.browse_assets_requested.connect(self._open_asset_browser)
        self._stage.spectrum_position_changed.connect(self.spectrum_position_changed.emit)
        self._stage.logo_position_changed.connect(self.logo_position_changed.emit)
        self._stage.spectrum_size_delta_requested.connect(self.spectrum_size_delta_requested.emit)
        self._stage.spectrum_layer_patch_changed.connect(self.spectrum_layer_patch_changed.emit)
        content.addWidget(self._stage, stretch=1)

        self._right = StudioRightRail()
        self._right.patch_requested.connect(self.patch_requested.emit)
        self._right.json_apply_requested.connect(self.json_apply_requested.emit)
        self._fix_rail(self._right, STUDIO_RIGHT_RAIL_WIDTH)
        content.addWidget(self._right, stretch=0)

        root.addLayout(content, stretch=1)

        self._asset_dialog: AssetBrowserDialog | None = None

        # Compat aliases used by older tests / call sites.
        self._inspector = self._right._inspector
        self._export_panel = self._stage.export_panel()
        self._timeline = self._stage
        self._tracks = self._stage._tracks
        self._side_tabs = self._right._tabs
        self._preview = self._stage.preview()

        # Sync initial scene selection into the right Inspector tab.
        self._on_node(self._left._tree.current_node())

    @staticmethod
    def _fix_rail(rail: QWidget, width: int) -> None:
        rail.setMinimumWidth(width)
        rail.setMaximumWidth(width)
        policy = rail.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
        policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        rail.setSizePolicy(policy)

    def _on_node(self, key: str) -> None:
        self._right.show_node(key)
        self.node_selected.emit(key)

    def _open_asset_browser(self) -> None:
        if self._asset_dialog is None:
            dialog = AssetBrowserDialog(self)
            dialog.apply_requested.connect(self.patch_requested.emit)
            dialog.favorite_toggled.connect(self.favorite_toggled.emit)
            self._asset_dialog = dialog
        self._asset_dialog.show()
        self._asset_dialog.raise_()
        self._asset_dialog.activateWindow()

    def set_favorites(self, ids: list[str]) -> None:
        if self._asset_dialog is not None:
            self._asset_dialog.set_favorites(ids)

    def set_projects(self, projects: list[tuple[str, str]], selected_id: str | None) -> None:
        self._left.set_projects(projects, selected_id)

    def set_name(self, name: str) -> None:
        self._left.set_name(name)

    def set_dirty(self, dirty: bool) -> None:
        self._left.set_dirty(dirty)

    def set_status(self, text: str) -> None:
        self._left.set_status(text)

    def set_export_busy(self, busy: bool) -> None:
        self._stage.set_export_busy(busy)

    def bind_document(self, state: dict) -> None:
        self._right.bind_document(state)
        self._stage.bind_export(state)
        tracks = state.get("audioTracks")
        track_list = [str(x) for x in tracks if str(x).strip()] if isinstance(tracks, list) else []
        active = str(state.get("audioPath") or "").strip()
        if active and active not in track_list:
            track_list.insert(0, active)
        self._stage.bind_tracks(track_list, active)

    def set_export_readiness(self, ok: bool, message: str = "") -> None:
        self._stage.set_export_readiness(ok, message)

    def export_options(self) -> dict:
        return self._stage.export_options()

    def apply_preview(self, doc: dict) -> None:
        self._preview.apply_document(doc)
        self._stage.set_duration(self._preview.duration_sec())
        self._right.set_document(doc)

    def set_ai_explanation(self, text: str) -> None:
        self._left.set_ai_explanation(text)

    def set_timeline_duration(self, duration_sec: float) -> None:
        self._stage.set_duration(duration_sec)

    def set_timeline_position(self, time_sec: float) -> None:
        self._stage.set_position(time_sec)

    def set_timeline_playing(self, playing: bool) -> None:
        self._stage.set_playing(playing)

    def preview(self) -> StudioPreviewStage:
        return self._preview

    def select_node(self, key: str) -> None:
        self._left.select_node(key)
        self._on_node(key)

    def set_preview_interaction_modes(
        self,
        *,
        spectrum_position: bool = False,
        logo_position: bool = False,
    ) -> None:
        self._stage.set_interaction_modes(
            spectrum_position=spectrum_position,
            logo_position=logo_position,
        )
