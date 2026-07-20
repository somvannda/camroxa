"""GPU spectrum bar renderer for export (REQ-2.3 slice 1–2).

Uploads smoothed FFT bins as a 1D R32F texture and expands bar quads in the
vertex shader via instanced draw. Default bars plus most slice-2 bar variants;
``pulse-beads`` / ``dot-matrix`` (variable quads) and waveforms stay on CPU.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import moderngl
import numpy as np

from ._spectrum_fast import _BINS

WAVEFORM_SPECTRUM_STYLES = frozenset(
    {
        "aurora-ribbon",
        "magma-ridge",
        "plasma-bloom",
        "soft-waveform",
        "mountain",
        "liquid",
        "continuous-waveform",
    }
)

# Bar styles with non-default CPU geometry — slice 2.
SPECIAL_BAR_STYLES_SLICE2 = frozenset(
    {
        "pulse-beads",
        "dot-matrix",
        "mirror-blades",
        "symmetrical-bars",
        "drift-capsules",
        "floating-blocks",
        "grid-steps",
        "pixel-bars",
        "signal-needles",
        "thin-lines",
        "ignition-flare",
        "neon-pulse",
    }
)

# Slice-2 styles on the GPU instanced path (single quad per bar).
# pulse-beads / dot-matrix need multi-quad expansion → remain CPU.
SPECIAL_BAR_STYLES_GPU_READY = frozenset(
    {
        "thin-lines",
        "signal-needles",
        "grid-steps",
        "pixel-bars",
        "mirror-blades",
        "symmetrical-bars",
        "drift-capsules",
        "floating-blocks",
        "ignition-flare",
        "neon-pulse",
    }
)

# Vertex shader style_mode values (must match GLSL).
_STYLE_MODE_DEFAULT = 0
_STYLE_MODE_MIRROR = 1
_STYLE_MODE_DRIFT = 2

_CORNER_INDICES = np.array([0.0, 1.0, 2.0, 0.0, 2.0, 3.0], dtype=np.float32)


def gpu_spectrum_enabled() -> bool:
    """Return True when export should use the GPU bar spectrum path."""
    return str(os.environ.get("CAMXORA_GPU_SPECTRUM", "0")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def normalize_spectrum_style_key(style: str) -> str:
    return str(style or "orbit-spikes").lower().strip()


def is_waveform_spectrum_style(style: str) -> bool:
    return normalize_spectrum_style_key(style) in WAVEFORM_SPECTRUM_STYLES


def is_gpu_bar_style_slice1(style: str) -> bool:
    """True for bar styles handled by the GPU path (slice 1 + GPU-ready slice 2)."""
    key = normalize_spectrum_style_key(style)
    if key in WAVEFORM_SPECTRUM_STYLES:
        return False
    if key in SPECIAL_BAR_STYLES_SLICE2 and key not in SPECIAL_BAR_STYLES_GPU_READY:
        return False
    return True


def gpu_bar_style_mode(style: str) -> int:
    """Return GLSL ``style_mode`` for GPU-ready bar variants."""
    key = normalize_spectrum_style_key(style)
    if key in {"mirror-blades", "symmetrical-bars"}:
        return _STYLE_MODE_MIRROR
    if key in {"drift-capsules", "floating-blocks"}:
        return _STYLE_MODE_DRIFT
    return _STYLE_MODE_DEFAULT


def gpu_bar_half_width_scale(style: str) -> float:
    """Width scale vs default bars for GPU-ready slice-2 styles."""
    key = normalize_spectrum_style_key(style)
    if key in {"thin-lines", "signal-needles"}:
        return 0.28
    if key in {"ignition-flare", "neon-pulse"}:
        return 1.2
    return 1.0


def quantize_fft_for_gpu_bar_style(
    style: str,
    render_fft: np.ndarray,
    *,
    thickness: float,
    sf: float,
) -> np.ndarray:
    """Quantize FFT magnitudes for grid-steps / pixel-bars (matches CPU path)."""
    key = normalize_spectrum_style_key(style)
    if key not in {"grid-steps", "pixel-bars"}:
        return render_fft
    src = np.asarray(render_fft, dtype=np.float32)
    thick = float(max(1e-6, thickness))
    step_px = float(max(1.0, 20.0 * float(sf)))
    # CPU path quantizes ``h_val = fft * thickness``; invert after ceil.
    h_val = np.maximum(2.0, src * thick)
    h_q = np.ceil(h_val / step_px) * step_px
    return (h_q / thick).astype(np.float32)


def pack_fft_r32_texture(values: np.ndarray, *, count: int = _BINS) -> bytes:
    """Pack FFT magnitudes into R32F texel bytes for a ``count``-wide 1D texture."""
    out = np.zeros(int(max(1, count)), dtype=np.float32)
    src = np.asarray(values, dtype=np.float32).reshape(-1)
    n = min(int(out.shape[0]), int(src.shape[0]))
    if n > 0:
        out[:n] = src[:n]
    return out.tobytes()


def unpack_fft_r32_texture(data: bytes, *, count: int = _BINS) -> np.ndarray:
    """Decode ``pack_fft_r32_texture`` output (for unit tests)."""
    arr = np.frombuffer(data, dtype=np.float32)
    want = int(max(1, count))
    if arr.shape[0] < want:
        padded = np.zeros(want, dtype=np.float32)
        padded[: arr.shape[0]] = arr
        return padded
    return arr[:want].copy()


def pack_color_rgba_texture(colors: np.ndarray, *, count: int = _BINS) -> bytes:
    """Pack per-bar RGBA colors into a ``count`` x 1 RGBA32F texture."""
    out = np.zeros((int(max(1, count)), 4), dtype=np.float32)
    src = np.asarray(colors, dtype=np.float32)
    if src.ndim == 1:
        src = src.reshape(1, -1)
    n = min(int(out.shape[0]), int(src.shape[0]))
    if n > 0:
        if src.shape[1] >= 4:
            out[:n] = src[:n, :4]
        elif src.shape[1] == 3:
            out[:n, :3] = src[:n, :3]
            out[:n, 3] = 1.0
    return out.tobytes()


@dataclass
class _GpuPassResources:
    color_tex: moderngl.Texture
    pass_thickness: float
    bar_half_width: float
    alpha: float


@dataclass
class _GpuLayerResources:
    instance_vbo: moderngl.Buffer
    passes: list[_GpuPassResources] = field(default_factory=list)
    bar_count: int = _BINS


class SpectrumGpuRenderer:
    """Instanced bar spectrum draw helper for ``run_gpu_render``."""

    def __init__(self, ctx: moderngl.Context) -> None:
        self._ctx = ctx
        self._prog = self._compile_program()
        self._corner_vbo = ctx.buffer(_CORNER_INDICES.tobytes())
        self._fft_tex = ctx.texture((_BINS, 1), 1, dtype="f4")
        self._fft_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._fft_tex.repeat_x = False
        self._fft_tex.repeat_y = False
        self._layers: dict[int, _GpuLayerResources] = {}
        self._layer_vaos: dict[int, moderngl.VertexArray] = {}

    def _compile_program(self) -> moderngl.Program:
        vs = """
        #version 330
        in float in_corner;
        in vec4 in_bar;

        uniform sampler2D tex_fft;
        uniform float pass_thickness;
        uniform vec2 bar_center_px;
        uniform vec2 out_size_px;
        uniform float bar_half_width;
        uniform int style_mode;   // 0 default, 1 mirror, 2 drift
        uniform float style_sf;

        flat out int v_bar_idx;

        vec2 corner_default(vec2 px_py, vec2 dx_dy, float h_val, float wx, float wy, int corner) {
            vec2 p0 = px_py + vec2(-wx, -wy);
            vec2 p1 = px_py + vec2(wx, wy);
            vec2 p2 = px_py + dx_dy * h_val + vec2(wx, wy);
            vec2 p3 = px_py + dx_dy * h_val + vec2(-wx, -wy);
            if (corner == 0) return p0;
            if (corner == 1) return p1;
            if (corner == 2) return p2;
            return p3;
        }

        vec2 corner_mirror(vec2 px_py, vec2 dx_dy, float h_val, float wx, float wy, int corner) {
            float half_h = h_val * 0.5;
            vec2 p0 = px_py - dx_dy * half_h + vec2(-wx, -wy);
            vec2 p1 = px_py - dx_dy * half_h + vec2(wx, wy);
            vec2 p2 = px_py + dx_dy * half_h + vec2(wx, wy);
            vec2 p3 = px_py + dx_dy * half_h + vec2(-wx, -wy);
            if (corner == 0) return p0;
            if (corner == 1) return p1;
            if (corner == 2) return p2;
            return p3;
        }

        vec2 corner_drift(vec2 px_py, vec2 dx_dy, float h_val, float wx, float wy, int corner) {
            float sf = max(style_sf, 0.001);
            float off1 = h_val + 20.0 * sf;
            float off2 = h_val + 30.0 * sf;
            vec2 p0 = px_py + dx_dy * off1 + vec2(-wx, -wy);
            vec2 p1 = px_py + dx_dy * off1 + vec2(wx, wy);
            vec2 p2 = px_py + dx_dy * off2 + vec2(wx, wy);
            vec2 p3 = px_py + dx_dy * off2 + vec2(-wx, -wy);
            if (corner == 0) return p0;
            if (corner == 1) return p1;
            if (corner == 2) return p2;
            return p3;
        }

        void main() {
            v_bar_idx = gl_InstanceID;
            float fft_val = texelFetch(tex_fft, ivec2(v_bar_idx, 0), 0).r;
            float h_val = max(2.0, fft_val * pass_thickness);
            int corner = int(in_corner + 0.5);
            // Match CPU: wx = -dy * half_w, wy = dx * half_w
            float half = bar_half_width;
            float wxv = -in_bar.w * half;
            float wyv = in_bar.z * half;
            vec2 local;
            if (style_mode == 1) {
                local = corner_mirror(in_bar.xy, in_bar.zw, h_val, wxv, wyv, corner);
            } else if (style_mode == 2) {
                local = corner_drift(in_bar.xy, in_bar.zw, h_val, wxv, wyv, corner);
            } else {
                local = corner_default(in_bar.xy, in_bar.zw, h_val, wxv, wyv, corner);
            }
            vec2 px = bar_center_px + local;
            vec2 ndc = px / out_size_px * 2.0 - 1.0;
            gl_Position = vec4(ndc, 0.0, 1.0);
        }
        """
        fs = """
        #version 330
        uniform sampler2D tex_colors;
        uniform int clip_enabled;
        uniform vec2 clip_center_px;
        uniform float clip_radius_px;
        flat in int v_bar_idx;
        out vec4 frag;
        void main() {
            if (clip_enabled == 1) {
                vec2 d = gl_FragCoord.xy - clip_center_px;
                if (length(d) > clip_radius_px) discard;
            }
            frag = texelFetch(tex_colors, ivec2(v_bar_idx, 0), 0);
        }
        """
        return self._ctx.program(vertex_shader=vs, fragment_shader=fs)

    def register_layer(
        self,
        layer_key: int,
        *,
        px: np.ndarray,
        py: np.ndarray,
        dx: np.ndarray,
        dy: np.ndarray,
        pass_specs: list[dict],
        pass_colors: list[np.ndarray],
    ) -> bool:
        """Upload static bar layout + per-pass color textures. Returns False if invalid."""
        n = int(min(len(px), len(py), len(dx), len(dy), _BINS))
        if n <= 0:
            return False
        instance = np.column_stack(
            [
                px[:n].astype(np.float32),
                py[:n].astype(np.float32),
                dx[:n].astype(np.float32),
                dy[:n].astype(np.float32),
            ]
        )
        instance_vbo = self._ctx.buffer(instance.tobytes())
        passes: list[_GpuPassResources] = []
        for idx, spec in enumerate(pass_specs):
            cols = pass_colors[idx] if idx < len(pass_colors) else pass_colors[-1]
            color_tex = self._ctx.texture((n, 1), 4, pack_color_rgba_texture(cols, count=n), dtype="f4")
            color_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            color_tex.repeat_x = False
            color_tex.repeat_y = False
            passes.append(
                _GpuPassResources(
                    color_tex=color_tex,
                    pass_thickness=float(spec.get("thickness", 30.0)),
                    bar_half_width=float(spec.get("bar_half_width", 2.0)),
                    alpha=float(spec.get("alpha", 1.0)),
                )
            )
        layer = _GpuLayerResources(instance_vbo=instance_vbo, passes=passes, bar_count=n)
        self._layers[layer_key] = layer
        self._layer_vaos[layer_key] = self._ctx.vertex_array(
            self._prog,
            [
                (self._corner_vbo, "1f", "in_corner"),
                (instance_vbo, "4f/i", "in_bar"),
            ],
        )
        return True

    def draw_pass(
        self,
        layer_key: int,
        pass_index: int,
        render_fft: np.ndarray,
        *,
        cx: float,
        cy: float,
        w: int,
        h: int,
        pass_thickness: float | None = None,
        bar_half_width: float | None = None,
        style_mode: int = 0,
        style_sf: float = 1.0,
    ) -> None:
        layer = self._layers.get(layer_key)
        vao = self._layer_vaos.get(layer_key)
        if layer is None or vao is None:
            return
        if pass_index < 0 or pass_index >= len(layer.passes):
            return
        pass_res = layer.passes[pass_index]
        thickness = float(pass_res.pass_thickness if pass_thickness is None else pass_thickness)
        half_w = float(pass_res.bar_half_width if bar_half_width is None else bar_half_width)

        self._fft_tex.write(pack_fft_r32_texture(render_fft, count=_BINS))
        self._fft_tex.use(location=0)
        pass_res.color_tex.use(location=1)

        self._prog["tex_fft"].value = 0
        self._prog["tex_colors"].value = 1
        self._prog["pass_thickness"].value = float(thickness)
        self._prog["bar_center_px"].value = (float(cx), float(cy))
        self._prog["out_size_px"].value = (float(max(1, w)), float(max(1, h)))
        self._prog["bar_half_width"].value = float(half_w)
        self._prog["style_mode"].value = int(style_mode)
        self._prog["style_sf"].value = float(max(0.001, style_sf))
        self._prog["clip_enabled"].value = 0
        self._prog["clip_center_px"].value = (0.0, 0.0)
        self._prog["clip_radius_px"].value = 0.0

        vao.render(moderngl.TRIANGLES, instances=int(layer.bar_count))

    def release(self) -> None:
        for layer in self._layers.values():
            layer.instance_vbo.release()
            for p in layer.passes:
                p.color_tex.release()
        self._layers.clear()
        self._layer_vaos.clear()
        self._corner_vbo.release()
        self._fft_tex.release()
        self._prog.release()
