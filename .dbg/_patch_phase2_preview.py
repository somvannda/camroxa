"""Patch preview_widget for Phase 2 contour + reflection."""
from __future__ import annotations

from pathlib import Path

path = Path("camxora_python/visualizer/preview_widget.py")
text = path.read_text(encoding="utf-8")

old_import = """from visualizer._spectrum_fast import (
    build_solid_band_strip_vertices,
    clamp_spectrum_bar_count,
    generate_points_curved,
    generate_points_linear,
    normalize_spectrum_gravity,
    resample_fft_bins,
    resolve_bar_pixel_width,
    resolve_curved_spectrum_basis,
    smooth_fft_envelope,
)"""
new_import = """from visualizer._spectrum_fast import (
    build_contour_wave_strips,
    build_solid_band_strip_vertices,
    clamp_spectrum_bar_count,
    generate_points_curved,
    generate_points_linear,
    mirror_spectrum_points_vertical,
    normalize_spectrum_gravity,
    resample_fft_bins,
    resolve_bar_pixel_width,
    resolve_curved_spectrum_basis,
    smooth_fft_envelope,
)"""
assert old_import in text, "import block missing"
text = text.replace(old_import, new_import)

old_wave = """                waveform_style = style_preset in ('aurora-ribbon', 'magma-ridge', 'plasma-bloom', 'soft-waveform', 'mountain', 'liquid', 'continuous-waveform')
                if curved and mirrored and waveform_style:
                    px_arr = np.concatenate([px_arr, px_arr[:1]])
                    py_arr = np.concatenate([py_arr, py_arr[:1]])
                    dx_arr = np.concatenate([dx_arr, dx_arr[:1]])
                    dy_arr = np.concatenate([dy_arr, dy_arr[:1]])
                base_total_length = radius * (np.pi * 2.0 if mirrored else np.pi) if curved else float(h * 0.8) if gravity in ('left', 'right') else float(w * 0.8)
                pass_specs: list[dict] = []
                if glow_strength > 0.0:
                    pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.14 + glow_strength * 0.22), 'bar_width': bar_width_px + (glow_softness * 1.8 + glow_strength * 18.0) * sf, 'spike_height': spike_height_px + (glow_softness * 2.2 + glow_strength * 22.0) * sf, 'fill_circle': False})
                    pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.08 + glow_strength * 0.15), 'bar_width': bar_width_px + (glow_softness * 3.0 + glow_strength * 32.0) * sf, 'spike_height': spike_height_px + (glow_softness * 3.4 + glow_strength * 34.0) * sf, 'fill_circle': False})
                pass_specs.append({'is_glow': False, 'alpha': layer_op, 'bar_width': bar_width_px, 'spike_height': spike_height_px, 'fill_circle': bool(sl.get('fillCircle', False))})
                for pass_cfg in pass_specs:"""

new_wave = """                contour_style = style_preset == 'contour-waves'
                waveform_style = style_preset in ('aurora-ribbon', 'magma-ridge', 'plasma-bloom', 'soft-waveform', 'mountain', 'liquid', 'continuous-waveform')
                ring_close_style = waveform_style or contour_style
                if curved and mirrored and ring_close_style:
                    px_arr = np.concatenate([px_arr, px_arr[:1]])
                    py_arr = np.concatenate([py_arr, py_arr[:1]])
                    dx_arr = np.concatenate([dx_arr, dx_arr[:1]])
                    dy_arr = np.concatenate([dy_arr, dy_arr[:1]])
                base_total_length = radius * (np.pi * 2.0 if mirrored else np.pi) if curved else float(h * 0.8) if gravity in ('left', 'right') else float(w * 0.8)
                reflection_enabled = bool(sl.get('reflectionEnabled', False))
                try:
                    reflection_opacity = float(sl.get('reflectionOpacity', 0.32) or 0.32)
                except (TypeError, ValueError):
                    reflection_opacity = 0.32
                reflection_opacity = float(max(0.05, min(0.85, reflection_opacity)))
                draw_variants: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]] = [
                    (px_arr, py_arr, dx_arr, dy_arr, 1.0)
                ]
                if reflection_enabled:
                    r_px, r_py, r_dx, r_dy = mirror_spectrum_points_vertical(px_arr, py_arr, dx_arr, dy_arr)
                    draw_variants.append((r_px, r_py, r_dx, r_dy, reflection_opacity))
                pass_specs: list[dict] = []
                if glow_strength > 0.0:
                    pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.14 + glow_strength * 0.22), 'bar_width': bar_width_px + (glow_softness * 1.8 + glow_strength * 18.0) * sf, 'spike_height': spike_height_px + (glow_softness * 2.2 + glow_strength * 22.0) * sf, 'fill_circle': False})
                    pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.08 + glow_strength * 0.15), 'bar_width': bar_width_px + (glow_softness * 3.0 + glow_strength * 32.0) * sf, 'spike_height': spike_height_px + (glow_softness * 3.4 + glow_strength * 34.0) * sf, 'fill_circle': False})
                pass_specs.append({'is_glow': False, 'alpha': layer_op, 'bar_width': bar_width_px, 'spike_height': spike_height_px, 'fill_circle': bool(sl.get('fillCircle', False))})
                for v_px, v_py, v_dx, v_dy, v_alpha_mul in draw_variants:
                  for pass_cfg in pass_specs:"""

assert old_wave in text, "wave block missing"
text = text.replace(old_wave, new_wave)

# Fix indented loop body references: first line after for pass_cfg
# The variant loop added extra indent requirement - instead keep same indent and assign locals.
# Revert to using px_arr names by copying variant into locals at start of pass loop.

text = text.replace(
    """                for v_px, v_py, v_dx, v_dy, v_alpha_mul in draw_variants:
                  for pass_cfg in pass_specs:
                    pass_bar_width_px = float(pass_cfg['bar_width'])
                    pass_spike_height_px = float(pass_cfg['spike_height'])
                    pass_alpha = float(max(0.0, min(1.0, float(pass_cfg['alpha']))))
""",
    """                for v_px, v_py, v_dx, v_dy, v_alpha_mul in draw_variants:
                  px_arr, py_arr, dx_arr, dy_arr = v_px, v_py, v_dx, v_dy
                  for pass_cfg in pass_specs:
                    # Skip expensive glow passes on the reflection copy.
                    if pass_cfg['is_glow'] and v_alpha_mul < 0.999:
                        continue
                    pass_bar_width_px = float(pass_cfg['bar_width'])
                    pass_spike_height_px = float(pass_cfg['spike_height'])
                    pass_alpha = float(max(0.0, min(1.0, float(pass_cfg['alpha']) * float(v_alpha_mul))))
""",
)

text = text.replace(
    "                    if curved and mirrored and waveform_style:\n                        val_arr = np.concatenate([val_arr, val_arr[:1]])",
    "                    if curved and mirrored and ring_close_style:\n                        val_arr = np.concatenate([val_arr, val_arr[:1]])",
)

old_if_wave = "                    if waveform_style:\n                        xs_o = np.zeros(nn, dtype=np.float32)"
new_if_wave = """                    if contour_style:
                        strips = build_contour_wave_strips(
                            px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                            line_count=5,
                            line_half_px=float(max(0.7, pass_bar_width_px * 0.45)),
                        )
                        for strip_i, strip_pos in enumerate(strips):
                            strip_nn = int(strip_pos.shape[0] // 2)
                            strip_alpha = float(max(0.0, min(1.0, pass_alpha * (0.45 + 0.55 * ((strip_i + 1) / max(1, len(strips)))))))
                            strip_cols = np.repeat(
                                build_spectrum_vertex_rgba(
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    count=strip_nn,
                                    alpha=strip_alpha,
                                ),
                                2,
                                axis=0,
                            )
                            if pass_cfg["is_glow"]:
                                strip_cols = dampen_spectrum_glow_rgba(strip_cols, strength=0.38)
                            strip_verts = np.column_stack([strip_pos, strip_cols]).astype(np.float32)
                            if strip_verts.nbytes > self.line_vbo.size:
                                self.line_vbo.orphan(size=strip_verts.nbytes)
                            self.line_vbo.write(strip_verts.tobytes())
                            self.vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(strip_pos.shape[0]))
                    elif waveform_style:
                        xs_o = np.zeros(nn, dtype=np.float32)"""
assert old_if_wave in text, "waveform if missing"
text = text.replace(old_if_wave, new_if_wave)

path.write_text(text, encoding="utf-8")
print("preview_widget patched")
