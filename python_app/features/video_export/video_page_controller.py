"""VideoPageController — owns video template parameter updates.

Extracted from ``MainWindow`` as part of the *main-window-decomposition* spec
(Requirement 2). The controller owns all ``update_*`` template-parameter methods
(formerly ``_update_*`` on ``MainWindow``) and the ``apply_*`` methods that
populate UI controls from a resolved template-settings dict.

The controller does **not** hold a reference to ``MainWindow``. Instead it
receives a small set of callables and a registry of widget accessors:

* ``template_accessor`` — returns the live template ``dict``.
* ``template_mutator`` — pushes an updated template back to the host/preview.
* ``preview_accessor`` — returns the visualizer preview widget.
* ``persist_fn`` — persists the template change.
* ``widget_accessors`` — maps a widget/attribute name to a zero-arg callable
  returning the corresponding widget (or helper object such as the template
  management coordinator). Missing names resolve to ``None`` so the controller
  degrades gracefully when a widget has not been built yet.

Each ``update_*`` method follows the same pipeline: read the current template
via ``template_accessor``, apply the parameter change, push the updated template
through ``template_mutator``, and call ``persist_fn`` to persist the change.
"""

from __future__ import annotations

from collections.abc import Callable

from ...models.spectrum_model import default_template, normalize_template
from ...views.components import _apply_style_preset_to_template
from ...views.helpers import widget_factory
from ...visualizer.contracts import PreviewConfig


class VideoPageController:
    """Owns video template parameter updates and UI <-> template sync."""

    def __init__(
        self,
        *,
        template_accessor: Callable[[], dict],
        template_mutator: Callable[[dict], None],
        preview_accessor: Callable[[], PreviewConfig],
        persist_fn: Callable[[dict], None],
        widget_accessors: dict[str, Callable[[], object]],
    ) -> None:
        self._template_accessor = template_accessor
        self._template_mutator = template_mutator
        self._preview_accessor = preview_accessor
        self._persist_fn = persist_fn
        self._widget_accessors = dict(widget_accessors)
        self._selected_layer_index: int = 0
        self._bg_edit_mode: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _w(self, name: str) -> object | None:
        """Return the named widget/helper, or ``None`` when unavailable."""
        accessor = self._widget_accessors.get(name)
        if accessor is None:
            return None
        try:
            return accessor()
        except Exception:
            return None

    def _metric(self, name: str, text: str) -> None:
        """Set a metric label's text if the label widget exists."""
        widget = self._w(name)
        if widget is not None:
            widget_factory.set_metric_text(widget, text)

    def _coordinator(self) -> object | None:
        """Return the template management coordinator if wired."""
        return self._w("template_mgmt_coordinator")

    def _commit(self, template: dict) -> None:
        """Push the updated template to the preview and persist the change."""
        self._template_mutator(template)
        self._persist_fn(template)

    @staticmethod
    def _sync_toggle_button(toggle: object, checked: bool) -> None:
        """Reflect the checked state in the toggle button's text."""
        if toggle is not None and hasattr(toggle, "setText"):
            toggle.setText("ON" if checked else "OFF")

    @staticmethod
    def _logo_size_slider_to_real_size(slider_value: int) -> int:
        return int(max(1, min(10, int(slider_value)))) * 100

    @staticmethod
    def _logo_real_size_to_slider_value(real_size: float) -> int:
        return int(max(1, min(10, round(float(real_size) / 100.0))))

    def _sync_bg_motion_visibility(self) -> None:
        combo = self._w("bg_motion_mode_combo")
        if combo is None:
            return
        mode = str(combo.currentData() or "none")
        show_zoom = mode in ("zoom", "both")
        show_vib = mode in ("vibrate", "both")
        for name, show in (
            ("bg_motion_zoom_label", show_zoom),
            ("bg_motion_zoom_slider", show_zoom),
            ("bg_motion_vibrate_label", show_vib),
            ("bg_motion_vibrate_slider", show_vib),
        ):
            widget = self._w(name)
            if widget is not None:
                widget.setVisible(show)

    # ------------------------------------------------------------------
    # Layer / overlay state helpers
    # ------------------------------------------------------------------
    def _layers(self) -> list[dict]:
        t = self._template_accessor()
        layers = t.get("layers") if isinstance(t.get("layers"), list) else []
        out = [dict(x) for x in layers if isinstance(x, dict)]
        if not out:
            out = [dict(normalize_template(default_template()).get("layers", [{}])[0])]
        return out

    def _selected_layer(self) -> dict:
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(self._selected_layer_index))))
        self._selected_layer_index = idx
        return layers[idx]

    def _set_selected_layer(self, patch: dict) -> None:
        t = self._template_accessor()
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(self._selected_layer_index))))
        current = layers[idx] if isinstance(layers[idx], dict) else {}
        layers[idx] = {**current, **patch}
        t["layers"] = layers
        self._commit(t)
        self.apply_template_to_controls()

    def _set_selected_layer_color(self, patch: dict) -> None:
        layer = self._selected_layer()
        col = layer.get("color") if isinstance(layer.get("color"), dict) else {}
        self._set_selected_layer({"color": {**col, **patch}})

    def _text_overlays(self) -> list[dict]:
        t = self._template_accessor()
        raw = t.get("textOverlays") if isinstance(t.get("textOverlays"), list) else []
        return [dict(x) for x in raw if isinstance(x, dict)]

    def _set_text_overlay(self, idx: int, patch: dict) -> None:
        t = self._template_accessor()
        overlays = self._text_overlays()
        while len(overlays) < 5:
            overlays.append({})
        cur = overlays[idx] if isinstance(overlays[idx], dict) else {}
        overlays[idx] = {**cur, **patch}
        t["textOverlays"] = overlays
        self._commit(t)

    def _refresh_layer_selector(self) -> None:
        selector = self._w("layer_selector")
        if selector is None:
            return
        layers = self._layers()
        idx = int(max(0, min(len(layers) - 1, int(self._selected_layer_index))))
        self._selected_layer_index = idx
        selector.blockSignals(True)
        selector.clear()
        for i, layer in enumerate(layers):
            layer_name = str(layer.get("name") or f"Layer {i + 1}")
            selector.addItem(layer_name, userData=i)
        selector.setCurrentIndex(idx)
        selector.blockSignals(False)
        btn_remove = self._w("btn_remove_layer")
        if btn_remove is not None:
            btn_remove.setEnabled(len(layers) > 1)

    # ------------------------------------------------------------------
    # Apply (template -> UI controls)
    # ------------------------------------------------------------------
    def apply_template_to_controls(self) -> None:
        """Apply the current template to UI controls via coordinator."""
        coord = self._coordinator()
        if coord is not None:
            coord.apply_template_to_controls()
        else:
            self.apply_resolved_template_settings({})

    def apply_resolved_template_settings(self, settings: dict) -> None:
        """Apply a pre-resolved template settings dict to UI controls."""
        t = self._template_accessor()
        s = settings  # resolved settings dict from coordinator
        if not s:
            coord = self._coordinator()
            s = coord.resolve_template_settings(t) if coord is not None else {}
        self.apply_style_and_audio_settings(s)
        self.apply_background_settings(s)
        self.apply_effect_settings(s)
        self.apply_overlay_settings(s)
        self.apply_layer_settings(s)

    def apply_style_and_audio_settings(self, s: dict) -> None:
        """Apply style combo, spectrum enabled, audio sensitivity/smoothing."""
        t = self._template_accessor()
        # --- Style combo ---
        style_combo = self._w("style_combo")
        if style_combo is not None:
            style_combo.blockSignals(True)
            style_combo.setCurrentIndex(max(0, style_combo.findData(str(s.get("style", str(t.get("style", "classic-vertical")))))))
            style_combo.blockSignals(False)

        # --- Spectrum enabled ---
        spectrum_enabled = self._w("spectrum_enabled")
        if spectrum_enabled is not None:
            spectrum_enabled.blockSignals(True)
            en = bool(s.get("spectrum_enabled", bool(t.get("spectrumEnabled", True))))
            spectrum_enabled.setChecked(en)
            spectrum_enabled.blockSignals(False)
            self._sync_toggle_button(spectrum_enabled, en)

        # --- Audio settings ---
        sens_slider = self._w("sens_slider")
        if sens_slider is not None:
            sens_slider.blockSignals(True)
            sens_slider.setValue(int(round(float(s.get("audio_sensitivity", 1.0)) * 100.0)))
            sens_slider.blockSignals(False)
        smooth_slider = self._w("smooth_slider")
        if smooth_slider is not None:
            smooth_slider.blockSignals(True)
            smooth_slider.setValue(int(round(float(s.get("audio_smoothing", 0.8)) * 100.0)))
            smooth_slider.blockSignals(False)
        self._metric("sens_label", f"Sensitivity ({float(s.get('audio_sensitivity', 1.0)):.2f})")
        self._metric("smooth_label", f"Smoothing ({float(s.get('audio_smoothing', 0.8)):.2f})")

        # --- Position ---
        anchor_combo = self._w("anchor_combo")
        if anchor_combo is not None:
            anchor_combo.blockSignals(True)
            anchor_combo.setCurrentIndex(max(0, anchor_combo.findData(str(s.get("position_anchor", "center")))))
            anchor_combo.blockSignals(False)
        x_slider = self._w("x_slider")
        if x_slider is not None:
            x_slider.blockSignals(True)
            x_slider.setValue(int(s.get("position_x", 0)))
            x_slider.blockSignals(False)
        y_slider = self._w("y_slider")
        if y_slider is not None:
            y_slider.blockSignals(True)
            y_slider.setValue(int(s.get("position_y", 0)))
            y_slider.blockSignals(False)
        self._metric("x_label", f"X Offset ({int(s.get('position_x', 0))})")
        self._metric("y_label", f"Y Offset ({int(s.get('position_y', 0))})")

    def apply_background_settings(self, s: dict) -> None:
        """Apply background fit, scale, brightness, reactivity, smoothing, motion."""
        bg_fit_mode_combo = self._w("bg_fit_mode_combo")
        if bg_fit_mode_combo is not None:
            bg_fit_mode_combo.blockSignals(True)
            bg_fit_mode_combo.setCurrentIndex(max(0, bg_fit_mode_combo.findData(str(s.get("bg_fit_mode", "cover")))))
            bg_fit_mode_combo.blockSignals(False)
        bg_user_scale_slider = self._w("bg_user_scale_slider")
        if bg_user_scale_slider is not None:
            bg_user_scale_slider.blockSignals(True)
            bg_user_scale_slider.setValue(int(round(float(s.get("bg_user_scale", 1.0)) * 100.0)))
            bg_user_scale_slider.blockSignals(False)
        bg_user_scale_label = self._w("bg_user_scale_label")
        if bg_user_scale_label is not None:
            pct = int(round(float(s.get("bg_user_scale", 1.0)) * 100.0))
            widget_factory.set_metric_text(bg_user_scale_label, f"Scale ({pct}%)")
        bg_edit_mode = self._w("bg_edit_mode")
        if bg_edit_mode is not None:
            bg_edit = bool(self._bg_edit_mode)
            bg_edit_mode.blockSignals(True)
            bg_edit_mode.setChecked(bg_edit)
            bg_edit_mode.blockSignals(False)
            self._sync_toggle_button(bg_edit_mode, bg_edit)
        bg_brightness_slider = self._w("bg_brightness_slider")
        if bg_brightness_slider is not None:
            bg_brightness_slider.blockSignals(True)
            bg_brightness_slider.setValue(int(round(float(s.get("bg_brightness", 1.0)) * 100.0)))
            bg_brightness_slider.blockSignals(False)
        bg_reactivity_slider = self._w("bg_reactivity_slider")
        if bg_reactivity_slider is not None:
            bg_reactivity_slider.blockSignals(True)
            bg_reactivity_slider.setValue(int(round(float(s.get("bg_reactivity", 0.0)) * 100.0)))
            bg_reactivity_slider.blockSignals(False)
        bg_smoothing_slider = self._w("bg_smoothing_slider")
        if bg_smoothing_slider is not None:
            bg_smoothing_slider.blockSignals(True)
            bg_smoothing_slider.setValue(int(round(float(s.get("bg_smoothing", 0.8)) * 100.0)))
            bg_smoothing_slider.blockSignals(False)
        bg_motion_mode_combo = self._w("bg_motion_mode_combo")
        if bg_motion_mode_combo is not None:
            bg_motion_mode_combo.blockSignals(True)
            bg_motion_mode_combo.setCurrentIndex(max(0, bg_motion_mode_combo.findData(str(s.get("bg_motion_mode", "none")))))
            bg_motion_mode_combo.blockSignals(False)
        bg_motion_zoom_slider = self._w("bg_motion_zoom_slider")
        if bg_motion_zoom_slider is not None:
            bg_motion_zoom_slider.blockSignals(True)
            bg_motion_zoom_slider.setValue(int(round(float(s.get("bg_motion_zoom", 1.0)) * 100.0)))
            bg_motion_zoom_slider.blockSignals(False)
        bg_motion_vibrate_slider = self._w("bg_motion_vibrate_slider")
        if bg_motion_vibrate_slider is not None:
            bg_motion_vibrate_slider.blockSignals(True)
            bg_motion_vibrate_slider.setValue(int(round(float(s.get("bg_motion_vibrate", 1.0)) * 100.0)))
            bg_motion_vibrate_slider.blockSignals(False)
        self._metric("bg_brightness_label", f"Brightness ({float(s.get('bg_brightness', 1.0)):.2f})")
        self._metric("bg_reactivity_label", f"Audio Reactivity ({float(s.get('bg_reactivity', 0.0)):.2f})")
        self._metric("bg_smoothing_label", f"Reaction Smoothness ({float(s.get('bg_smoothing', 0.8)):.2f})")
        self._metric("bg_motion_zoom_label", f"Zoom Strength ({float(s.get('bg_motion_zoom', 1.0)):.2f})")
        self._metric("bg_motion_vibrate_label", f"Vibrate Strength ({float(s.get('bg_motion_vibrate', 1.0)):.2f})")
        self._sync_bg_motion_visibility()

    def apply_effect_settings(self, s: dict) -> None:
        """Apply particles, vignette, smoke, and particle extras."""
        # --- Particles ---
        particles_enabled = self._w("particles_enabled")
        if particles_enabled is not None:
            particles_enabled.blockSignals(True)
            p_en = bool(s.get("p_enabled", False))
            particles_enabled.setChecked(p_en)
            particles_enabled.blockSignals(False)
            self._sync_toggle_button(particles_enabled, p_en)
        particles_controls = self._w("particles_controls")
        if particles_controls is not None:
            particles_controls.setVisible(bool(s.get("p_enabled", False)))
        p_max_slider = self._w("p_max_slider")
        if p_max_slider is not None:
            p_max_slider.blockSignals(True)
            p_max_slider.setValue(int(s.get("p_max_count", 200)))
            p_max_slider.blockSignals(False)
        p_spawn_slider = self._w("p_spawn_slider")
        if p_spawn_slider is not None:
            p_spawn_slider.blockSignals(True)
            p_spawn_slider.setValue(int(s.get("p_spawn_rate", 100)))
            p_spawn_slider.blockSignals(False)
        p_life_slider = self._w("p_life_slider")
        if p_life_slider is not None:
            p_life_slider.blockSignals(True)
            p_life_slider.setValue(int(round(float(s.get("p_lifetime", 1.6)) * 100.0)))
            p_life_slider.blockSignals(False)
        p_speed_slider = self._w("p_speed_slider")
        if p_speed_slider is not None:
            p_speed_slider.blockSignals(True)
            p_speed_slider.setValue(int(round(float(s.get("p_speed", 1.0)) * 10.0)))
            p_speed_slider.blockSignals(False)
        p_react_slider = self._w("p_react_slider")
        if p_react_slider is not None:
            p_react_slider.blockSignals(True)
            p_react_slider.setValue(int(round(float(s.get("p_reactivity", 0.1)) * 100.0)))
            p_react_slider.blockSignals(False)
        p_smoothing_slider = self._w("p_smoothing_slider")
        if p_smoothing_slider is not None:
            p_smoothing_slider.blockSignals(True)
            p_smoothing_slider.setValue(int(round(float(s.get("p_smoothing", 0.65)) * 100.0)))
            p_smoothing_slider.blockSignals(False)
        p_size_slider = self._w("p_size_slider")
        if p_size_slider is not None:
            p_size_slider.blockSignals(True)
            p_size_slider.setValue(int(round(float(s.get("p_size", 2.0)) * 10.0)))
            p_size_slider.blockSignals(False)
        p_opacity_slider = self._w("p_opacity_slider")
        if p_opacity_slider is not None:
            p_opacity_slider.blockSignals(True)
            p_opacity_slider.setValue(int(round(float(s.get("p_opacity", 0.35)) * 100.0)))
            p_opacity_slider.blockSignals(False)
        p_color_input = self._w("p_color_input")
        if p_color_input is not None:
            p_color_input.blockSignals(True)
            p_color_input.setText(str(s.get("p_color", "#ffffff")))
            p_color_input.blockSignals(False)
        p_spawn_mode_combo = self._w("p_spawn_mode_combo")
        if p_spawn_mode_combo is not None:
            p_spawn_mode_combo.blockSignals(True)
            p_spawn_mode_combo.setCurrentIndex(max(0, p_spawn_mode_combo.findData(str(s.get("p_spawn_mode", "always")))))
            p_spawn_mode_combo.blockSignals(False)
        p_spawn_trigger_combo = self._w("p_spawn_trigger_combo")
        if p_spawn_trigger_combo is not None:
            p_spawn_trigger_combo.blockSignals(True)
            p_spawn_trigger_combo.setCurrentIndex(max(0, p_spawn_trigger_combo.findData(str(s.get("p_spawn_trigger", "both")))))
            p_spawn_trigger_combo.blockSignals(False)
        p_spawn_threshold_slider = self._w("p_spawn_threshold_slider")
        if p_spawn_threshold_slider is not None:
            p_spawn_threshold_slider.blockSignals(True)
            p_spawn_threshold_slider.setValue(int(round(float(s.get("p_spawn_threshold", 0.15)) * 100.0)))
            p_spawn_threshold_slider.blockSignals(False)
        p_style_combo = self._w("p_style_combo")
        if p_style_combo is not None:
            p_style_combo.blockSignals(True)
            p_style_combo.setCurrentIndex(max(0, p_style_combo.findData(str(s.get("p_style", "dot")))))
            p_style_combo.blockSignals(False)
        p_react_color_input = self._w("p_react_color_input")
        if p_react_color_input is not None:
            p_react_color_input.blockSignals(True)
            p_react_color_input.setText(str(s.get("p_react_color", "#ffffff")))
            p_react_color_input.blockSignals(False)
        p_react_strength_slider = self._w("p_react_strength_slider")
        if p_react_strength_slider is not None:
            p_react_strength_slider.blockSignals(True)
            p_react_strength_slider.setValue(int(round(float(s.get("p_react_strength", 0.65)) * 100.0)))
            p_react_strength_slider.blockSignals(False)
        self._metric("p_max_label", f"Max Count ({int(s.get('p_max_count', 200))})")
        self._metric("p_spawn_label", f"Birth Rate ({int(s.get('p_spawn_rate', 100))})")
        self._metric("p_life_label", f"Lifetime ({float(s.get('p_lifetime', 1.6)):.2f}s)")
        self._metric("p_speed_label", f"Base Speed ({float(s.get('p_speed', 1.0)):.1f})")
        self._metric("p_react_label", f"Audio Reactivity ({float(s.get('p_reactivity', 0.1)):.2f})")
        self._metric("p_smoothing_label", f"Reaction Smoothness ({float(s.get('p_smoothing', 0.65)):.2f})")
        self._metric("p_size_label", f"Particle Size ({float(s.get('p_size', 2.0)):.1f})")
        self._metric("p_opacity_label", f"Opacity ({float(s.get('p_opacity', 0.35)):.2f})")
        self._metric("p_spawn_threshold_label", f"Spawn Threshold ({float(s.get('p_spawn_threshold', 0.15)):.2f})")
        self._metric("p_react_strength_label", f"React Strength ({float(s.get('p_react_strength', 0.65)):.2f})")

        # --- Vignette ---
        vignette_enabled = self._w("vignette_enabled")
        if vignette_enabled is not None:
            vignette_enabled.blockSignals(True)
            en = bool(s.get("vig_enabled", False))
            vignette_enabled.setChecked(en)
            vignette_enabled.blockSignals(False)
            self._sync_toggle_button(vignette_enabled, en)
        vignette_controls = self._w("vignette_controls")
        if vignette_controls is not None:
            vignette_controls.setVisible(bool(s.get("vig_enabled", False)))
        vignette_strength_slider = self._w("vignette_strength_slider")
        if vignette_strength_slider is not None:
            vignette_strength_slider.blockSignals(True)
            vignette_strength_slider.setValue(int(round(float(s.get("vig_strength", 0.35)) * 100.0)))
            vignette_strength_slider.blockSignals(False)
        vignette_feather_slider = self._w("vignette_feather_slider")
        if vignette_feather_slider is not None:
            vignette_feather_slider.blockSignals(True)
            vignette_feather_slider.setValue(int(round(float(s.get("vig_feather", 0.65)) * 100.0)))
            vignette_feather_slider.blockSignals(False)
        vignette_opacity_slider = self._w("vignette_opacity_slider")
        if vignette_opacity_slider is not None:
            vignette_opacity_slider.blockSignals(True)
            vignette_opacity_slider.setValue(int(round(float(s.get("vig_opacity", 0.65)) * 100.0)))
            vignette_opacity_slider.blockSignals(False)
        vignette_color_input = self._w("vignette_color_input")
        if vignette_color_input is not None:
            vignette_color_input.blockSignals(True)
            vignette_color_input.setText(str(s.get("vig_color", "#000000")))
            vignette_color_input.blockSignals(False)
        self._metric("vignette_strength_label", f"Strength ({float(s.get('vig_strength', 0.35)):.2f})")
        self._metric("vignette_feather_label", f"Feather ({float(s.get('vig_feather', 0.65)):.2f})")
        self._metric("vignette_opacity_label", f"Opacity ({float(s.get('vig_opacity', 0.65)):.2f})")

        # --- Smoke ---
        smoke_enabled = self._w("smoke_enabled")
        if smoke_enabled is not None:
            smoke_enabled.blockSignals(True)
            en = bool(s.get("smoke_enabled", False))
            smoke_enabled.setChecked(en)
            smoke_enabled.blockSignals(False)
            self._sync_toggle_button(smoke_enabled, en)
        smoke_controls = self._w("smoke_controls")
        if smoke_controls is not None:
            smoke_controls.setVisible(bool(s.get("smoke_enabled", False)))
        smoke_strength_slider = self._w("smoke_strength_slider")
        if smoke_strength_slider is not None:
            smoke_strength_slider.blockSignals(True)
            smoke_strength_slider.setValue(int(round(float(s.get("smoke_strength", 0.35)) * 100.0)))
            smoke_strength_slider.blockSignals(False)
        smoke_blur_slider = self._w("smoke_blur_slider")
        if smoke_blur_slider is not None:
            smoke_blur_slider.blockSignals(True)
            smoke_blur_slider.setValue(int(round(float(s.get("smoke_blur", 0.55)) * 100.0)))
            smoke_blur_slider.blockSignals(False)
        smoke_noise_slider = self._w("smoke_noise_slider")
        if smoke_noise_slider is not None:
            smoke_noise_slider.blockSignals(True)
            smoke_noise_slider.setValue(int(round(float(s.get("smoke_noise", 0.55)) * 100.0)))
            smoke_noise_slider.blockSignals(False)
        smoke_speed_slider = self._w("smoke_speed_slider")
        if smoke_speed_slider is not None:
            smoke_speed_slider.blockSignals(True)
            smoke_speed_slider.setValue(int(round(float(s.get("smoke_speed", 0.35)) * 100.0)))
            smoke_speed_slider.blockSignals(False)
        smoke_opacity_slider = self._w("smoke_opacity_slider")
        if smoke_opacity_slider is not None:
            smoke_opacity_slider.blockSignals(True)
            smoke_opacity_slider.setValue(int(round(float(s.get("smoke_opacity", 0.55)) * 100.0)))
            smoke_opacity_slider.blockSignals(False)
        smoke_color_input = self._w("smoke_color_input")
        if smoke_color_input is not None:
            smoke_color_input.blockSignals(True)
            smoke_color_input.setText(str(s.get("smoke_color", "#000000")))
            smoke_color_input.blockSignals(False)
        self._metric("smoke_strength_label", f"Strength ({float(s.get('smoke_strength', 0.35)):.2f})")
        self._metric("smoke_blur_label", f"Blur ({float(s.get('smoke_blur', 0.55)):.2f})")
        self._metric("smoke_noise_label", f"Noise ({float(s.get('smoke_noise', 0.55)):.2f})")
        self._metric("smoke_speed_label", f"Motion Speed ({float(s.get('smoke_speed', 0.35)):.2f})")
        self._metric("smoke_opacity_label", f"Opacity ({float(s.get('smoke_opacity', 0.55)):.2f})")

        # --- Particles extras ---
        p_variant_combo = self._w("p_variant_combo")
        if p_variant_combo is not None:
            p_variant_combo.blockSignals(True)
            p_variant_combo.setCurrentIndex(max(0, p_variant_combo.findData(str(s.get("p_variant", "classic")))))
            p_variant_combo.blockSignals(False)
        p_spawn_area_combo = self._w("p_spawn_area_combo")
        if p_spawn_area_combo is not None:
            p_spawn_area_combo.blockSignals(True)
            p_spawn_area_combo.setCurrentIndex(max(0, p_spawn_area_combo.findData(str(s.get("p_spawn_area", "centerRing")))))
            p_spawn_area_combo.blockSignals(False)
        p_size_jitter_slider = self._w("p_size_jitter_slider")
        if p_size_jitter_slider is not None:
            p_size_jitter_slider.blockSignals(True)
            p_size_jitter_slider.setValue(int(round(float(s.get("p_size_jitter", 0.0)) * 100.0)))
            p_size_jitter_slider.blockSignals(False)
        p_drift_slider = self._w("p_drift_slider")
        if p_drift_slider is not None:
            p_drift_slider.blockSignals(True)
            p_drift_slider.setValue(int(round(float(s.get("p_drift", 0.0)) * 100.0)))
            p_drift_slider.blockSignals(False)
        p_swirl_slider = self._w("p_swirl_slider")
        if p_swirl_slider is not None:
            p_swirl_slider.blockSignals(True)
            p_swirl_slider.setValue(int(round(float(s.get("p_swirl", 0.0)) * 100.0)))
            p_swirl_slider.blockSignals(False)
        self._metric("p_size_jitter_label", f"Size Variance ({float(s.get('p_size_jitter', 0.0)):.2f})")
        self._metric("p_drift_label", f"Drift ({float(s.get('p_drift', 0.0)):.2f})")
        self._metric("p_swirl_label", f"Swirl ({float(s.get('p_swirl', 0.0)):.2f})")

    def apply_overlay_settings(self, s: dict) -> None:
        """Apply logo and text overlay settings."""
        t = self._template_accessor()
        # --- Logo settings ---
        logo_enabled = self._w("logo_enabled")
        if logo_enabled is not None:
            logo_enabled.blockSignals(True)
            en = bool(s.get("logo_enabled", True))
            logo_enabled.setChecked(en)
            logo_enabled.blockSignals(False)
            self._sync_toggle_button(logo_enabled, en)
        logo_controls = self._w("logo_controls")
        if logo_controls is not None:
            logo_controls.setVisible(bool(s.get("logo_enabled", True)))
        logo_shape_combo = self._w("logo_shape_combo")
        if logo_shape_combo is not None:
            logo_shape_combo.blockSignals(True)
            logo_shape_combo.setCurrentIndex(0 if bool(s.get("logo_circle_mask", True)) else 1)
            logo_shape_combo.blockSignals(False)
        logo_size_slider = self._w("logo_size_slider")
        if logo_size_slider is not None:
            logo_size_slider.blockSignals(True)
            logo_size_slider.setValue(self._logo_real_size_to_slider_value(float(s.get("logo_size", 200))))
            logo_size_slider.blockSignals(False)
        logo_opacity_slider = self._w("logo_opacity_slider")
        if logo_opacity_slider is not None:
            logo_opacity_slider.blockSignals(True)
            logo_opacity_slider.setValue(int(round(float(s.get("logo_opacity", 1.0)) * 100.0)))
            logo_opacity_slider.blockSignals(False)
        logo_reactivity_slider = self._w("logo_reactivity_slider")
        if logo_reactivity_slider is not None:
            logo_reactivity_slider.blockSignals(True)
            logo_reactivity_slider.setValue(int(round(float(s.get("logo_reactivity", 0.0)) * 100.0)))
            logo_reactivity_slider.blockSignals(False)
        logo_smoothing_slider = self._w("logo_smoothing_slider")
        if logo_smoothing_slider is not None:
            logo_smoothing_slider.blockSignals(True)
            logo_smoothing_slider.setValue(int(round(float(s.get("logo_smoothing", 0.75)) * 100.0)))
            logo_smoothing_slider.blockSignals(False)
        logo_size_label = self._w("logo_size_label")
        if logo_size_label is not None:
            real_size = int(round(float(s.get("logo_size", 200))))
            slider_size = self._logo_real_size_to_slider_value(real_size)
            widget_factory.set_metric_text(logo_size_label, f"Size ({slider_size} => {real_size})")
        self._metric("logo_opacity_label", f"Opacity ({float(s.get('logo_opacity', 1.0)):.2f})")
        self._metric("logo_reactivity_label", f"Audio Reactivity ({float(s.get('logo_reactivity', 0.0)):.2f})")
        self._metric("logo_smoothing_label", f"Reaction Smoothness ({float(s.get('logo_smoothing', 0.75)):.2f})")
        logo_spin_enabled = self._w("logo_spin_enabled")
        if logo_spin_enabled is not None:
            logo_spin_enabled.blockSignals(True)
            spin_en = bool(s.get("logo_spin_enabled", False))
            logo_spin_enabled.setChecked(spin_en)
            logo_spin_enabled.blockSignals(False)
            self._sync_toggle_button(logo_spin_enabled, spin_en)
        logo_spin_controls = self._w("logo_spin_controls")
        if logo_spin_controls is not None:
            logo_spin_controls.setVisible(bool(s.get("logo_spin_enabled", False)))
        logo_spin_direction_combo = self._w("logo_spin_direction_combo")
        if logo_spin_direction_combo is not None:
            logo_spin_direction_combo.blockSignals(True)
            logo_spin_direction_combo.setCurrentIndex(max(0, logo_spin_direction_combo.findData(str(s.get("logo_spin_direction", "cw")))))
            logo_spin_direction_combo.blockSignals(False)
        logo_spin_speed_slider = self._w("logo_spin_speed_slider")
        if logo_spin_speed_slider is not None:
            logo_spin_speed_slider.blockSignals(True)
            logo_spin_speed_slider.setValue(int(round(float(s.get("logo_spin_speed", 0.0)))))
            logo_spin_speed_slider.blockSignals(False)
        self._metric("logo_spin_speed_label", f"Speed ({float(s.get('logo_spin_speed', 0.0)):.0f}\u00b0/s)")

        # --- Text overlays ---
        text_overlays = s.get("text_overlays", [])
        overlays_raw = t.get("textOverlays")
        overlays_fallback = overlays_raw if isinstance(overlays_raw, list) else []
        for i in range(5):
            o = text_overlays[i] if i < len(text_overlays) else {}
            if not o:
                o = overlays_fallback[i] if i < len(overlays_fallback) and isinstance(overlays_fallback[i], dict) else {}
                if isinstance(o, dict):
                    o = {
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
                    }
            en = bool(o.get("enabled", False)) if isinstance(o, dict) else False
            enabled_list = self._w("text_overlay_enabled")
            if isinstance(enabled_list, list) and i < len(enabled_list):
                cb = enabled_list[i]
                cb.blockSignals(True)
                cb.setChecked(en)
                cb.blockSignals(False)
                self._sync_toggle_button(cb, en)
            controls_list = self._w("text_overlay_controls")
            if isinstance(controls_list, list) and i < len(controls_list):
                controls_list[i].setVisible(en)
            if isinstance(o, dict):
                text_list = self._w("text_overlay_text")
                if isinstance(text_list, list) and i < len(text_list):
                    te = text_list[i]
                    te.blockSignals(True)
                    te.setPlainText(str(o.get("text", "")))
                    te.blockSignals(False)
                start_list = self._w("text_overlay_start")
                if isinstance(start_list, list) and i < len(start_list):
                    sp = start_list[i]
                    sp.blockSignals(True)
                    sp.setValue(int(round(float(o.get("start_sec", 0.0)))))
                    sp.blockSignals(False)
                duration_list = self._w("text_overlay_duration")
                if isinstance(duration_list, list) and i < len(duration_list):
                    sp = duration_list[i]
                    sp.blockSignals(True)
                    sp.setValue(int(round(float(o.get("duration_sec", 3.0)))))
                    sp.blockSignals(False)
                anchor_list = self._w("text_overlay_anchor")
                if isinstance(anchor_list, list) and i < len(anchor_list):
                    co = anchor_list[i]
                    co.blockSignals(True)
                    co.setCurrentIndex(max(0, co.findData(str(o.get("anchor", "top-left")))))
                    co.blockSignals(False)
                x_list = self._w("text_overlay_x_slider")
                if isinstance(x_list, list) and i < len(x_list):
                    x_list[i].blockSignals(True)
                    x_list[i].setValue(int(round(float(o.get("x", 24.0)))))
                    x_list[i].blockSignals(False)
                y_list = self._w("text_overlay_y_slider")
                if isinstance(y_list, list) and i < len(y_list):
                    y_list[i].blockSignals(True)
                    y_list[i].setValue(int(round(float(o.get("y", 24.0)))))
                    y_list[i].blockSignals(False)
                size_list = self._w("text_overlay_size_slider")
                if isinstance(size_list, list) and i < len(size_list):
                    size_list[i].blockSignals(True)
                    size_list[i].setValue(int(round(float(o.get("size_px", 46.0)))))
                    size_list[i].blockSignals(False)
                color_list = self._w("text_overlay_color")
                if isinstance(color_list, list) and i < len(color_list):
                    color_list[i].blockSignals(True)
                    color_list[i].setText(str(o.get("color", "#ffffff")))
                    color_list[i].blockSignals(False)
                stroke_color_list = self._w("text_overlay_stroke_color")
                if isinstance(stroke_color_list, list) and i < len(stroke_color_list):
                    stroke_color_list[i].blockSignals(True)
                    stroke_color_list[i].setText(str(o.get("stroke_color", "#000000")))
                    stroke_color_list[i].blockSignals(False)
                stroke_slider_list = self._w("text_overlay_stroke_slider")
                if isinstance(stroke_slider_list, list) and i < len(stroke_slider_list):
                    stroke_slider_list[i].blockSignals(True)
                    stroke_slider_list[i].setValue(int(round(float(o.get("stroke_width", 2.0)) * 10.0)))
                    stroke_slider_list[i].blockSignals(False)
                shadow_slider_list = self._w("text_overlay_shadow_slider")
                if isinstance(shadow_slider_list, list) and i < len(shadow_slider_list):
                    shadow_slider_list[i].blockSignals(True)
                    shadow_slider_list[i].setValue(int(round(float(o.get("shadow", 0.4)) * 100.0)))
                    shadow_slider_list[i].blockSignals(False)
                anim_list = self._w("text_overlay_anim")
                if isinstance(anim_list, list) and i < len(anim_list):
                    co = anim_list[i]
                    co.blockSignals(True)
                    co.setCurrentIndex(max(0, co.findData(str(o.get("animation", "fade")))))
                    co.blockSignals(False)
                x_label_list = self._w("text_overlay_x_label")
                if isinstance(x_label_list, list) and i < len(x_label_list):
                    widget_factory.set_metric_text(x_label_list[i], f"X Offset ({int(round(float(o.get('x', 24.0))))}px)")
                y_label_list = self._w("text_overlay_y_label")
                if isinstance(y_label_list, list) and i < len(y_label_list):
                    widget_factory.set_metric_text(y_label_list[i], f"Y Offset ({int(round(float(o.get('y', 24.0))))}px)")
                size_label_list = self._w("text_overlay_size_label")
                if isinstance(size_label_list, list) and i < len(size_label_list):
                    widget_factory.set_metric_text(size_label_list[i], f"Font Size ({int(round(float(o.get('size_px', 46.0))))}px)")
                stroke_label_list = self._w("text_overlay_stroke_label")
                if isinstance(stroke_label_list, list) and i < len(stroke_label_list):
                    widget_factory.set_metric_text(stroke_label_list[i], f"Stroke Width ({float(o.get('stroke_width', 2.0)):.1f})")
                shadow_label_list = self._w("text_overlay_shadow_label")
                if isinstance(shadow_label_list, list) and i < len(shadow_label_list):
                    widget_factory.set_metric_text(shadow_label_list[i], f"Shadow ({float(o.get('shadow', 0.4)):.2f})")

    def apply_layer_settings(self, s: dict) -> None:
        """Apply layer config (name, gravity, curved, mirrored, fill, dims, color)."""
        self._refresh_layer_selector()
        l0 = self._selected_layer()
        selected_idx = int(self._selected_layer_index) + 1
        layer_count = len(self._layers())
        layer_editing = self._w("layer_editing")
        if l0 and layer_editing is not None:
            layer_editing.setText(f"Editing Layer {selected_idx}/{layer_count}: {str(l0.get('name', 'Layer'))}")
        layer_name_input = self._w("layer_name_input")
        if l0 and layer_name_input is not None:
            layer_name_input.blockSignals(True)
            layer_name_input.setText(str(l0.get("name", f"Layer {selected_idx}")))
            layer_name_input.blockSignals(False)
        layer_gravity_combo = self._w("layer_gravity_combo")
        if l0 and layer_gravity_combo is not None:
            layer_gravity_combo.blockSignals(True)
            layer_gravity_combo.setCurrentIndex(max(0, layer_gravity_combo.findData(str(l0.get("gravity", "bottom")))))
            layer_gravity_combo.blockSignals(False)
        layer_curved_cb = self._w("layer_curved_cb")
        if l0 and layer_curved_cb is not None:
            layer_curved_cb.blockSignals(True)
            curved = bool(l0.get("curved", True))
            layer_curved_cb.setChecked(curved)
            layer_curved_cb.blockSignals(False)
            self._sync_toggle_button(layer_curved_cb, curved)
        layer_mirrored_cb = self._w("layer_mirrored_cb")
        if l0 and layer_mirrored_cb is not None:
            layer_mirrored_cb.blockSignals(True)
            mirrored = bool(l0.get("mirrored", True))
            layer_mirrored_cb.setChecked(mirrored)
            layer_mirrored_cb.blockSignals(False)
            self._sync_toggle_button(layer_mirrored_cb, mirrored)
        layer_fill_cb = self._w("layer_fill_cb")
        if l0 and layer_fill_cb is not None:
            layer_fill_cb.blockSignals(True)
            fill_circle = bool(l0.get("fillCircle", False))
            layer_fill_cb.setChecked(fill_circle)
            layer_fill_cb.blockSignals(False)
            self._sync_toggle_button(layer_fill_cb, fill_circle)
        layer_barwidth_slider = self._w("layer_barwidth_slider")
        if l0 and layer_barwidth_slider is not None:
            bw = int(round(float(l0.get("barWidth", 4.0))))
            layer_barwidth_slider.blockSignals(True)
            layer_barwidth_slider.setValue(bw)
            layer_barwidth_slider.blockSignals(False)
            self._metric("layer_barwidth_label", f"Bar Width ({bw})")
        layer_thickness_slider = self._w("layer_thickness_slider")
        if l0 and layer_thickness_slider is not None:
            th = int(round(float(l0.get("thickness", 30.0))))
            layer_thickness_slider.blockSignals(True)
            layer_thickness_slider.setValue(th)
            layer_thickness_slider.blockSignals(False)
            self._metric("layer_thickness_label", f"Spike Height ({th})")
        layer_radius_slider = self._w("layer_radius_slider")
        if l0 and layer_radius_slider is not None:
            ro = int(round(float(l0.get("radiusOffset", 0.0))))
            layer_radius_slider.blockSignals(True)
            layer_radius_slider.setValue(ro)
            layer_radius_slider.blockSignals(False)
            self._metric("layer_radius_label", f"Layer Gap ({ro})")
        layer_opacity_slider = self._w("layer_opacity_slider")
        if l0 and layer_opacity_slider is not None:
            op = float(l0.get("opacity", 1.0))
            op = float(max(0.0, min(1.0, op)))
            layer_opacity_slider.blockSignals(True)
            layer_opacity_slider.setValue(int(round(op * 100.0)))
            layer_opacity_slider.blockSignals(False)
            self._metric("layer_opacity_label", f"Opacity ({op:.2f})")
        layer_blend_combo = self._w("layer_blend_combo")
        if l0 and layer_blend_combo is not None:
            layer_blend_combo.blockSignals(True)
            layer_blend_combo.setCurrentIndex(max(0, layer_blend_combo.findData(str(l0.get("blend_mode", "normal")))))
            layer_blend_combo.blockSignals(False)
        layer_glow_slider = self._w("layer_glow_slider")
        if l0 and layer_glow_slider is not None:
            glow = int(round(float(l0.get("glow", 0.0))))
            layer_glow_slider.blockSignals(True)
            layer_glow_slider.setValue(glow)
            layer_glow_slider.blockSignals(False)
            self._metric("layer_glow_label", f"Glow Strength ({glow})")
        layer_blur_slider = self._w("layer_blur_slider")
        if l0 and layer_blur_slider is not None:
            blur = int(round(float(l0.get("blur", 0.0))))
            layer_blur_slider.blockSignals(True)
            layer_blur_slider.setValue(blur)
            layer_blur_slider.blockSignals(False)
            self._metric("layer_blur_label", f"Glow Softness ({blur})")

        col = l0.get("color") if isinstance(l0.get("color"), dict) else {}
        layer_color_mode = self._w("layer_color_mode")
        if layer_color_mode is not None:
            mode = str(col.get("mode", "solid"))
            layer_color_mode.blockSignals(True)
            layer_color_mode.setCurrentIndex(max(0, layer_color_mode.findData(mode)))
            layer_color_mode.blockSignals(False)
        layer_solid_widget = self._w("layer_solid_widget")
        layer_grad_widget = self._w("layer_grad_widget")
        if layer_solid_widget is not None and layer_grad_widget is not None:
            is_solid = str(col.get("mode", "solid")) == "solid"
            layer_solid_widget.setVisible(is_solid)
            layer_grad_widget.setVisible(not is_solid)
        layer_solid_input = self._w("layer_solid_input")
        if layer_solid_input is not None:
            layer_solid_input.blockSignals(True)
            layer_solid_input.setText(str(col.get("solidColor", "#ffffff")))
            layer_solid_input.blockSignals(False)
        layer_grad_dir = self._w("layer_grad_dir")
        if layer_grad_dir is not None:
            layer_grad_dir.blockSignals(True)
            layer_grad_dir.setCurrentIndex(max(0, layer_grad_dir.findData(str(col.get("gradientDirection", "left-to-right")))))
            layer_grad_dir.blockSignals(False)

    # ------------------------------------------------------------------
    # Update (UI controls -> template) — style / audio / position
    # ------------------------------------------------------------------
    def update_style(self) -> None:
        style_combo = self._w("style_combo")
        if style_combo is None:
            return
        v = style_combo.currentData()
        if not v:
            return
        t = self._template_accessor()
        t = _apply_style_preset_to_template(t, str(v), int(self._selected_layer_index))
        name_input = self._w("template_name_input")
        name_text = name_input.text() if name_input is not None else ""
        t["templateName"] = str(name_text or t.get("templateName", "My Template")).strip() or "My Template"
        self._commit(t)
        self.apply_template_to_controls()

    def update_spectrum_enabled(self) -> None:
        spectrum_enabled = self._w("spectrum_enabled")
        en = bool(spectrum_enabled.isChecked()) if spectrum_enabled is not None else True
        self._sync_toggle_button(spectrum_enabled, en)
        t = self._template_accessor()
        t["spectrumEnabled"] = bool(en)
        self._commit(t)

    def update_audio_sensitivity(self, v: int) -> None:
        t = self._template_accessor()
        s = float(v) / 100.0
        a = t.get("audioSettings", {}) if isinstance(t.get("audioSettings"), dict) else {}
        t["audioSettings"] = {**a, "sensitivity": s}
        self._metric("sens_label", f"Sensitivity ({s:.2f})")
        self._commit(t)

    def update_audio_smoothing(self, v: int) -> None:
        t = self._template_accessor()
        s = float(v) / 100.0
        a = t.get("audioSettings", {}) if isinstance(t.get("audioSettings"), dict) else {}
        t["audioSettings"] = {**a, "smoothing": s}
        self._metric("smooth_label", f"Smoothing ({s:.2f})")
        self._commit(t)

    def reset_center(self) -> None:
        t = self._template_accessor()
        t["position"] = {"anchor": "center", "x": 0, "y": 0}
        self._commit(t)
        self.apply_template_to_controls()

    def update_anchor(self) -> None:
        anchor_combo = self._w("anchor_combo")
        if anchor_combo is None:
            return
        v = anchor_combo.currentData()
        if not v:
            return
        t = self._template_accessor()
        t["position"] = {"anchor": str(v), "x": 0, "y": 0}
        self._commit(t)
        self.apply_template_to_controls()

    def update_pos_x(self, v: int) -> None:
        t = self._template_accessor()
        p = t.get("position", {}) if isinstance(t.get("position"), dict) else {}
        t["position"] = {**p, "x": int(v)}
        self._metric("x_label", f"X Offset ({int(v)})")
        self._commit(t)

    def update_pos_y(self, v: int) -> None:
        t = self._template_accessor()
        p = t.get("position", {}) if isinstance(t.get("position"), dict) else {}
        t["position"] = {**p, "y": int(v)}
        self._metric("y_label", f"Y Offset ({int(v)})")
        self._commit(t)

    # ------------------------------------------------------------------
    # Update — background
    # ------------------------------------------------------------------
    def update_bg_brightness(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "brightness": x}
        self._metric("bg_brightness_label", f"Brightness ({x:.2f})")
        self._commit(t)

    def update_bg_fit_mode(self) -> None:
        combo = self._w("bg_fit_mode_combo")
        mode = str(combo.currentData() or "cover") if combo is not None else "cover"
        if mode not in ("cover", "contain", "original"):
            mode = "cover"
        t = self._template_accessor()
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "fitMode": mode}
        self._commit(t)

    def update_bg_user_scale(self, v: int) -> None:
        pct = int(max(10, min(400, int(v))))
        scale = float(pct) / 100.0
        t = self._template_accessor()
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "userScale": scale}
        self._metric("bg_user_scale_label", f"Scale ({pct}%)")
        self._commit(t)
        self.apply_template_to_controls()

    def update_bg_edit_mode(self) -> None:
        bg_edit_mode = self._w("bg_edit_mode")
        en = bool(bg_edit_mode.isChecked()) if bg_edit_mode is not None else False
        self._sync_toggle_button(bg_edit_mode, en)
        self._bg_edit_mode = bool(en)
        preview = self._preview_accessor()
        try:
            if hasattr(preview, "set_bg_edit_mode"):
                preview.set_bg_edit_mode(bool(en))
        except Exception:
            pass

    def update_bg_reactivity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "reactivity": x}
        self._metric("bg_reactivity_label", f"Audio Reactivity ({x:.2f})")
        self._commit(t)

    def update_bg_smoothing(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "smoothing": x}
        self._metric("bg_smoothing_label", f"Reaction Smoothness ({x:.2f})")
        self._commit(t)

    def update_bg_motion_mode(self) -> None:
        combo = self._w("bg_motion_mode_combo")
        t = self._template_accessor()
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        mode = str(combo.currentData() or "none") if combo is not None else "none"
        if mode not in ("none", "zoom", "vibrate", "both"):
            mode = "none"
        t["backgroundSettings"] = {**bg, "motionMode": mode}
        self._sync_bg_motion_visibility()
        self._commit(t)

    def update_bg_motion_zoom(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "motionZoomStrength": x}
        self._metric("bg_motion_zoom_label", f"Zoom Strength ({x:.2f})")
        self._commit(t)

    def update_bg_motion_vibrate(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        bg = t.get("backgroundSettings", {}) if isinstance(t.get("backgroundSettings"), dict) else {}
        t["backgroundSettings"] = {**bg, "motionVibrateStrength": x}
        self._metric("bg_motion_vibrate_label", f"Vibrate Strength ({x:.2f})")
        self._commit(t)

    # ------------------------------------------------------------------
    # Update — logo
    # ------------------------------------------------------------------
    def update_logo_shape(self) -> None:
        combo = self._w("logo_shape_combo")
        v = combo.currentData() if combo is not None else None
        t = self._template_accessor()
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        t["logoSettings"] = {**ls, "circleMask": bool(v == "circle")}
        self._commit(t)

    def update_logo_size(self, v: int) -> None:
        t = self._template_accessor()
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        real_size = self._logo_size_slider_to_real_size(v)
        t["logoSettings"] = {**ls, "size": real_size}
        self._metric("logo_size_label", f"Size ({int(v)} => {real_size})")
        self._commit(t)

    def update_logo_opacity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        t["logoSettings"] = {**ls, "opacity": x}
        self._metric("logo_opacity_label", f"Opacity ({x:.2f})")
        self._commit(t)

    def update_logo_reactivity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        t["logoSettings"] = {**ls, "reactivity": x}
        self._metric("logo_reactivity_label", f"Audio Reactivity ({x:.2f})")
        self._commit(t)

    def update_logo_smoothing(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        t["logoSettings"] = {**ls, "smoothing": x}
        self._metric("logo_smoothing_label", f"Reaction Smoothness ({x:.2f})")
        self._commit(t)

    def update_logo_enabled(self) -> None:
        logo_enabled = self._w("logo_enabled")
        t = self._template_accessor()
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        en = bool(logo_enabled.isChecked()) if logo_enabled is not None else False
        self._sync_toggle_button(logo_enabled, en)
        t["logoSettings"] = {**ls, "enabled": en}
        logo_controls = self._w("logo_controls")
        if logo_controls is not None:
            logo_controls.setVisible(en)
        self._commit(t)

    def update_logo_spin_enabled(self) -> None:
        logo_spin_enabled = self._w("logo_spin_enabled")
        t = self._template_accessor()
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        en = bool(logo_spin_enabled.isChecked()) if logo_spin_enabled is not None else False
        self._sync_toggle_button(logo_spin_enabled, en)
        t["logoSettings"] = {**ls, "spinEnabled": en}
        logo_spin_controls = self._w("logo_spin_controls")
        if logo_spin_controls is not None:
            logo_spin_controls.setVisible(en)
        self._commit(t)

    def update_logo_spin_direction(self) -> None:
        combo = self._w("logo_spin_direction_combo")
        t = self._template_accessor()
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        d = str(combo.currentData() or "cw") if combo is not None else "cw"
        if d not in ("cw", "ccw"):
            d = "cw"
        t["logoSettings"] = {**ls, "spinDirection": d}
        self._commit(t)

    def update_logo_spin_speed(self, v: int) -> None:
        deg_s = float(max(0.0, min(720.0, float(v))))
        t = self._template_accessor()
        ls = t.get("logoSettings", {}) if isinstance(t.get("logoSettings"), dict) else {}
        t["logoSettings"] = {**ls, "spinSpeed": deg_s}
        self._metric("logo_spin_speed_label", f"Speed ({deg_s:.0f}\u00b0/s)")
        self._commit(t)

    # ------------------------------------------------------------------
    # Update — particles
    # ------------------------------------------------------------------
    def update_particles_enabled(self) -> None:
        particles_enabled = self._w("particles_enabled")
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        en = bool(particles_enabled.isChecked()) if particles_enabled is not None else False
        self._sync_toggle_button(particles_enabled, en)
        t["particlesSettings"] = {**ps, "enabled": en}
        particles_controls = self._w("particles_controls")
        if particles_controls is not None:
            particles_controls.setVisible(en)
        self._commit(t)

    def update_particles_max(self, v: int) -> None:
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "maxCount": int(v)}
        self._metric("p_max_label", f"Max Count ({int(v)})")
        self._commit(t)

    def update_particles_spawn(self, v: int) -> None:
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "spawnRate": int(v)}
        self._metric("p_spawn_label", f"Birth Rate ({int(v)})")
        self._commit(t)

    def update_particles_life(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "lifetimeSec": x}
        self._metric("p_life_label", f"Lifetime ({x:.2f}s)")
        self._commit(t)

    def update_particles_speed(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 10.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "speed": x}
        self._metric("p_speed_label", f"Base Speed ({x:.1f})")
        self._commit(t)

    def update_particles_reactivity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "reactivity": x}
        self._metric("p_react_label", f"Audio Reactivity ({x:.2f})")
        self._commit(t)

    def update_particles_smoothing(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "smoothing": x}
        self._metric("p_smoothing_label", f"Reaction Smoothness ({x:.2f})")
        self._commit(t)

    def update_particles_size(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 10.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "size": x}
        self._metric("p_size_label", f"Particle Size ({x:.1f})")
        self._commit(t)

    def update_particles_opacity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "opacity": x}
        self._metric("p_opacity_label", f"Opacity ({x:.2f})")
        self._commit(t)

    def update_particles_color(self) -> None:
        p_color_input = self._w("p_color_input")
        col = str(p_color_input.text() or "").strip() if p_color_input is not None else ""
        if not col:
            return
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "color": col}
        self._commit(t)

    def update_particles_spawn_mode(self) -> None:
        combo = self._w("p_spawn_mode_combo")
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        mode = str(combo.currentData() or "always") if combo is not None else "always"
        if mode not in ("always", "reactiveOnly"):
            mode = "always"
        t["particlesSettings"] = {**ps, "spawnMode": mode}
        self._commit(t)

    def update_particles_spawn_trigger(self) -> None:
        combo = self._w("p_spawn_trigger_combo")
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        trig = str(combo.currentData() or "both") if combo is not None else "both"
        if trig not in ("kick", "bass", "both"):
            trig = "both"
        t["particlesSettings"] = {**ps, "spawnTrigger": trig}
        self._commit(t)

    def update_particles_spawn_threshold(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "spawnThreshold": x}
        self._metric("p_spawn_threshold_label", f"Spawn Threshold ({x:.2f})")
        self._commit(t)

    def update_particles_style(self) -> None:
        combo = self._w("p_style_combo")
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        style = str(combo.currentData() or "dot") if combo is not None else "dot"
        if style not in ("dot", "glow", "ring", "spark", "bokeh"):
            style = "dot"
        t["particlesSettings"] = {**ps, "style": style}
        self._commit(t)

    def update_particles_react_color(self) -> None:
        p_react_color_input = self._w("p_react_color_input")
        col = str(p_react_color_input.text() or "").strip() if p_react_color_input is not None else ""
        if not col:
            return
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "reactColor": col}
        self._commit(t)

    def update_particles_react_strength(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "reactStrength": x}
        self._metric("p_react_strength_label", f"React Strength ({x:.2f})")
        self._commit(t)

    def update_particles_variant(self) -> None:
        combo = self._w("p_variant_combo")
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        v = str(combo.currentData() or "classic") if combo is not None else "classic"
        t["particlesSettings"] = {**ps, "variant": v}
        self._commit(t)

    def update_particles_spawn_area(self) -> None:
        combo = self._w("p_spawn_area_combo")
        t = self._template_accessor()
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        v = str(combo.currentData() or "centerRing") if combo is not None else "centerRing"
        t["particlesSettings"] = {**ps, "spawnArea": v}
        self._commit(t)

    def update_particles_size_jitter(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "sizeJitter": x}
        self._metric("p_size_jitter_label", f"Size Variance ({x:.2f})")
        self._commit(t)

    def update_particles_drift(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "drift": x}
        self._metric("p_drift_label", f"Drift ({x:.2f})")
        self._commit(t)

    def update_particles_swirl(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        ps = t.get("particlesSettings", {}) if isinstance(t.get("particlesSettings"), dict) else {}
        t["particlesSettings"] = {**ps, "swirl": x}
        self._metric("p_swirl_label", f"Swirl ({x:.2f})")
        self._commit(t)

    # ------------------------------------------------------------------
    # Update — vignette
    # ------------------------------------------------------------------
    def update_vignette_enabled(self) -> None:
        vignette_enabled = self._w("vignette_enabled")
        t = self._template_accessor()
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        en = bool(vignette_enabled.isChecked()) if vignette_enabled is not None else False
        self._sync_toggle_button(vignette_enabled, en)
        t["effects"] = {**fx, "vignette": {**vig, "enabled": en}}
        vignette_controls = self._w("vignette_controls")
        if vignette_controls is not None:
            vignette_controls.setVisible(en)
        self._commit(t)

    def update_vignette_strength(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        t["effects"] = {**fx, "vignette": {**vig, "strength": x}}
        self._metric("vignette_strength_label", f"Strength ({x:.2f})")
        self._commit(t)

    def update_vignette_feather(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        t["effects"] = {**fx, "vignette": {**vig, "feather": x}}
        self._metric("vignette_feather_label", f"Feather ({x:.2f})")
        self._commit(t)

    def update_vignette_opacity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        t["effects"] = {**fx, "vignette": {**vig, "opacity": x}}
        self._metric("vignette_opacity_label", f"Opacity ({x:.2f})")
        self._commit(t)

    def update_vignette_color(self) -> None:
        vignette_color_input = self._w("vignette_color_input")
        col = str(vignette_color_input.text() or "").strip() if vignette_color_input is not None else ""
        if not col:
            return
        t = self._template_accessor()
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        t["effects"] = {**fx, "vignette": {**vig, "color": col}}
        self._commit(t)

    # ------------------------------------------------------------------
    # Update — smoke
    # ------------------------------------------------------------------
    def update_smoke_enabled(self) -> None:
        smoke_enabled = self._w("smoke_enabled")
        t = self._template_accessor()
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        en = bool(smoke_enabled.isChecked()) if smoke_enabled is not None else False
        self._sync_toggle_button(smoke_enabled, en)
        t["effects"] = {**fx, "smoke": {**sm, "enabled": en}}
        smoke_controls = self._w("smoke_controls")
        if smoke_controls is not None:
            smoke_controls.setVisible(en)
        self._commit(t)

    def update_smoke_strength(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        t["effects"] = {**fx, "smoke": {**sm, "strength": x}}
        self._metric("smoke_strength_label", f"Strength ({x:.2f})")
        self._commit(t)

    def update_smoke_blur(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        t["effects"] = {**fx, "smoke": {**sm, "blur": x}}
        self._metric("smoke_blur_label", f"Blur ({x:.2f})")
        self._commit(t)

    def update_smoke_noise(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        t["effects"] = {**fx, "smoke": {**sm, "noise": x}}
        self._metric("smoke_noise_label", f"Noise ({x:.2f})")
        self._commit(t)

    def update_smoke_speed(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        t["effects"] = {**fx, "smoke": {**sm, "speed": x}}
        self._metric("smoke_speed_label", f"Motion Speed ({x:.2f})")
        self._commit(t)

    def update_smoke_opacity(self, v: int) -> None:
        t = self._template_accessor()
        x = float(v) / 100.0
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        t["effects"] = {**fx, "smoke": {**sm, "opacity": x}}
        self._metric("smoke_opacity_label", f"Opacity ({x:.2f})")
        self._commit(t)

    def update_smoke_color(self) -> None:
        smoke_color_input = self._w("smoke_color_input")
        col = str(smoke_color_input.text() or "").strip() if smoke_color_input is not None else ""
        if not col:
            return
        t = self._template_accessor()
        fx = t.get("effects", {}) if isinstance(t.get("effects"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        t["effects"] = {**fx, "smoke": {**sm, "color": col}}
        self._commit(t)

    # ------------------------------------------------------------------
    # Update — text overlays
    # ------------------------------------------------------------------
    def update_text_enabled(self, idx: int) -> None:
        enabled_list = self._w("text_overlay_enabled")
        if not (isinstance(enabled_list, list) and idx < len(enabled_list)):
            return
        cb = enabled_list[idx]
        en = bool(cb.isChecked())
        self._sync_toggle_button(cb, en)
        controls_list = self._w("text_overlay_controls")
        if isinstance(controls_list, list) and idx < len(controls_list):
            controls_list[idx].setVisible(en)
        self._set_text_overlay(idx, {"enabled": en})

    def update_text_content(self, idx: int) -> None:
        text_list = self._w("text_overlay_text")
        if not (isinstance(text_list, list) and idx < len(text_list)):
            return
        self._set_text_overlay(idx, {"text": str(text_list[idx].toPlainText() or "")})

    def update_text_start(self, idx: int) -> None:
        start_list = self._w("text_overlay_start")
        if not (isinstance(start_list, list) and idx < len(start_list)):
            return
        self._set_text_overlay(idx, {"startSec": float(start_list[idx].value())})

    def update_text_duration(self, idx: int) -> None:
        duration_list = self._w("text_overlay_duration")
        if not (isinstance(duration_list, list) and idx < len(duration_list)):
            return
        self._set_text_overlay(idx, {"durationSec": float(duration_list[idx].value())})

    def update_text_anchor(self, idx: int) -> None:
        anchor_list = self._w("text_overlay_anchor")
        if not (isinstance(anchor_list, list) and idx < len(anchor_list)):
            return
        self._set_text_overlay(idx, {"anchor": str(anchor_list[idx].currentData() or "top-left")})

    def update_text_x(self, idx: int, v: int) -> None:
        x_label_list = self._w("text_overlay_x_label")
        if isinstance(x_label_list, list) and idx < len(x_label_list):
            widget_factory.set_metric_text(x_label_list[idx], f"X Offset ({int(v)}px)")
        self._set_text_overlay(idx, {"x": float(v)})

    def update_text_y(self, idx: int, v: int) -> None:
        y_label_list = self._w("text_overlay_y_label")
        if isinstance(y_label_list, list) and idx < len(y_label_list):
            widget_factory.set_metric_text(y_label_list[idx], f"Y Offset ({int(v)}px)")
        self._set_text_overlay(idx, {"y": float(v)})

    def update_text_size(self, idx: int, v: int) -> None:
        size_label_list = self._w("text_overlay_size_label")
        if isinstance(size_label_list, list) and idx < len(size_label_list):
            widget_factory.set_metric_text(size_label_list[idx], f"Font Size ({int(v)}px)")
        self._set_text_overlay(idx, {"sizePx": float(v)})

    def update_text_color(self, idx: int) -> None:
        color_list = self._w("text_overlay_color")
        if not (isinstance(color_list, list) and idx < len(color_list)):
            return
        col = str(color_list[idx].text() or "").strip()
        if not col:
            return
        self._set_text_overlay(idx, {"color": col})

    def update_text_stroke_color(self, idx: int) -> None:
        stroke_color_list = self._w("text_overlay_stroke_color")
        if not (isinstance(stroke_color_list, list) and idx < len(stroke_color_list)):
            return
        col = str(stroke_color_list[idx].text() or "").strip()
        if not col:
            return
        self._set_text_overlay(idx, {"strokeColor": col})

    def update_text_stroke_width(self, idx: int, v: int) -> None:
        x = float(v) / 10.0
        stroke_label_list = self._w("text_overlay_stroke_label")
        if isinstance(stroke_label_list, list) and idx < len(stroke_label_list):
            widget_factory.set_metric_text(stroke_label_list[idx], f"Stroke Width ({x:.1f})")
        self._set_text_overlay(idx, {"strokeWidth": x})

    def update_text_shadow(self, idx: int, v: int) -> None:
        x = float(v) / 100.0
        shadow_label_list = self._w("text_overlay_shadow_label")
        if isinstance(shadow_label_list, list) and idx < len(shadow_label_list):
            widget_factory.set_metric_text(shadow_label_list[idx], f"Shadow ({x:.2f})")
        self._set_text_overlay(idx, {"shadow": x})

    def update_text_animation(self, idx: int) -> None:
        anim_list = self._w("text_overlay_anim")
        if not (isinstance(anim_list, list) and idx < len(anim_list)):
            return
        self._set_text_overlay(idx, {"animation": str(anim_list[idx].currentData() or "fade")})

    # ------------------------------------------------------------------
    # Update — layers
    # ------------------------------------------------------------------
    def update_layer_blend_mode(self) -> None:
        combo = self._w("layer_blend_combo")
        v = combo.currentData() if combo is not None else None
        if not v:
            return
        self._set_selected_layer({"blend_mode": str(v)})

    def update_layer_glow(self, v: int) -> None:
        self._metric("layer_glow_label", f"Glow Strength ({int(v)})")
        self._set_selected_layer({"glow": int(v)})

    def update_layer_blur(self, v: int) -> None:
        self._metric("layer_blur_label", f"Glow Softness ({int(v)})")
        self._set_selected_layer({"blur": int(v)})

    def update_layer_gravity(self) -> None:
        combo = self._w("layer_gravity_combo")
        v = combo.currentData() if combo is not None else None
        if not v:
            return
        self._set_selected_layer({"gravity": str(v)})

    def update_layer_curved(self) -> None:
        cb = self._w("layer_curved_cb")
        checked = bool(cb.isChecked()) if cb is not None else False
        self._sync_toggle_button(cb, checked)
        self._set_selected_layer({"curved": checked})

    def update_layer_mirrored(self) -> None:
        cb = self._w("layer_mirrored_cb")
        checked = bool(cb.isChecked()) if cb is not None else False
        self._sync_toggle_button(cb, checked)
        self._set_selected_layer({"mirrored": checked})

    def update_layer_fill_circle(self) -> None:
        cb = self._w("layer_fill_cb")
        checked = bool(cb.isChecked()) if cb is not None else False
        self._sync_toggle_button(cb, checked)
        self._set_selected_layer({"fillCircle": checked})

    def update_layer_bar_width(self, v: int) -> None:
        self._metric("layer_barwidth_label", f"Bar Width ({int(v)})")
        self._set_selected_layer({"barWidth": int(v)})

    def update_layer_thickness(self, v: int) -> None:
        self._metric("layer_thickness_label", f"Spike Height ({int(v)})")
        self._set_selected_layer({"thickness": int(v)})

    def update_layer_radius(self, v: int) -> None:
        self._metric("layer_radius_label", f"Layer Gap ({int(v)})")
        self._set_selected_layer({"radiusOffset": int(v)})

    def update_layer_opacity(self, v: int) -> None:
        x = float(v) / 100.0
        self._metric("layer_opacity_label", f"Opacity ({x:.2f})")
        self._set_selected_layer({"opacity": x})

    def update_layer_color_mode(self) -> None:
        combo = self._w("layer_color_mode")
        v = combo.currentData() if combo is not None else None
        if not v:
            return
        self._set_selected_layer_color({"mode": str(v)})

    def update_layer_solid_color_text(self) -> None:
        layer_solid_input = self._w("layer_solid_input")
        col = str(layer_solid_input.text() or "").strip() if layer_solid_input is not None else ""
        if col:
            self._set_selected_layer_color({"solidColor": col})

    def update_layer_grad_dir(self) -> None:
        combo = self._w("layer_grad_dir")
        v = combo.currentData() if combo is not None else None
        if not v:
            return
        self._set_selected_layer_color({"gradientDirection": str(v)})

    def update_layer_grad_preset(self) -> None:
        combo = self._w("layer_grad_preset")
        v = combo.currentData() if combo is not None else None
        if not v:
            return
        cols = str(v).split(",")
        self._set_selected_layer_color({"gradientColors": cols})
