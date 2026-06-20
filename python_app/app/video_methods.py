"""Relocated VideoMethodsMixin methods (task 11.3 shell reduction).

These methods were moved verbatim from ``MainWindow`` into this mixin so the
``MainWindow`` class body stays a thin shell (Requirement 9.1). ``MainWindow``
inherits this mixin, so ``self.<method>()`` resolves unchanged via the MRO.
"""
from __future__ import annotations

from ..features.video_export.export_batch import ExportBatch
from pathlib import Path
from .widgets import PopoutPreviewWindow
from ..visualizer.contracts import PreviewConfig
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox,
    QFileDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton,
    QSlider, QToolButton, QWidget,
)
from PyQt6.QtCore import Qt, QDate, QEvent, QObject, QPoint, QSize, QTimer
from ..views.components import _fmt_time, STACKED_LAYER_PRESETS
from ..models.spectrum_model import VideoTemplate, default_template, normalize_template
from ..views.helpers.style_helper import (
    apply_card_field as _sh_apply_card_field,
    apply_cta_button as _sh_apply_cta_button,
    refresh_widget_style as _sh_refresh_widget_style,
    render_svg_icon as _sh_render_svg_icon,
    set_button_role as _sh_set_button_role,
    set_field_role as _sh_set_field_role,
    set_label_role as _sh_set_label_role,
    set_widget_property as _sh_set_widget_property,
)
from ..database.persistence import (
    DbCfg,
    db_get_profile_image_config,
    db_list_video_templates,
    db_upsert_video_template,
    read_local_templates,
    write_local_templates,
)
from ..database.music_db import (
    find_batch_by_output_dir,
)
from ..database.image_db import (
    cancel_all_pending_image_jobs,
    get_ready_background_output,
    upsert_image_job,
)
from ..database.preset_db import list_text_style_presets
import re
import time
import uuid
from ..views.helpers import widget_factory


class VideoMethodsMixin:
    def _set_export_toggle_running(self, running: bool) -> None:
        if hasattr(self, "btn_export_toggle"):
            _sh_apply_cta_button(self.btn_export_toggle, "warning" if running else "success", self.ui)

    def _set_export_status_message(self, text: str, *, source: str = "Video") -> None:
        msg = str(text or "").strip()
        if hasattr(self, "export_status"):
            self.export_status.setText(msg)
        self._set_global_status(msg, source=source)

    def _on_profile_thumbnail_overlay_mode_changed(self, index: int) -> None:
        """Validate preset existence when switching to preset_text mode."""
        combo = getattr(self, "music_settings_profile_thumbnail_overlay_mode", None)
        if combo is None:
            return
        mode = str(combo.currentData() or "ai").strip()
        if mode != "preset_text":
            return
        # Validate that at least one text style preset exists
        try:
            presets = list_text_style_presets(self.db_cfg) if self.db_cfg else []
            if not presets:
                QMessageBox.warning(
                    self,
                    "Thumbnail Overlay",
                    "Create at least one text style preset first.",
                )
                # Revert to "ai"
                combo.blockSignals(True)
                ai_idx = combo.findData("ai")
                combo.setCurrentIndex(ai_idx if ai_idx >= 0 else 0)
                combo.blockSignals(False)
        except Exception:
            pass

    def _toggle_popout(self) -> None:
        if self._popout is not None:
            try:
                self._popout.close()
            except Exception:
                pass
            self._popout = None
            self.btn_popout.setText("Live Preview")
            return

        w = PopoutPreviewWindow(self)
        self._popout = w
        self.btn_popout.setText("Close Preview")
        w.show()

    def _on_video_output_resolution_changed(self, _idx: int = 0) -> None:
        combo = getattr(self, "video_output_resolution_combo", None)
        if combo is None:
            return
        res = str(combo.currentData() or "").strip()
        if not res:
            return
        try:
            self._persist_setting_patch({"outputResolution": res})
        except Exception:
            pass
        w = 16
        h = 9
        try:
            w, h = self._parse_output_resolution(res, fallback=(1920, 1080))
        except Exception:
            w, h = (16, 9)
        box = getattr(self, "preview_box", None)
        if box is not None and hasattr(box, "set_ratio"):
            try:
                box.set_ratio(int(w), int(h))
            except Exception:
                pass
        # Refresh template list to show reel vs video templates based on resolution
        try:
            self.refresh_templates()
        except Exception:
            pass

    def _sync_play_button_state(self) -> None:
        if hasattr(self, "btn_play") and hasattr(self, "preview"):
            is_playing = bool(getattr(self.preview, "audio_playing", False))
            self.btn_play.setText("Pause" if is_playing else "Play")

    def _sync_bg_motion_visibility(self) -> None:
        if not hasattr(self, "bg_motion_mode_combo"):
            return
        mode = str(self.bg_motion_mode_combo.currentData() or "none")
        show_zoom = mode in ("zoom", "both")
        show_vib = mode in ("vibrate", "both")
        if hasattr(self, "bg_motion_zoom_label"):
            self.bg_motion_zoom_label.setVisible(show_zoom)
        if hasattr(self, "bg_motion_zoom_slider"):
            self.bg_motion_zoom_slider.setVisible(show_zoom)
        if hasattr(self, "bg_motion_vibrate_label"):
            self.bg_motion_vibrate_label.setVisible(show_vib)
        if hasattr(self, "bg_motion_vibrate_slider"):
            self.bg_motion_vibrate_slider.setVisible(show_vib)

    def _on_preview_position_changed(self, x: int, y: int) -> None:
        p = self.template.get("position", {}) if isinstance(self.template.get("position"), dict) else {}
        self.template["position"] = {**p, "x": int(x), "y": int(y)}
        self.preview.set_template(self.template)
        if hasattr(self, "x_slider") and hasattr(self, "y_slider"):
            self.x_slider.blockSignals(True)
            self.y_slider.blockSignals(True)
            self.x_slider.setValue(int(x))
            self.y_slider.setValue(int(y))
            self.x_slider.blockSignals(False)
            self.y_slider.blockSignals(False)
        if hasattr(self, "x_label") and hasattr(self, "y_label"):
            widget_factory.set_metric_text(self.x_label, f"X Offset ({int(x)})")
            widget_factory.set_metric_text(self.y_label, f"Y Offset ({int(y)})")

    def _on_preview_background_transform_changed(self, offset_x: float, offset_y: float, scale: float) -> None:
        bg = self.template.get("backgroundSettings", {}) if isinstance(self.template.get("backgroundSettings"), dict) else {}
        self.template["backgroundSettings"] = {**bg, "userOffsetX": float(offset_x), "userOffsetY": float(offset_y), "userScale": float(scale)}
        self.preview.set_template(self.template)
        if hasattr(self, "bg_user_scale_slider"):
            self.bg_user_scale_slider.blockSignals(True)
            self.bg_user_scale_slider.setValue(int(round(float(scale) * 100.0)))
            self.bg_user_scale_slider.blockSignals(False)
        if hasattr(self, "bg_user_scale_label"):
            widget_factory.set_metric_text(self.bg_user_scale_label, f"Scale ({int(round(float(scale) * 100.0))}%)")

    def _on_seek_pressed(self) -> None:
        self._seek_dragging = True

    def _on_seek_released(self) -> None:
        self._seek_dragging = False
        dur = self._audio_controller.get_audio_duration()
        if dur <= 0:
            return
        t = (self.seek_slider.value() / 1000.0) * dur
        self._audio_controller.seek_to(t)

    def _set_template(self, tpl: dict) -> None:
        self.template = normalize_template(tpl)
        logo_path = str(self.template.get("logoPath", "")).strip()
        bg_path = getattr(self.preview, 'bg_path', '') or ''
        config = PreviewConfig(
            width=int(self.preview.width()) if hasattr(self.preview, 'width') else 1920,
            height=int(self.preview.height()) if hasattr(self.preview, 'height') else 1080,
            template=self.template,
            background_path=bg_path,
            logo_path=logo_path if logo_path and Path(logo_path).exists() else "",
        )
        self.preview.configure(config)
        if logo_path and Path(logo_path).exists():
            self._persist_setting_patch({"videoRenderLogoPath": logo_path})
            if hasattr(self, "logo_path_input"):
                self.logo_path_input.setText(str(logo_path))
        else:
            if hasattr(self, "logo_path_input"):
                self.logo_path_input.setText("")
        self.template_name_input.setText(str(self.template.get("templateName", "Template")))
        self._video_controller.apply_template_to_controls()
        self._refresh_footer()

    def _load_mp3_folder_into_ui(self, folder_path: str, selected_mp3: str = "") -> None:
        d = str(folder_path or "").strip()
        if not d:
            return
        p = Path(d)
        if not p.exists() or not p.is_dir():
            return
        def track_key(path_text: str) -> tuple[int, int, str] | tuple[int, str]:
            name = Path(path_text).name
            m = re.match(r"\s*(\d+)", name)
            if m:
                return (0, int(m.group(1)), name.lower())
            return (1, name.lower())

        mp3s = sorted([str(x) for x in p.glob("*.mp3")], key=track_key)
        self._mp3_dir = d
        self.mp3_list.blockSignals(True)
        self.mp3_list.clear()
        for m in mp3s:
            item = QListWidgetItem(Path(m).name)
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.mp3_list.addItem(item)
        self.mp3_list.blockSignals(False)
        self._log(
            f"[{time.strftime('%H:%M:%S')}] MP3 folder loaded: dir={d} count={len(mp3s)} selected={selected_mp3 or '<auto>'}"
        )
        if not mp3s:
            return
        target = str(selected_mp3 or "").strip()
        idx = mp3s.index(target) if target in mp3s else 0
        self._log(
            f"[{time.strftime('%H:%M:%S')}] MP3 folder selection apply: row={idx} track={mp3s[idx]}"
        )
        self.mp3_list.setCurrentRow(idx)

    def _on_tpl_combo_changed(self, idx: int) -> None:
        if idx <= 0:
            self.current_template_id = None
            self._persist_setting_patch({"videoRenderTemplatePath": ""})
            return
        tpl_id = self.tpl_combo.itemData(idx)
        if tpl_id:
            self.load_selected_template(str(tpl_id))

    def _reset_bg_transform(self) -> None:
        bg = self.template.get("backgroundSettings", {}) if isinstance(self.template.get("backgroundSettings"), dict) else {}
        self.template["backgroundSettings"] = {**bg, "userScale": 1.0, "userOffsetX": 0.0, "userOffsetY": 0.0}
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()

    def _pick_particle_color(self) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        col = c.name()
        self.p_color_input.setText(col)

    def _pick_particle_react_color(self) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        col = c.name()
        self.p_react_color_input.setText(col)

    def _pick_vignette_color(self) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        self.vignette_color_input.setText(c.name())

    def _pick_smoke_color(self) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        self.smoke_color_input.setText(c.name())

    def _text_overlays(self) -> list[dict]:
        raw = self.template.get("textOverlays") if isinstance(self.template.get("textOverlays"), list) else []
        return [dict(x) for x in raw if isinstance(x, dict)]

    def _set_text_overlay(self, idx: int, patch: dict) -> None:
        overlays = self._text_overlays()
        while len(overlays) < 5:
            overlays.append({})
        cur = overlays[idx] if isinstance(overlays[idx], dict) else {}
        overlays[idx] = {**cur, **patch}
        self.template["textOverlays"] = overlays
        self.preview.set_template(self.template)

    def _pick_text_color(self, idx: int) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        self.text_overlay_color[idx].setText(c.name())

    def _pick_text_stroke_color(self, idx: int) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        self.text_overlay_stroke_color[idx].setText(c.name())

    def _layers(self) -> list[dict]:
        layers = self.template.get("layers") if isinstance(self.template.get("layers"), list) else []
        out = [dict(x) for x in layers if isinstance(x, dict)]
        if not out:
            out = [dict(normalize_template(default_template()).get("layers", [{}])[0])]
        return out

    def _selected_layer(self) -> dict:
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(getattr(self, "_selected_layer_index", 0)))))
        self._selected_layer_index = idx
        return layers[idx]

    def _set_selected_layer(self, patch: dict) -> None:
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(getattr(self, "_selected_layer_index", 0)))))
        current = layers[idx] if isinstance(layers[idx], dict) else {}
        layers[idx] = {**current, **patch}
        self.template["layers"] = layers
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()

    def _set_selected_layer_color(self, patch: dict) -> None:
        layer = self._selected_layer()
        col = layer.get("color") if isinstance(layer.get("color"), dict) else {}
        self._set_selected_layer({"color": {**col, **patch}})

    def _refresh_layer_selector(self) -> None:
        if not hasattr(self, "layer_selector"):
            return
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(getattr(self, "_selected_layer_index", 0)))))
        self._selected_layer_index = idx
        self.layer_selector.blockSignals(True)
        self.layer_selector.clear()
        for i, layer in enumerate(layers):
            layer_name = str(layer.get("name") or f"Layer {i + 1}")
            self.layer_selector.addItem(layer_name, userData=i)
        self.layer_selector.setCurrentIndex(idx)
        self.layer_selector.blockSignals(False)
        if hasattr(self, "btn_remove_layer"):
            self.btn_remove_layer.setEnabled(len(layers) > 1)

    def _on_layer_selector_changed(self, idx: int) -> None:
        if idx < 0:
            return
        self._selected_layer_index = int(idx)
        self._video_controller.apply_template_to_controls()

    def _add_layer(self) -> None:
        layers = self._layers()
        base = dict(self._selected_layer()) if layers else dict(normalize_template(default_template()).get("layers", [{}])[0])
        next_idx = len(layers)
        base["id"] = f"layer-{int(time.time() * 1000)}-{next_idx + 1}"
        base["name"] = f"Layer {next_idx + 1}"
        base["radiusOffset"] = float(max(0.0, float(base.get("radiusOffset", 0.0)) + 26.0))
        layers.append(base)
        self.template["layers"] = layers
        self._selected_layer_index = next_idx
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()

    def _duplicate_selected_layer(self) -> None:
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(getattr(self, "_selected_layer_index", 0)))))
        src = dict(layers[idx])
        next_idx = len(layers)
        src["id"] = f"layer-{int(time.time() * 1000)}-{next_idx + 1}"
        src["name"] = f"{str(src.get('name') or f'Layer {idx + 1}')} Copy"
        src["radiusOffset"] = float(max(0.0, float(src.get("radiusOffset", 0.0)) + 20.0))
        layers.insert(idx + 1, src)
        self.template["layers"] = layers
        self._selected_layer_index = idx + 1
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()
        self._set_export_status_message(f"Duplicated layer: {src['name']}")

    def _remove_selected_layer(self) -> None:
        layers = self._layers()
        if len(layers) <= 1:
            self._set_export_status_message("At least one spectrum layer is required")
            return
        idx = int(max(0, min(len(layers) - 1, int(getattr(self, "_selected_layer_index", 0)))))
        removed_name = str(layers[idx].get("name") or f"Layer {idx + 1}")
        layers.pop(idx)
        self.template["layers"] = layers
        self._selected_layer_index = max(0, min(idx, len(layers) - 1))
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()
        self._set_export_status_message(f"Removed spectrum layer: {removed_name}")

    def _rename_selected_layer(self) -> None:
        name = str(self.layer_name_input.text() or "").strip()
        if not name:
            return
        self._set_selected_layer({"name": name})

    def _apply_stacked_preset(self) -> None:
        key = str(self.stack_preset_combo.currentData() or "").strip()
        if not key:
            return
        preset = STACKED_LAYER_PRESETS.get(key)
        if not isinstance(preset, dict):
            return
        base_tpl = normalize_template(self.template)
        fallback_layer = dict(base_tpl.get("layers", [default_template()["layers"][0]])[0])
        layers_out: list[dict] = []
        for i, layer_patch in enumerate(preset.get("layers", [])):
            merged_color = {**fallback_layer.get("color", {}), **(layer_patch.get("color") if isinstance(layer_patch.get("color"), dict) else {})}
            merged_layer = {**fallback_layer, **layer_patch, "color": merged_color}
            merged_layer["id"] = f"stack-{key}-{i + 1}-{int(time.time() * 1000)}"
            layers_out.append(merged_layer)
        if not layers_out:
            return
        base_tpl["style"] = str(preset.get("style") or base_tpl.get("style", "classic-vertical"))
        base_tpl["layers"] = layers_out
        self.template = normalize_template(base_tpl)
        self._selected_layer_index = 0
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()
        self._set_export_status_message(f"Applied stacked preset: {self.stack_preset_combo.currentText()}")

    def _clear_stacked_preset(self) -> None:
        base_tpl = normalize_template(self.template)
        fallback_layer = dict(default_template()["layers"][0])
        base_tpl["layers"] = [fallback_layer]
        self.template = normalize_template(base_tpl)
        self._selected_layer_index = 0
        self.preview.set_template(self.template)
        self._video_controller.apply_template_to_controls()
        if hasattr(self, "stack_preset_combo"):
            self.stack_preset_combo.blockSignals(True)
            self.stack_preset_combo.setCurrentIndex(0)
            self.stack_preset_combo.blockSignals(False)
        self._set_export_status_message("Cleared stacked ring preset")

    def _pick_layer_solid_color(self) -> None:
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        self.layer_solid_input.setText(c.name())

    def _apply_settings_to_ui(self) -> None:
        s = self.e_settings or {}
        self._ffmpeg_path = str(s.get("ffmpegPath", "")).strip()
        self._output_dir = str(s.get("videoRenderOutputDir", "")).strip()
        if hasattr(self, "export_auto_merge_toggle"):
            enabled = bool(s.get("videoAutoMergeMp4", False))
            self.export_auto_merge_toggle.blockSignals(True)
            self.export_auto_merge_toggle.setChecked(enabled)
            self._sync_toggle_button(self.export_auto_merge_toggle, enabled)
            self.export_auto_merge_toggle.blockSignals(False)
        if hasattr(self, "export_workers_spin"):
            try:
                workers = int(s.get("videoExportWorkers", 1) or 1)
            except Exception:
                workers = 1
            workers = max(1, min(10, workers))
            self.export_workers_spin.blockSignals(True)
            self.export_workers_spin.setValue(workers)
            self.export_workers_spin.blockSignals(False)
            self._export_workers = workers
        if hasattr(self, "export_speed_combo"):
            mode = str(s.get("videoExportSpeedMode", "balanced")).strip() or "balanced"
            idx = self.export_speed_combo.findData(mode)
            self.export_speed_combo.blockSignals(True)
            self.export_speed_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.export_speed_combo.blockSignals(False)
        if hasattr(self, "export_merge_progress"):
            self.export_merge_progress.setVisible(False)
            self.export_merge_progress.setValue(0)
            self.export_merge_progress.setFormat("Merging: 0%")
        self._refresh_export_output_label()
        self._refresh_footer()

    def _refresh_export_output_label(self) -> None:
        return self.workspace_coordinator.refresh_export_output_label()

    def _get_export_browse_default_dir(self) -> str:
        return self.workspace_coordinator._get_export_browse_default_dir()

    def _prompt_output_dir_for_export(self) -> str:
        return self.workspace_coordinator.prompt_output_dir_for_export()

    def _format_export_percent(self, ratio: float) -> str:
        return self.workspace_coordinator.format_export_percent(ratio)

    def _set_export_progress(self, ratio: float) -> None:
        return self.workspace_coordinator.set_export_progress(ratio)

    def _normalize_export_stage_message(self, msg: str) -> str:
        return self.workspace_coordinator.normalize_export_stage_message(msg)

    def _refresh_export_detail(self) -> None:
        return self.workspace_coordinator.refresh_export_detail()

    def _restore_runtime_state(self) -> None:
        s = self.e_settings or {}
        bg_path = str(s.get("videoRenderBackgroundPath", "")).strip()
        if bg_path and Path(bg_path).exists():
            self._pending_video_bg_path = bg_path
            self.btn_set_bg.setText("Change BG")

        logo_path = str(s.get("videoRenderLogoPath", "")).strip()
        if logo_path and Path(logo_path).exists():
            self._pending_video_logo_path = logo_path
            if hasattr(self, "btn_set_logo"):
                self.btn_set_logo.setText("Change Logo")
            if hasattr(self, "logo_path_input"):
                self.logo_path_input.setText(str(logo_path))

        mp3_dir = str(s.get("videoRenderMp3Dir", "")).strip()
        selected_mp3 = str(s.get("videoRenderSelectedMp3", "")).strip()
        if mp3_dir:
            self._pending_video_mp3_dir = mp3_dir
            self._pending_video_selected_mp3 = selected_mp3
            self._mp3_dir = mp3_dir

        template_id = str(s.get("videoRenderTemplatePath", "")).strip()
        if template_id:
            self._pending_video_template_id = template_id

    def _apply_pending_video_restore(self) -> None:
        bg_path = str(getattr(self, "_pending_video_bg_path", "") or "").strip()
        logo_path = str(getattr(self, "_pending_video_logo_path", "") or "").strip()
        # Use PreviewConfig DTO to restore background and logo on the preview widget
        if (bg_path and Path(bg_path).exists()) or (logo_path and Path(logo_path).exists()):
            config = PreviewConfig(
                width=int(self.preview.width()) if hasattr(self.preview, 'width') else 1920,
                height=int(self.preview.height()) if hasattr(self.preview, 'height') else 1080,
                template=getattr(self, 'template', {}),
                background_path=bg_path if bg_path and Path(bg_path).exists() else "",
                logo_path=logo_path if logo_path and Path(logo_path).exists() else "",
            )
            try:
                self.preview.configure(config)
            except Exception:
                pass
        template_id = str(getattr(self, "_pending_video_template_id", "") or "").strip()
        if template_id:
            try:
                self.load_selected_template(template_id)
            except Exception:
                pass
        mp3_dir = str(getattr(self, "_pending_video_mp3_dir", "") or "").strip()
        selected_mp3 = str(getattr(self, "_pending_video_selected_mp3", "") or "").strip()
        if mp3_dir:
            try:
                self._load_mp3_folder_into_ui(mp3_dir, selected_mp3)
            except Exception:
                pass
        self._pending_video_bg_path = ""
        self._pending_video_logo_path = ""
        self._pending_video_template_id = ""
        self._pending_video_mp3_dir = ""
        self._pending_video_selected_mp3 = ""

    def _get_saved_video_template(self, tpl_id: str) -> VideoTemplate | None:
        return self.workspace_coordinator.get_saved_video_template(tpl_id)

    def refresh_templates(self) -> None:
        return self.template_coordinator.refresh_template_list()

    def refresh_templates_impl(self) -> None:
        # Determine which kind to list based on current resolution
        _res_combo = getattr(self, "video_output_resolution_combo", None)
        _cur_res = str(_res_combo.currentData() or "").strip() if _res_combo else ""
        kind = "reel" if _cur_res == "1080x1920" else "video"

        rows = []
        if self.db_cfg:
            try:
                rows = db_list_video_templates(self.db_cfg, kind=kind)
                write_local_templates(rows)
            except Exception:
                rows = read_local_templates()
        else:
            rows = read_local_templates()

        self.tpl_combo.blockSignals(True)
        self.tpl_combo.clear()
        self.tpl_combo.addItem("Load Template...", userData="")
        for r in rows:
            self.tpl_combo.addItem(r.name or r.id, userData=r.id)
        if self.current_template_id:
            idx = self.tpl_combo.findData(str(self.current_template_id))
            if idx >= 0:
                self.tpl_combo.setCurrentIndex(idx)
        self.tpl_combo.blockSignals(False)

    def save_template(self) -> None:
        return self.template_coordinator.save_template()

    def save_template_impl(self) -> None:
        name = str(self.template_name_input.text() or "").strip() or "My Template"
        self.template["templateName"] = name
        self.template["logoPath"] = str(getattr(self.preview, "logo_path", "") or "")
        self.preview.set_template(self.template)
        if hasattr(self, "preview_title"):
            self.preview_title.setText(f"Preview: {name}")
        self._refresh_footer()
        existing_id = str(self.current_template_id or "").strip()
        tpl_id = existing_id
        existing_row = self._get_saved_video_template(existing_id) if existing_id else None
        if existing_row is not None and str(existing_row.name or "").strip() != name:
            tpl_id = ""
        if not tpl_id:
            tpl_id = str(uuid.uuid4())
        # Determine template kind from current resolution — portrait (9:16) saves as "reel"
        _res_combo = getattr(self, "video_output_resolution_combo", None)
        _cur_res = str(_res_combo.currentData() or "").strip() if _res_combo else ""
        kind = "reel" if _cur_res == "1080x1920" else "video"

        saved = False
        if self.db_cfg:
            try:
                db_upsert_video_template(self.db_cfg, tpl_id, name, self.template, kind=kind)
                saved = True
            except Exception:
                saved = False
        if not saved:
            rows = read_local_templates()
            rows2 = [r for r in rows if r.id != tpl_id]
            rows2.append(VideoTemplate(id=tpl_id, name=name, source="user", template=self.template, updated_at=time.strftime("%Y-%m-%dT%H:%M:%S")))
            write_local_templates(rows2)
        self.current_template_id = tpl_id
        self.refresh_templates()
        idx = self.tpl_combo.findData(str(tpl_id))
        if idx >= 0:
            self.tpl_combo.setCurrentIndex(idx)
        self._persist_setting_patch({"videoRenderTemplatePath": tpl_id})
        self._set_export_status_message(f"Saved template: {name}")

    def load_selected_template(self, tpl_id: str) -> None:
        return self.template_coordinator.load_selected_template(tpl_id)

    def load_selected_template_impl(self, tpl_id: str) -> None:
        if not tpl_id:
            return
        row = self._get_saved_video_template(str(tpl_id))
        tpl = row.template if row is not None else None
        if not isinstance(tpl, dict):
            return
        self.current_template_id = str(tpl_id)
        self._set_template(tpl)
        idx = self.tpl_combo.findData(str(tpl_id))
        if idx >= 0:
            self.tpl_combo.blockSignals(True)
            self.tpl_combo.setCurrentIndex(idx)
            self.tpl_combo.blockSignals(False)
        self._persist_setting_patch({"videoRenderTemplatePath": str(tpl_id)})

    def delete_current_template(self) -> None:
        self.template_mgmt_coordinator.delete_current_template()

    def _browse_mp3_folder_with_file_preview(self, start_dir: str = "") -> str:
        initial_dir = str(start_dir or getattr(self, "_mp3_dir", "") or "").strip()
        dlg = QFileDialog(self, "Select MP3 Folder", initial_dir)
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        dlg.setOption(QFileDialog.Option.ShowDirsOnly, False)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setNameFilter("MP3 Files (*.mp3);;All Files (*.*)")
        dlg.setLabelText(QFileDialog.DialogLabel.Accept, "Select Folder")
        if not dlg.exec():
            return ""
        files = dlg.selectedFiles()
        selected = str(files[0]).strip() if files else ""
        if selected:
            selected_path = Path(selected)
            if selected_path.is_file():
                resolved = str(selected_path.parent)
                self._log(
                    f"[{time.strftime('%H:%M:%S')}] MP3 folder dialog resolved file selection to parent folder: "
                    f"file={selected} folder={resolved}"
                )
                return resolved
            if selected_path.is_dir():
                return str(selected_path)
        try:
            current_dir = str(dlg.directory().absolutePath()).strip()
        except Exception:
            current_dir = ""
        if current_dir:
            self._log(
                f"[{time.strftime('%H:%M:%S')}] MP3 folder dialog fallback directory used: {current_dir}"
            )
        return current_dir

    def pick_mp3_folder(self) -> None:
        d = self._browse_mp3_folder_with_file_preview(getattr(self, "_mp3_dir", ""))
        if not d:
            return
        self._log(f"[{time.strftime('%H:%M:%S')}] MP3 folder picked: {d}")
        self._load_mp3_folder_into_ui(d)
        self._persist_setting_patch({"videoRenderMp3Dir": d})

    def _on_generate_thumbnail_clicked(self) -> None:
        """Handle Generate Thumbnail button click on the Video page."""
        mp3_dir = str(getattr(self, "_mp3_dir", "") or "").strip()
        if not mp3_dir:
            QMessageBox.warning(self, "Thumbnail", "Select an MP3 folder first.")
            return
        if not self.db_cfg:
            QMessageBox.warning(self, "Thumbnail", "Database is not configured.")
            return

        # Resolve batch_id and profile from the current mp3 directory
        batch_info = find_batch_by_output_dir(self.db_cfg, mp3_dir)
        batch_id = str(batch_info.get("batchId", "")).strip()
        if not batch_id:
            QMessageBox.warning(self, "Thumbnail", "Could not determine batch for the current MP3 folder.")
            return

        role = str(batch_info.get("role", "OK")).strip().upper()
        profile_id = str(batch_info.get("profileOkId", "")).strip() if role == "OK" else str(batch_info.get("profileAltId", "")).strip()
        if not profile_id:
            # Fallback to the other profile if primary is empty
            profile_id = str(batch_info.get("profileAltId", "")).strip() or str(batch_info.get("profileOkId", "")).strip()
        if not profile_id:
            QMessageBox.warning(self, "Thumbnail", "Could not determine profile for the current batch.")
            return

        # Check for existing background image
        bg_path = get_ready_background_output(self.db_cfg, batch_id=batch_id, profile_id=profile_id)
        if not bg_path:
            QMessageBox.warning(self, "Thumbnail", "Background image must be generated first.")
            return

        # Get the profile's thumbnail overlay mode
        image_config = db_get_profile_image_config(self.db_cfg, profile_id)
        thumbnail_mode = str(image_config.get("thumbnailOverlayMode", "ai")).strip().lower()

        # Create the thumbnail job
        job = upsert_image_job(self.db_cfg, {
            "batchId": batch_id,
            "profileId": profile_id,
            "kind": "thumbnail",
            "status": "PENDING",
        })

        self._log(f"[{time.strftime('%H:%M:%S')}] Generate Thumbnail: batch={batch_id} profile={profile_id} mode={thumbnail_mode} job_uid={job.get('jobUid', '')}")

        # Trigger image poll to pick up the new job
        if hasattr(self, "_image_coordinator"):
            self._image_coordinator.trigger_image_poll(manual=True, max_jobs=4)

        QMessageBox.information(self, "Thumbnail", f"Thumbnail job created (mode: {thumbnail_mode}). It will appear in the Image page queue.")

    def on_mp3_selected(self, idx: int) -> None:
        if not hasattr(self, "mp3_list") or idx < 0 or idx >= self.mp3_list.count():
            self._log(f"[{time.strftime('%H:%M:%S')}] MP3 selection ignored: idx={idx}")
            return
        item = self.mp3_list.item(idx)
        p = item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        if not p:
            self._log(f"[{time.strftime('%H:%M:%S')}] MP3 selection ignored: empty path at row={idx}")
            return
        selected_path = str(p).strip()
        current_path = str(getattr(self.preview, "audio_path", "") or "").strip()
        self._log(
            f"[{time.strftime('%H:%M:%S')}] MP3 selection changed: row={idx} path={selected_path} current={current_path or '<none>'}"
        )
        if selected_path == current_path and (
            getattr(self.preview, "audio_loading", False)
            or getattr(self.preview, "analysis_loading", False)
            or getattr(self.preview, "audio_ready", False)
        ):
            self._log(
                f"[{time.strftime('%H:%M:%S')}] MP3 reload skipped: already active {selected_path}"
            )
        else:
            self.preview.load_audio(selected_path)
        self._set_export_status_message(Path(selected_path).name)
        self._persist_setting_patch({"videoRenderSelectedMp3": selected_path})
        self._refresh_footer()

    def pick_bg(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Select Background", "", "Image Files (*.png *.jpg *.jpeg)")
        if f:
            self.preview.load_background(f)
            self.btn_set_bg.setText("Change BG")
            self._persist_setting_patch({"videoRenderBackgroundPath": f})

    def pick_logo(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Image Files (*.png *.jpg *.jpeg)")
        if f:
            self.preview.load_logo(f)
            self.template["logoPath"] = str(f)
            if hasattr(self, "btn_set_logo"):
                self.btn_set_logo.setText("Change Logo")
            if hasattr(self, "logo_path_input"):
                self.logo_path_input.setText(str(f))
            self._persist_setting_patch({"videoRenderLogoPath": f})

    def pick_ffmpeg(self) -> None:
        return self.workspace_coordinator.pick_ffmpeg()

    def _toggle_export(self) -> None:
        if self._export_batches:
            self.stop_export()
        else:
            self.start_batch_export()

    def _on_export_auto_merge_changed(self) -> None:
        enabled = bool(getattr(self, "export_auto_merge_toggle", None).isChecked()) if hasattr(self, "export_auto_merge_toggle") else False
        self._persist_setting_patch({"videoAutoMergeMp4": bool(enabled)})

    def _on_export_workers_changed(self, value: int) -> None:
        workers = max(1, min(10, int(value or 1)))
        self._persist_setting_patch({"videoExportWorkers": workers})
        self._export_workers = workers
        if hasattr(self, "perf_export_workers_spin"):
            try:
                self.perf_export_workers_spin.blockSignals(True)
                self.perf_export_workers_spin.setValue(workers)
            finally:
                self.perf_export_workers_spin.blockSignals(False)

    def _on_export_speed_mode_changed(self, _value: int = 0) -> None:
        combo = getattr(self, "export_speed_combo", None)
        if combo is None:
            return
        mode = str(combo.currentData() or "balanced").strip() or "balanced"
        if mode not in {"balanced", "fast", "very_fast"}:
            mode = "balanced"
        self._persist_setting_patch({"videoExportSpeedMode": mode})

    def _export_worker_limit(self) -> int:
        return self.workspace_coordinator.worker_limit()

    def _parse_output_resolution(self, text: str, *, fallback: tuple[int, int] = (1920, 1080)) -> tuple[int, int]:
        return self.workspace_coordinator.parse_output_resolution(text, fallback=fallback)

    def _resolved_output_resolution(self, *, profile: dict | None = None) -> tuple[int, int]:
        return self.workspace_coordinator.resolved_output_resolution(profile=profile)

    def _export_auto_merge_enabled(self) -> bool:
        return self.workspace_coordinator.export_auto_merge_enabled()

    def _update_export_overall_progress(self) -> None:
        return self.workspace_coordinator.update_export_overall_progress()

    def _start_export_workers(self, batch: ExportBatch) -> None:
        return self.export_coordinator.start_export_workers(batch)

    def start_batch_export(self) -> None:
        return self.export_coordinator.start_batch_export()

    def stop_export(self) -> None:
        return self.export_coordinator.stop_export()

    def stop_export_for_batch(self, batch_key: str) -> None:
        return self.export_coordinator.stop_export_for_batch(batch_key)

    def stop_export_merge(self) -> None:
        return self.export_coordinator.stop_export_merge()

    def _on_export_event(self, evt: dict) -> None:
        # NOTE: export events keep delegating to the ExportCoordinator. The
        # SignalRouter dispatches by a single event-type key, but export
        # "progress"/"status" types collide with the music-event types of the
        # same name, so routing export through the router would misroute them.
        # MainWindow holds no export dispatch-switch logic here (Req 4.6).
        return self.export_coordinator.on_export_event(evt)

    def _find_batch_for_mp3(self, mp3_path: str) -> tuple[str | None, ExportBatch | None]:
        return self.export_coordinator.find_batch_for_mp3(mp3_path)

    def _handle_export_started(self, evt: dict) -> None:
        return self.export_coordinator.handle_export_started(evt)

    def _handle_export_stage_changed(self, evt: dict) -> None:
        return self.export_coordinator.handle_export_stage_changed(evt)

    def _handle_export_progress(self, evt: dict) -> None:
        return self.export_coordinator.handle_export_progress(evt)

    def _handle_export_completed(self, evt: dict) -> None:
        return self.export_coordinator.handle_export_completed(evt)

    def _handle_export_failed(self, evt: dict) -> None:
        return self.export_coordinator.handle_export_failed(evt)

    def _handle_export_status(self, evt: dict) -> None:
        return self.export_coordinator.handle_export_status(evt)

    def _on_export_done(self, payload: dict) -> None:
        return self.export_coordinator.on_export_done(payload)
