"""Multi-Spectrum instances — independent spectrum stacks (like lightning bolts).

Each instance owns: style, position, attach/gap, audio knobs, and an inner
``layers[]`` ring stack. Legacy templates with only top-level ``layers`` migrate
to a single instance; instance[0] is mirrored back for packs / old readers.
"""

from __future__ import annotations

import copy
from typing import Any

_MAX_SPECTRUM_INSTANCES = 8

_DEFAULT_AUDIO: dict[str, float] = {
    "inputGain": 1.0,
    "barHeight": 1.0,
    "bandContrast": 1.0,
    "transientFocus": 1.0,
    "kickImpact": 0.0,
    "bassEmphasis": 1.0,
    "trebleShimmer": 1.0,
    "peakHoldBlend": 0.0,
    "motionSmoothing": 0.8,
    "flyingGlowWingMotionSpeed": 1.0,
    "flyingGlowWingRelease": 0.9,
}


def _read_float(src: dict[str, Any], key: str, default: float, lo: float, hi: float) -> float:
    raw = src.get(key, default)
    if raw is None:
        raw = default
    try:
        return float(max(lo, min(hi, float(raw))))
    except (TypeError, ValueError):
        return float(default)


def _clone_layers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(copy.deepcopy(item))
    return out


def _coerce_audio_settings(audio_in: Any) -> dict[str, float]:
    """Normalize instance/legacy audio; map sensitivity→inputGain, smoothing→motionSmoothing."""
    src = audio_in if isinstance(audio_in, dict) else {}
    aliased = dict(src)
    if aliased.get("inputGain") is None and aliased.get("sensitivity") is not None:
        aliased["inputGain"] = aliased.get("sensitivity")
    if aliased.get("motionSmoothing") is None and aliased.get("smoothing") is not None:
        aliased["motionSmoothing"] = aliased.get("smoothing")
    audio = dict(_DEFAULT_AUDIO)
    for key, default in _DEFAULT_AUDIO.items():
        audio[key] = _read_float(aliased, key, default, -100.0, 100.0)
    # Keep legacy aliases so preview/export paths that still read sensitivity/smoothing work.
    audio["sensitivity"] = float(audio["inputGain"])
    audio["smoothing"] = float(max(0.0, min(0.99, audio["motionSmoothing"])))
    return audio


def _heal_empty_instance_layers(
    instances: list[dict[str, Any]],
    *,
    fallback_layers: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Fill empty instance ring stacks from fallback (usually top-level template.layers)."""
    fallback = _clone_layers(fallback_layers)
    if not instances or not fallback:
        return instances
    out: list[dict[str, Any]] = []
    for inst in instances:
        item = dict(inst) if isinstance(inst, dict) else {}
        if not _clone_layers(item.get("layers")):
            item["layers"] = _clone_layers(fallback)
        out.append(item)
    return out


def default_spectrum_instance(*, index: int = 1, layers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": f"spectrum-{index}",
        "name": f"Spectrum {index}",
        "enabled": True,
        "style": "orbit-spikes",
        "anchor": "center",
        "x": 0.0,
        "y": 0.0,
        "spectrumAttachToLogo": True,
        "spectrumLogoGap": 0.0,
        "audioSettings": _coerce_audio_settings(_DEFAULT_AUDIO),
        "layers": _clone_layers(layers) if layers else [],
    }


def normalize_spectrum_instance(raw: Any, *, index: int = 0) -> dict[str, Any]:
    base = default_spectrum_instance(index=index + 1)
    src = raw if isinstance(raw, dict) else {}
    pos = src.get("position") if isinstance(src.get("position"), dict) else {}
    audio = _coerce_audio_settings(src.get("audioSettings"))

    x = src.get("x", pos.get("x", 0.0))
    y = src.get("y", pos.get("y", 0.0))
    anchor = str(src.get("anchor") or pos.get("anchor") or "center").strip() or "center"

    layers = _clone_layers(src.get("layers"))
    if not layers:
        layers = _clone_layers(base.get("layers"))

    from features.video.lib.video_template_draft import normalize_spectrum_preset_key

    style = normalize_spectrum_preset_key(str(src.get("style") or base["style"]))
    return {
        "id": str(src.get("id") or base["id"]),
        "name": str(src.get("name") or base["name"]),
        "enabled": bool(src.get("enabled", True)),
        "style": style or "orbit-spikes",
        "anchor": anchor,
        "x": _read_float({"x": x}, "x", 0.0, -1000.0, 1000.0),
        "y": _read_float({"y": y}, "y", 0.0, -1000.0, 1000.0),
        "spectrumAttachToLogo": bool(src.get("spectrumAttachToLogo", True)),
        "spectrumLogoGap": _read_float(src, "spectrumLogoGap", 0.0, 0.0, 200.0),
        "audioSettings": audio,
        "layers": layers,
    }


def migrate_legacy_spectrum_to_instances(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Build instances from ``spectrumInstances`` or wrap legacy top-level spectrum fields."""
    raw = template.get("spectrumInstances")
    legacy_layers = _clone_layers(template.get("layers"))
    if isinstance(raw, list) and raw:
        out = [
            normalize_spectrum_instance(item, index=i)
            for i, item in enumerate(raw)
            if isinstance(item, dict)
        ][:_MAX_SPECTRUM_INSTANCES]
        if out:
            return _heal_empty_instance_layers(out, fallback_layers=legacy_layers)

    pos = template.get("position") if isinstance(template.get("position"), dict) else {}
    preview = template.get("previewBindings") if isinstance(template.get("previewBindings"), dict) else {}
    audio = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
    inst = normalize_spectrum_instance(
        {
            "id": "spectrum-1",
            "name": "Spectrum 1",
            "enabled": True,
            "style": template.get("style") or "orbit-spikes",
            "anchor": pos.get("anchor") or "center",
            "x": pos.get("x", 0.0),
            "y": pos.get("y", 0.0),
            "spectrumAttachToLogo": bool(preview.get("spectrumAttachToLogo", True)),
            "spectrumLogoGap": preview.get("spectrumLogoGap", 0.0),
            "audioSettings": audio,
            "layers": legacy_layers,
        },
        index=0,
    )
    return [inst]


def normalize_spectrum_instances(raw: Any, *, template: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    fallback_layers = _clone_layers(template.get("layers")) if isinstance(template, dict) else []
    if isinstance(raw, list) and raw:
        out = [
            normalize_spectrum_instance(item, index=i)
            for i, item in enumerate(raw)
            if isinstance(item, dict)
        ][:_MAX_SPECTRUM_INSTANCES]
        if out:
            return _heal_empty_instance_layers(out, fallback_layers=fallback_layers)
    if isinstance(template, dict):
        return migrate_legacy_spectrum_to_instances(template)
    return [normalize_spectrum_instance(default_spectrum_instance(index=1), index=0)]


def mirror_spectrum_instance0_to_legacy(template: dict[str, Any], instances: list[dict[str, Any]]) -> dict[str, Any]:
    """Write instance[0] (or first enabled) into legacy top-level spectrum fields."""
    if not instances:
        return template
    existing_layers = _clone_layers(template.get("layers"))
    healed = _heal_empty_instance_layers(list(instances), fallback_layers=existing_layers)
    primary = healed[0]
    for item in healed:
        if bool(item.get("enabled", True)):
            primary = item
            break
    preview = template.get("previewBindings") if isinstance(template.get("previewBindings"), dict) else {}
    template["style"] = str(primary.get("style") or "orbit-spikes")
    template["position"] = {
        "anchor": str(primary.get("anchor") or "center"),
        "x": float(primary.get("x", 0.0) or 0.0),
        "y": float(primary.get("y", 0.0) or 0.0),
    }
    template["previewBindings"] = {
        **preview,
        "spectrumAttachToLogo": bool(primary.get("spectrumAttachToLogo", True)),
        "spectrumLogoGap": float(primary.get("spectrumLogoGap", 0.0) or 0.0),
    }
    audio = _coerce_audio_settings(primary.get("audioSettings"))
    template["audioSettings"] = audio
    primary_layers = _clone_layers(primary.get("layers"))
    # Never wipe a healthy top-level stack with an empty primary.
    template["layers"] = primary_layers if primary_layers else existing_layers
    if primary_layers:
        for i, item in enumerate(healed):
            if item is primary or (isinstance(item, dict) and item.get("id") == primary.get("id")):
                healed[i] = {**item, "layers": primary_layers}
                break
    elif existing_layers:
        for i, item in enumerate(healed):
            if not _clone_layers(item.get("layers")):
                healed[i] = {**item, "layers": _clone_layers(existing_layers)}
    template["spectrumInstances"] = [normalize_spectrum_instance(i, index=n) for n, i in enumerate(healed)]
    return template


def iter_render_spectrum_instances(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalized enabled instances for preview/export (legacy → one instance)."""
    instances = normalize_spectrum_instances(template.get("spectrumInstances"), template=template)
    enabled = [inst for inst in instances if bool(inst.get("enabled", True))]
    # If every enabled instance somehow has empty rings, fall back to a legacy wrap.
    if enabled and not any(_clone_layers(inst.get("layers")) for inst in enabled):
        legacy = migrate_legacy_spectrum_to_instances(
            {**template, "spectrumInstances": None}
        )
        enabled = [inst for inst in legacy if bool(inst.get("enabled", True))]
    return enabled


def project_instance_to_draft_fields(instance: dict[str, Any]) -> dict[str, Any]:
    """Map an instance into the flat draft keys SpectrumInspector already binds."""
    audio = _coerce_audio_settings(instance.get("audioSettings"))
    return {
        "style": str(instance.get("style") or "orbit-spikes"),
        "anchor": str(instance.get("anchor") or "center"),
        "positionX": float(instance.get("x", 0.0) or 0.0),
        "positionY": float(instance.get("y", 0.0) or 0.0),
        "spectrumAttachToLogo": bool(instance.get("spectrumAttachToLogo", True)),
        "spectrumLogoGap": float(instance.get("spectrumLogoGap", 0.0) or 0.0),
        "audioInputGain": float(audio.get("inputGain", 1.0)),
        "audioBarHeight": float(audio.get("barHeight", 1.0)),
        "audioBandContrast": float(audio.get("bandContrast", 1.0)),
        "audioTransientFocus": float(audio.get("transientFocus", 1.0)),
        "audioKickImpact": float(audio.get("kickImpact", 0.0)),
        "audioBassEmphasis": float(audio.get("bassEmphasis", 1.0)),
        "audioTrebleShimmer": float(audio.get("trebleShimmer", 1.0)),
        "audioPeakHoldBlend": float(audio.get("peakHoldBlend", 0.0)),
        "audioMotionSmoothing": float(audio.get("motionSmoothing", 0.8)),
        "flyingGlowWingMotionSpeed": float(audio.get("flyingGlowWingMotionSpeed", 1.0)),
        "flyingGlowWingRelease": float(audio.get("flyingGlowWingRelease", 0.9)),
    }


def apply_draft_fields_to_instance(instance: dict[str, Any], draft_patch: dict[str, Any]) -> dict[str, Any]:
    """Write flat draft spectrum keys into an instance (partial patch OK)."""
    out = normalize_spectrum_instance(instance)
    audio = dict(out.get("audioSettings") or _DEFAULT_AUDIO)
    mapping = {
        "audioInputGain": "inputGain",
        "audioBarHeight": "barHeight",
        "audioBandContrast": "bandContrast",
        "audioTransientFocus": "transientFocus",
        "audioKickImpact": "kickImpact",
        "audioBassEmphasis": "bassEmphasis",
        "audioTrebleShimmer": "trebleShimmer",
        "audioPeakHoldBlend": "peakHoldBlend",
        "audioMotionSmoothing": "motionSmoothing",
        "flyingGlowWingMotionSpeed": "flyingGlowWingMotionSpeed",
        "flyingGlowWingRelease": "flyingGlowWingRelease",
    }
    for draft_key, audio_key in mapping.items():
        if draft_key in draft_patch:
            try:
                audio[audio_key] = float(draft_patch[draft_key])
            except (TypeError, ValueError):
                pass
    if "style" in draft_patch:
        out["style"] = str(draft_patch.get("style") or out["style"])
    if "anchor" in draft_patch:
        out["anchor"] = str(draft_patch.get("anchor") or out["anchor"])
    if "positionX" in draft_patch:
        out["x"] = float(draft_patch["positionX"])
    if "positionY" in draft_patch:
        out["y"] = float(draft_patch["positionY"])
    if "spectrumAttachToLogo" in draft_patch:
        out["spectrumAttachToLogo"] = bool(draft_patch["spectrumAttachToLogo"])
    if "spectrumLogoGap" in draft_patch:
        try:
            out["spectrumLogoGap"] = float(draft_patch["spectrumLogoGap"])
        except (TypeError, ValueError):
            pass
    out["audioSettings"] = audio
    return normalize_spectrum_instance(out)


def instance_position_dict(instance: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor": str(instance.get("anchor") or "center"),
        "x": float(instance.get("x", 0.0) or 0.0),
        "y": float(instance.get("y", 0.0) or 0.0),
    }
