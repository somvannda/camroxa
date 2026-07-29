from __future__ import annotations

import re
from pathlib import Path

p = Path("camxora_python/visualizer/gpu_render.py")
text = p.read_text(encoding="utf-8")

old1 = """            start_angle_pre, radial_sign_pre = resolve_curved_spectrum_basis(gravity_pre)
            if curved_pre:
                draw_radius_pre = resolve_inward_draw_radius(
                    radius_pre, thickness_pre, radial_sign_pre
                )
                px_pre, py_pre, dx_pre, dy_pre = generate_points_curved(
                    n_pre, draw_radius_pre, mirrored_pre, start_angle_pre, radial_sign_pre
                )
"""
new1 = """            start_angle_pre, growth_dx_pre, growth_dy_pre = resolve_curved_spectrum_basis(gravity_pre)
            if curved_pre:
                px_pre, py_pre, dx_pre, dy_pre = generate_points_curved(
                    n_pre, radius_pre, mirrored_pre, start_angle_pre, growth_dx_pre, growth_dy_pre
                )
"""
assert old1 in text, "old1 missing"
text = text.replace(old1, new1)

pat2 = re.compile(
    r"start_angle, radial_sign = resolve_curved_spectrum_basis\(gravity\)\s*\n"
    r"\s*if curved:\s*\n"
    r"\s*draw_radius = resolve_inward_draw_radius\(radius, thickness, radial_sign\)\s*\n"
    r"\s*px_arr, py_arr, dx_arr, dy_arr = generate_points_curved\(\s*\n"
    r"\s*n, draw_radius, mirrored, start_angle, radial_sign\s*\n"
    r"\s*\)\s*\n"
    r'\s*if gravity in \("bottom", "top"\):\s*\n'
    r"\s*sampled_fft = \(\s*\n"
    r"\s*sampled_fft \* rabbit_ear_length_multipliers\(px_arr, py_arr\)\s*\n"
    r"\s*\)\.astype\(np\.float32\)\s*\n"
    r"\s*else:\s*\n"
    r"\s*px_arr, py_arr, dx_arr, dy_arr = generate_points_linear\(n, total_length, gravity\)"
)
new2 = """start_angle, growth_dx, growth_dy = resolve_curved_spectrum_basis(gravity)
            
            if curved:
                px_arr, py_arr, dx_arr, dy_arr = generate_points_curved(
                    n, radius, mirrored, start_angle, growth_dx, growth_dy
                )
            else:
                px_arr, py_arr, dx_arr, dy_arr = generate_points_linear(n, total_length, gravity)"""
assert pat2.search(text), "pat2 missing"
text = pat2.sub(new2, text, count=1)

text = text.replace(
    'allow_fill_circle = bool(sl.get("fillCircle", False)) and float(radial_sign) >= 0.0',
    'allow_fill_circle = bool(sl.get("fillCircle", False))',
)
text = text.replace(
    'gravity_pre = str(sl_pre.get("gravity", "normal")).lower().strip()',
    'gravity_pre = normalize_spectrum_gravity(sl_pre.get("gravity", "top"))',
)
text = text.replace(
    'gravity = str(sl.get("gravity", "normal")).lower().strip()',
    'gravity = normalize_spectrum_gravity(sl.get("gravity", "top"))',
)

pat3 = re.compile(
    r"start_angle, radial_sign = resolve_curved_spectrum_basis\(gravity\)\s*\n"
    r"\s*draw_radius = resolve_inward_draw_radius\(radius, thickness, radial_sign\) if curved else radius"
)
new3 = (
    "start_angle, growth_dx, growth_dy = resolve_curved_spectrum_basis(gravity)\n"
    "            draw_radius = radius"
)
assert len(pat3.findall(text)) == 2, pat3.findall(text)
text = pat3.sub(new3, text)

pat4 = re.compile(
    r"dx_arr\[i\] = np\.cos\(angle\) \* radial_sign\s*\n"
    r"\s*dy_arr\[i\] = np\.sin\(angle\) \* radial_sign"
)
new4 = "dx_arr[i] = growth_dx\n                    dy_arr[i] = growth_dy"
assert len(pat4.findall(text)) == 2, len(pat4.findall(text))
text = pat4.sub(new4, text)

text = text.replace('if gravity in ("normal", "top"):', 'if gravity == "top":')

assert "resolve_inward_draw_radius" not in text
assert "rabbit_ear" not in text
assert "radial_sign" not in text

p.write_text(text, encoding="utf-8")
print("gpu_render patched ok")
