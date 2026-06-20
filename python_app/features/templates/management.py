"""Template management: CRUD, set/apply, combo handling, and persistence."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..ports import ConfirmQuestionFn

if TYPE_CHECKING:
    from ...app.main_window import MainWindow


@dataclass(slots=True)
class TemplateManagementCoordinator:
    """Owns video template management orchestration extracted from MainWindow.

    The host (VideoTemplateCoordinator) already delegates refresh / save / load
    calls. This coordinator encapsulates:
    - Setting a template into the workspace (_set_template)
    - Applying template values to UI controls (_apply_template_to_controls)
    - Deleting the current template
    - Full save / load implementations with DB + fallback
    - Combo change handling
    """

    host: "MainWindow"
    confirm_question_fn: ConfirmQuestionFn | None = field(default=None)

    # ------------------------------------------------------------------
    # Template get / set
    # ------------------------------------------------------------------

    def set_template(self, tpl: dict) -> None:
        """Apply a template dict into the workspace and persist logo path."""

        host = self.host
        from ...models.spectrum_model import normalize_template

        host.template = normalize_template(tpl)
        host.preview.set_template(host.template)
        logo_path = str(host.template.get("logoPath", "")).strip()
        if logo_path and Path(logo_path).exists():
            host.preview.load_logo(logo_path)
            host._persist_setting_patch({"videoRenderLogoPath": logo_path})
            if hasattr(host, "logo_path_input"):
                host.logo_path_input.setText(str(logo_path))
        else:
            host.preview.load_logo("")
            if hasattr(host, "logo_path_input"):
                host.logo_path_input.setText("")
        host.template_name_input.setText(str(host.template.get("templateName", "Template")))
        self.apply_template_to_controls()
        host._refresh_footer()

    # ------------------------------------------------------------------
    # Template resolution (extracted from UI)
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_dict(val: Any, key: str) -> dict:
        """Return val[key] if it's a dict, else empty dict."""
        d = val.get(key) if isinstance(val, dict) else None
        return d if isinstance(d, dict) else {}

    @staticmethod
    def _logo_real_size_to_slider_value(real_size: float) -> int:
        return int(max(1, min(10, round(float(real_size) / 100.0))))

    def resolve_template_settings(self, t: dict | None = None) -> dict[str, Any]:
        """Parse a template dict and return resolved settings for UI application.

        Returns a flat dict with all values extracted from the template,
        including defaults. No UI widgets are touched here.
        """
        if t is None:
            t = self.host.template

        result: dict[str, Any] = {}

        # Top-level
        result["style"] = str(t.get("style", "classic-vertical"))
        result["spectrum_enabled"] = bool(t.get("spectrumEnabled", True))

        # Audio settings
        a = self._safe_dict(t, "audioSettings")
        result["audio_sensitivity"] = float(a.get("sensitivity", 1.0))
        result["audio_smoothing"] = float(a.get("smoothing", 0.8))

        # Position
        p = self._safe_dict(t, "position")
        result["position_anchor"] = str(p.get("anchor", "center"))
        result["position_x"] = int(p.get("x", 0))
        result["position_y"] = int(p.get("y", 0))

        # Background settings
        bg = self._safe_dict(t, "backgroundSettings")
        result["bg_fit_mode"] = str(bg.get("fitMode", "cover"))
        result["bg_user_scale"] = float(bg.get("userScale", 1.0) or 1.0)
        result["bg_brightness"] = float(bg.get("brightness", 1.0))
        result["bg_reactivity"] = float(bg.get("reactivity", 0.0))
        result["bg_smoothing"] = float(bg.get("smoothing", 0.8))
        result["bg_motion_mode"] = str(bg.get("motionMode", "none"))
        result["bg_motion_zoom"] = float(bg.get("motionZoomStrength", 1.0))
        result["bg_motion_vibrate"] = float(bg.get("motionVibrateStrength", 1.0))

        # Logo settings
        ls = self._safe_dict(t, "logoSettings")
        result["logo_enabled"] = bool(ls.get("enabled", True))
        result["logo_circle_mask"] = bool(ls.get("circleMask", True))
        result["logo_size"] = float(ls.get("size", 200))
        result["logo_opacity"] = float(ls.get("opacity", 1.0))
        result["logo_reactivity"] = float(ls.get("reactivity", 0.0))
        result["logo_smoothing"] = float(ls.get("smoothing", 0.75))
        result["logo_spin_enabled"] = bool(ls.get("spinEnabled", False))
        result["logo_spin_direction"] = str(ls.get("spinDirection", "cw"))
        result["logo_spin_speed"] = float(ls.get("spinSpeed", 0.0) or 0.0)

        # Particles settings
        ps = self._safe_dict(t, "particlesSettings")
        result["p_enabled"] = bool(ps.get("enabled", False))
        result["p_max_count"] = int(ps.get("maxCount", 200))
        result["p_spawn_rate"] = int(ps.get("spawnRate", 100))
        result["p_lifetime"] = float(ps.get("lifetimeSec", 1.6))
        result["p_speed"] = float(ps.get("speed", 1.0))
        result["p_reactivity"] = float(ps.get("reactivity", 0.1))
        result["p_smoothing"] = float(ps.get("smoothing", 0.65))
        result["p_size"] = float(ps.get("size", 2.0))
        result["p_opacity"] = float(ps.get("opacity", 0.35))
        result["p_color"] = str(ps.get("color", "#ffffff"))
        result["p_spawn_mode"] = str(ps.get("spawnMode", "always"))
        result["p_spawn_trigger"] = str(ps.get("spawnTrigger", "both"))
        result["p_spawn_threshold"] = float(ps.get("spawnThreshold", 0.15))
        result["p_style"] = str(ps.get("style", "dot"))
        result["p_react_color"] = str(ps.get("reactColor", ps.get("color", "#ffffff")))
        result["p_react_strength"] = float(ps.get("reactStrength", 0.65))
        result["p_variant"] = str(ps.get("variant", "classic"))
        result["p_spawn_area"] = str(ps.get("spawnArea", "centerRing"))
        result["p_size_jitter"] = float(ps.get("sizeJitter", 0.0))
        result["p_drift"] = float(ps.get("drift", 0.0))
        result["p_swirl"] = float(ps.get("swirl", 0.0))

        # Effects - Vignette
        fx = self._safe_dict(t, "effects")
        vig = self._safe_dict(fx, "vignette")
        result["vig_enabled"] = bool(vig.get("enabled", False))
        result["vig_strength"] = float(vig.get("strength", 0.35))
        result["vig_feather"] = float(vig.get("feather", 0.65))
        result["vig_opacity"] = float(vig.get("opacity", 0.65))
        result["vig_color"] = str(vig.get("color", "#000000"))

        # Effects - Smoke
        sm = self._safe_dict(fx, "smoke")
        result["smoke_enabled"] = bool(sm.get("enabled", False))
        result["smoke_strength"] = float(sm.get("strength", 0.35))
        result["smoke_blur"] = float(sm.get("blur", 0.55))
        result["smoke_noise"] = float(sm.get("noise", 0.55))
        result["smoke_speed"] = float(sm.get("speed", 0.35))
        result["smoke_opacity"] = float(sm.get("opacity", 0.55))
        result["smoke_color"] = str(sm.get("color", "#000000"))

        # Text overlays
        overlays_raw = t.get("textOverlays")
        overlays = overlays_raw if isinstance(overlays_raw, list) else []
        text_overlays = []
        for i in range(5):
            o = overlays[i] if i < len(overlays) and isinstance(overlays[i], dict) else {}
            text_overlays.append({
                "enabled": bool(o.get("enabled", False)),
                "text": str(o.get("text", "")),
                "start_sec": float(o.get("startSec", 0.0) or 0.0),
                "duration_sec": float(o.get("durationSec", 3.0) or 3.0),
                "anchor": str(o.get("anchor", "top-left")),
                "x": float(o.get("x", 24.0) if "x" in o else 24.0),
                "y": float(o.get("y", 24.0) if "y" in o else 24.0),
                "size_px": float(o.get("sizePx", 46.0) if "sizePx" in o else 46.0),
                "color": str(o.get("color", "#ffffff")),
                "stroke_color": str(o.get("strokeColor", "#000000")),
                "stroke_width": float(o.get("strokeWidth", 2.0) if "strokeWidth" in o else 2.0),
                "shadow": float(o.get("shadow", 0.4) if "shadow" in o else 0.4),
                "animation": str(o.get("animation", "fade")),
            })
        result["text_overlays"] = text_overlays

        # Layer info (first selected layer)
        layers_raw = t.get("layers")
        layers = layers_raw if isinstance(layers_raw, list) else []
        result["layer_count"] = len(layers)
        if layers:
            l0 = layers[0] if isinstance(layers[0], dict) else {}
        else:
            l0 = {}
        result["layer_name"] = str(l0.get("name", "Layer"))
        result["layer_gravity"] = str(l0.get("gravity", "bottom"))
        result["layer_curved"] = bool(l0.get("curved", True))
        result["layer_mirrored"] = bool(l0.get("mirrored", True))
        result["layer_fill_circle"] = bool(l0.get("fillCircle", False))
        result["layer_bar_width"] = float(l0.get("barWidth", 4.0))
        result["layer_thickness"] = float(l0.get("thickness", 30.0))
        result["layer_radius_offset"] = float(l0.get("radiusOffset", 0.0))
        layer_opacity = float(l0.get("opacity", 1.0))
        result["layer_opacity"] = float(max(0.0, min(1.0, layer_opacity)))
        result["layer_blend_mode"] = str(l0.get("blend_mode", "normal"))
        result["layer_glow"] = float(l0.get("glow", 0.0))
        result["layer_blur"] = float(l0.get("blur", 0.0))

        layer_color = l0.get("color") if isinstance(l0.get("color"), dict) else {}
        result["layer_color_mode"] = str(layer_color.get("mode", "solid"))
        result["layer_solid_color"] = str(layer_color.get("solidColor", "#ffffff"))
        result["layer_grad_dir"] = str(layer_color.get("gradientDirection", "left-to-right"))
        result["layer_is_solid"] = str(layer_color.get("mode", "solid")) == "solid"

        return result

    # ------------------------------------------------------------------
    # Template application to UI controls
    # ------------------------------------------------------------------

    def apply_template_to_controls(self) -> None:
        """Sync template values into all video workspace widgets."""

        host = self.host
        settings = self.resolve_template_settings()

        host._apply_resolved_template_settings(settings)

    # ------------------------------------------------------------------
    # Template save implementation
    # ------------------------------------------------------------------

    def save_template_impl(self) -> None:
        """Persist the active template through the configured storage path."""

        host = self.host
        name = str(host.template_name_input.text() or "").strip() or "My Template"
        host.template["templateName"] = name
        host.template["logoPath"] = str(getattr(host.preview, "logo_path", "") or "")
        host.preview.set_template(host.template)
        if hasattr(host, "preview_title"):
            host.preview_title.setText(f"Preview: {name}")
        host._refresh_footer()

        existing_id = str(host.current_template_id or "").strip()
        tpl_id = existing_id
        existing_row = self.get_saved_video_template(existing_id) if existing_id else None
        if existing_row is not None and str(existing_row.name or "").strip() != name:
            tpl_id = ""
        if not tpl_id:
            tpl_id = str(uuid.uuid4())

        saved = False
        if host.db_cfg:
            try:
                from ...database.persistence import db_upsert_video_template
                # Determine kind from current resolution — portrait (9:16) saves as "reel"
                _res_combo = getattr(host, "video_output_resolution_combo", None)
                _cur_res = str(_res_combo.currentData() or "").strip() if _res_combo else ""
                kind = "reel" if _cur_res == "1080x1920" else "video"
                db_upsert_video_template(host.db_cfg, tpl_id, name, host.template, kind=kind)
                saved = True
            except Exception:
                saved = False
        if not saved:
            from ...database.persistence import read_local_templates, write_local_templates
            from ...models.spectrum_model import VideoTemplate

            rows = read_local_templates()
            rows2 = [r for r in rows if r.id != tpl_id]
            rows2.append(
                VideoTemplate(
                    id=tpl_id,
                    name=name,
                    source="user",
                    template=host.template,
                    updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
            )
            write_local_templates(rows2)

        host.current_template_id = tpl_id
        host.refresh_templates()
        idx = host.tpl_combo.findData(str(tpl_id))
        if idx >= 0:
            host.tpl_combo.setCurrentIndex(idx)
        host._persist_setting_patch({"videoRenderTemplatePath": tpl_id})
        host._set_export_status_message(f"Saved template: {name}")

    # ------------------------------------------------------------------
    # Template load implementation
    # ------------------------------------------------------------------

    def load_template_impl(self, tpl_id: str) -> None:
        """Load a saved template into the active workspace."""

        if not tpl_id:
            return
        host = self.host
        row = self.get_saved_video_template(str(tpl_id))
        tpl = row.template if row is not None else None
        if not isinstance(tpl, dict):
            return
        host.current_template_id = str(tpl_id)
        self.set_template(tpl)
        idx = host.tpl_combo.findData(str(tpl_id))
        if idx >= 0:
            host.tpl_combo.blockSignals(True)
            host.tpl_combo.setCurrentIndex(idx)
            host.tpl_combo.blockSignals(False)
        host._persist_setting_patch({"videoRenderTemplatePath": str(tpl_id)})

    # ------------------------------------------------------------------
    # Template delete
    # ------------------------------------------------------------------

    def delete_current_template(self) -> None:
        """Delete the currently selected template after confirmation."""

        host = self.host
        from ...models.spectrum_model import default_template

        tpl_id = str(host.current_template_id or "").strip()
        if not tpl_id:
            host._set_export_status_message("No saved template selected to delete")
            return

        name = str(host.template_name_input.text() or "").strip() or "this template"

        if self.confirm_question_fn is None:
            return
        if not self.confirm_question_fn("Delete Template", f"Delete template '{name}'?"):
            return

        deleted = False
        if host.db_cfg:
            try:
                from ...database.persistence import db_delete_video_template
                db_delete_video_template(host.db_cfg, tpl_id)
                deleted = True
            except Exception:
                deleted = False
        if not deleted:
            from ...database.persistence import read_local_templates, write_local_templates
            rows = read_local_templates()
            rows2 = [r for r in rows if str(r.id) != tpl_id]
            if len(rows2) != len(rows):
                write_local_templates(rows2)
                deleted = True
        if not deleted:
            host._set_export_status_message(f"Delete failed for template '{name}'")
            return

        host.current_template_id = None
        host.refresh_templates()
        host.tpl_combo.blockSignals(True)
        host.tpl_combo.setCurrentIndex(0)
        host.tpl_combo.blockSignals(False)
        host.template_name_input.setText("New Template")
        host.template = default_template()
        host.preview.set_template(host.template)
        if hasattr(host, "preview_title"):
            host.preview_title.setText("Preview: New Template")
        self.apply_template_to_controls()
        host._persist_setting_patch({"videoRenderTemplatePath": ""})
        host._set_export_status_message(f"Deleted template: {name}")

    # ------------------------------------------------------------------
    # Template combo change handling
    # ------------------------------------------------------------------

    def on_combo_changed(self, idx: int) -> None:
        """Handle tpl_combo selection change."""

        host = self.host
        if idx <= 0:
            host.current_template_id = None
            host._persist_setting_patch({"videoRenderTemplatePath": ""})
            return
        tpl_id = host.tpl_combo.itemData(idx)
        if tpl_id:
            self.load_template_impl(str(tpl_id))

    # ------------------------------------------------------------------
    # Template lookup helper
    # ------------------------------------------------------------------

    def get_saved_video_template(self, tpl_id: str) -> Any:
        """Fetch a saved video template from DB or local cache."""

        key = str(tpl_id or "").strip()
        if not key:
            return None
        host = self.host
        if host.db_cfg:
            try:
                from ...database.persistence import db_get_video_template
                row = db_get_video_template(host.db_cfg, key)
                if row is not None:
                    return row
            except Exception:
                pass
        from ...database.persistence import read_local_templates
        for row in read_local_templates():
            if str(row.id) == key:
                return row
        return None


# ==================================================================
# Reel Template CRUD Operations
# ==================================================================


def create_reel_template(
    db_cfg: Any,
    name: str,
    template: dict,
    *,
    source: str = "user",
    uid: str | None = None,
) -> str:
    """Create a new reel template with kind='reel'.

    Stores uid, name, source, template JSON, kind='reel', and timestamp.
    Returns the generated (or provided) uid.
    """
    from ...database.persistence import db_upsert_video_template

    tpl_id = uid or str(uuid.uuid4())
    db_upsert_video_template(db_cfg, tpl_id, name, template, kind="reel")
    return tpl_id


def update_reel_template(
    db_cfg: Any,
    template_id: str,
    name: str,
    template: dict,
) -> None:
    """Update an existing reel template (kind='reel') without affecting video templates.

    Uses the same upsert mechanism with kind='reel' so only the targeted
    reel template row is modified.
    """
    from ...database.persistence import db_upsert_video_template

    db_upsert_video_template(db_cfg, template_id, name, template, kind="reel")


def delete_reel_template(db_cfg: Any, template_id: str) -> None:
    """Delete a reel template by uid without affecting video templates.

    Since deletion targets the specific uid, video templates (which have
    different uids) remain untouched.
    """
    from ...database.persistence import db_delete_video_template

    db_delete_video_template(db_cfg, template_id)


def list_reel_templates(db_cfg: Any) -> list:
    """List all reel templates (kind='reel') from the database."""
    from ...database.persistence import db_list_video_templates

    return db_list_video_templates(db_cfg, kind="reel")
