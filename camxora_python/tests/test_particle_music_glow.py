"""Music-note particle style + neon glow."""

from __future__ import annotations

from features.video.lib.particle_music_icons import MUSIC_ICON_COUNT, build_music_icon_atlas
from features.video.lib.particle_settings import PARTICLE_STYLE_OPTIONS
from features.video.lib.video_template_draft import build_particle_settings_state
from features.video.lib.video_template_save import build_particles_template_patch
from visualizer_video.gpu_render import _resolve_particle_style_index
from visualizer_video.template_runtime import default_renderer_template, normalize_renderer_template


def test_music_style_registered() -> None:
    values = [value for value, _label in PARTICLE_STYLE_OPTIONS]
    assert "music" in values
    assert _resolve_particle_style_index("classic", "music") == 5


def test_music_icon_atlas_shape() -> None:
    atlas, count = build_music_icon_atlas()
    assert count == MUSIC_ICON_COUNT
    assert atlas.ndim == 3
    assert atlas.shape[2] == 4
    assert atlas.shape[1] == atlas.shape[0] * count
    assert int(atlas[:, :, 3].max()) > 0


def test_particles_glow_draft_roundtrip() -> None:
    template = normalize_renderer_template(default_renderer_template())
    template["particlesSettings"] = {
        **dict(template.get("particlesSettings") or {}),
        "style": "music",
        "glow": 0.7,
    }
    draft = build_particle_settings_state(template)
    assert draft["particlesStyle"] == "music"
    assert abs(float(draft["particlesGlow"]) - 0.7) < 1e-6
    patch = build_particles_template_patch(template, draft)
    ps = patch["particlesSettings"]
    assert ps["style"] == "music"
    assert abs(float(ps["glow"]) - 0.7) < 1e-6


def test_normalize_accepts_music_and_glow() -> None:
    out = normalize_renderer_template(
        {
            **default_renderer_template(),
            "particlesSettings": {"style": "music", "glow": 1.5},
        }
    )
    ps = out["particlesSettings"]
    assert ps["style"] == "music"
    assert float(ps["glow"]) == 1.0
