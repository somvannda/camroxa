from __future__ import annotations

import json
import os
import uuid
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


PNG_1X1 = bytes.fromhex(
    "89504E470D0A1A0A"
    "0000000D49484452000000010000000108060000001F15C489"
    "0000000D49444154789C63F8FFFF3F030008FC02FEA78D5A1D"
    "0000000049454E44AE426082"
)


def _soft_particles(*, enabled: bool = True, colors: list[str] | None = None) -> dict:
    palette = colors or ["#ffffff", "#a78bfa", "#22d3ee"]
    return {
        "enabled": bool(enabled),
        "maxCount": 900 if enabled else 200,
        "spawnRate": 180 if enabled else 50,
        "lifetimeSec": 2.2,
        "speed": 6.5,
        "reactivity": 0.55,
        "smoothing": 0.72,
        "size": 3.2,
        "sizeJitter": 0.35,
        "drift": 0.18,
        "swirl": 0.22,
        "spawnArea": "centerRing",
        "variant": "soft",
        "opacity": 0.42 if enabled else 0.0,
        "color": palette[0],
        "colorMode": "palette",
        "paletteColors": palette,
        "spawnMode": "reactiveOnly",
        "spawnTrigger": "both",
        "spawnThreshold": 0.22,
        "reactColor": palette[-1],
        "reactStrength": 0.7,
        "style": "glow",
    }


def _default_template() -> dict:
    return {
        "templateName": "Untitled",
        "style": "orbit-spikes",
        "spectrumEnabled": True,
        "layers": [
            {
                "id": "base-layer",
                "name": "Base Ring",
                "curved": True,
                "mirrored": True,
                "fillCircle": False,
                "solidBand": False,
                "thickness": 36.0,
                "barWidth": 5.0,
                "barCount": 64,
                "radiusOffset": 0.0,
                "gravity": "normal",
                "color": {
                    "mode": "gradient",
                    "solidColor": "#ffffff",
                    "gradientColors": ["#ffffff", "#ff4fd8", "#22d3ee"],
                    "gradientDirection": "left-to-right",
                },
                "glow": 24.0,
                "blur": 8.0,
                "rotation": 0.0,
                "blend_mode": "normal",
                "opacity": 1.0,
                "peakCapsEnabled": False,
                "peakCapColor": "#ffffff",
                "peakCapGap": 4.0,
                "peakCapThickness": 3.0,
                "peakCapDecay": 0.92,
            }
        ],
        "audioSettings": {
            "inputGain": 1.55,
            "barHeight": 1.35,
            "bandContrast": 1.45,
            "transientFocus": 1.25,
            "kickImpact": 1.15,
            "bassEmphasis": 1.4,
            "trebleShimmer": 1.15,
            "peakHoldBlend": 0.7,
            "motionSmoothing": 0.76,
            "sensitivity": 1.15,
            "smoothing": 0.78,
        },
        "position": {"anchor": "center", "x": 0, "y": 0},
        "previewBindings": {"spectrumAttachToLogo": False, "spectrumLogoGap": 18.0},
        "particlesSettings": _soft_particles(enabled=False),
        "effects": {
            "vignette": {
                "enabled": True,
                "strength": 0.42,
                "feather": 0.7,
                "color": "#000000",
                "opacity": 0.55,
            },
            "smoke": {
                "enabled": False,
                "strength": 0.35,
                "blur": 0.55,
                "noise": 0.55,
                "speed": 0.35,
                "color": "#000000",
                "opacity": 0.55,
            },
        },
    }


def _phase1_templates() -> list[dict]:
    # Dense needle crown with vivid multi-stop ring + soft cyan/magenta particles.
    t1 = _default_template()
    t1["templateName"] = "Prism Needle Crown"
    t1["style"] = "signal-needles"
    t1["layers"][0].update(
        {
            "name": "Needle Ring",
            "barCount": 112,
            "barWidth": 2.4,
            "thickness": 68.0,
            "glow": 28.0,
            "blur": 7.0,
            "solidBand": True,
            "peakCapsEnabled": True,
            "peakCapColor": "#f8fafc",
            "peakCapGap": 2.0,
            "peakCapThickness": 2.2,
            "peakCapDecay": 0.95,
            "opacity": 1.0,
            "blend_mode": "normal",
        }
    )
    t1["layers"][0]["color"].update(
        {
            "gradientColors": ["#ff006e", "#ffbe0b", "#8338ec", "#3a86ff", "#06d6a0"],
            "gradientDirection": "left-to-right",
        }
    )
    t1["particlesSettings"] = _soft_particles(
        enabled=True,
        colors=["#ffffff", "#ff006e", "#3a86ff", "#06d6a0"],
    )

    # Soft capsule orbit: thicker bars, richer aurora palette, glow particles.
    t2 = _default_template()
    t2["templateName"] = "Capsule Orbit Glow"
    t2["style"] = "drift-capsules"
    t2["layers"][0].update(
        {
            "name": "Capsule Ring",
            "barCount": 64,
            "barWidth": 10.0,
            "thickness": 42.0,
            "glow": 42.0,
            "blur": 12.0,
            "solidBand": True,
            "peakCapsEnabled": True,
            "peakCapColor": "#e0f2fe",
            "peakCapGap": 3.5,
            "peakCapThickness": 3.5,
            "peakCapDecay": 0.93,
            "opacity": 0.96,
            "blend_mode": "normal",
        }
    )
    t2["layers"][0]["color"].update(
        {
            "gradientColors": ["#fdf4ff", "#f0abfc", "#c084fc", "#67e8f9", "#38bdf8"],
            "gradientDirection": "left-to-right",
        }
    )
    t2["particlesSettings"] = _soft_particles(
        enabled=True,
        colors=["#fdf4ff", "#f0abfc", "#67e8f9"],
    )

    # Premium bottom equalizer: ribbon mountain + neon secondary layer (no grey cloud).
    t3 = _default_template()
    t3["templateName"] = "Linear Peak Matrix"
    t3["style"] = "magma-ridge"
    t3["layers"] = [
        {
            "id": "matrix-base",
            "name": "Base Ridge",
            "curved": False,
            "mirrored": False,
            "fillCircle": False,
            "solidBand": True,
            "thickness": 86.0,
            "barWidth": 14.0,
            "barCount": 72,
            "radiusOffset": 0.0,
            "gravity": "bottom",
            "color": {
                "mode": "gradient",
                "solidColor": "#ffffff",
                "gradientColors": ["#4c1d95", "#7c3aed", "#ec4899", "#f97316"],
                "gradientDirection": "top-to-bottom",
            },
            "glow": 26.0,
            "blur": 8.0,
            "rotation": 0.0,
            "blend_mode": "normal",
            "opacity": 1.0,
            "peakCapsEnabled": True,
            "peakCapColor": "#fff7ed",
            "peakCapGap": 4.0,
            "peakCapThickness": 3.0,
            "peakCapDecay": 0.94,
        },
        {
            "id": "matrix-needles",
            "name": "Peak Needles",
            "curved": False,
            "mirrored": False,
            "fillCircle": False,
            "solidBand": False,
            "thickness": 108.0,
            "barWidth": 3.0,
            "barCount": 96,
            "radiusOffset": 0.0,
            "gravity": "bottom",
            "color": {
                "mode": "gradient",
                "solidColor": "#ffffff",
                "gradientColors": ["#22d3ee", "#a855f7", "#fb7185"],
                "gradientDirection": "left-to-right",
            },
            "glow": 18.0,
            "blur": 4.0,
            "rotation": 0.0,
            "blend_mode": "add",
            "opacity": 0.78,
            "peakCapsEnabled": True,
            "peakCapColor": "#ffffff",
            "peakCapGap": 2.5,
            "peakCapThickness": 2.0,
            "peakCapDecay": 0.96,
        },
    ]
    t3["position"] = {"anchor": "bottom-center", "x": 0, "y": -40}
    t3["particlesSettings"] = _soft_particles(enabled=False)
    t3["effects"]["vignette"].update({"enabled": True, "strength": 0.5, "opacity": 0.62})

    # Magma core: filled core + outer ridge + warm particles (no sparse grey dots).
    t4 = _default_template()
    t4["templateName"] = "Magma Core Halo"
    t4["style"] = "magma-ridge"
    t4["layers"] = [
        {
            "id": "core-band",
            "name": "Core Band",
            "curved": True,
            "mirrored": True,
            "fillCircle": True,
            "solidBand": True,
            "thickness": 48.0,
            "barWidth": 12.0,
            "barCount": 80,
            "radiusOffset": 0.0,
            "gravity": "normal",
            "color": {
                "mode": "gradient",
                "solidColor": "#ffffff",
                "gradientColors": ["#fff7ed", "#fb7185", "#a855f7", "#38bdf8"],
                "gradientDirection": "left-to-right",
            },
            "glow": 40.0,
            "blur": 12.0,
            "rotation": 0.0,
            "blend_mode": "normal",
            "opacity": 0.95,
            "peakCapsEnabled": False,
            "peakCapColor": "#ffffff",
            "peakCapGap": 4.0,
            "peakCapThickness": 3.0,
            "peakCapDecay": 0.92,
        },
        {
            "id": "outer-caps",
            "name": "Outer Caps",
            "curved": True,
            "mirrored": True,
            "fillCircle": False,
            "solidBand": False,
            "thickness": 64.0,
            "barWidth": 4.5,
            "barCount": 108,
            "radiusOffset": 24.0,
            "gravity": "normal",
            "color": {
                "mode": "gradient",
                "solidColor": "#ffffff",
                "gradientColors": ["#fb7185", "#f59e0b", "#fde68a"],
                "gradientDirection": "left-to-right",
            },
            "glow": 28.0,
            "blur": 8.0,
            "rotation": 0.0,
            "blend_mode": "add",
            "opacity": 0.85,
            "peakCapsEnabled": True,
            "peakCapColor": "#fef3c7",
            "peakCapGap": 2.5,
            "peakCapThickness": 2.8,
            "peakCapDecay": 0.95,
        },
    ]
    t4["particlesSettings"] = _soft_particles(
        enabled=True,
        colors=["#fff7ed", "#fb7185", "#f59e0b", "#38bdf8"],
    )
    return [t1, t2, t3, t4]


def _upsert_templates(path: Path, templates: list[dict]) -> int:
    existing = []
    if path.is_file():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                existing = [item for item in parsed if isinstance(item, dict)]
        except Exception:
            existing = []

    by_name = {str(item.get("name") or ""): item for item in existing}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    for template in templates:
        name = str(template.get("templateName") or "Untitled Template")
        record = {
            "id": str(uuid.uuid4()),
            "name": name,
            "source": "user",
            "template": deepcopy(template),
            "updated_at": now,
        }
        prev = by_name.get(name)
        if prev:
            record["id"] = str(prev.get("id") or record["id"])
            record["source"] = str(prev.get("source") or "user")
        by_name[name] = record
    merged = list(by_name.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return len(templates)


def _write_ready_pack(base_dir: Path, template: dict) -> None:
    name = str(template.get("templateName") or "Template").strip()
    slug = name.lower().replace(" ", "-")
    out_dir = base_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "description": "Phase 1 spectrum style template (retuned)",
        "version": "1.1.0",
        "author": "Camxora Local",
        "kind": "video",
        "tags": ["spectrum", "phase1", "visualizer"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "template.json").write_text(json.dumps(template, indent=2), encoding="utf-8")
    (out_dir / "preview.png").write_bytes(PNG_1X1)
    zip_path = out_dir / f"{slug}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_dir / "manifest.json", arcname="manifest.json")
        zf.write(out_dir / "template.json", arcname="template.json")
        zf.write(out_dir / "preview.png", arcname="preview.png")


def main() -> None:
    localapp = Path(os.environ.get("LOCALAPPDATA", ""))
    if not localapp:
        raise RuntimeError("LOCALAPPDATA is not set")
    camxora = localapp / "Camxora"
    templates = _phase1_templates()

    catalog_paths: list[Path] = []
    users_dir = camxora / "users"
    if users_dir.is_dir():
        for user_dir in users_dir.iterdir():
            if user_dir.is_dir():
                catalog_paths.append(user_dir / "video-templates.json")
    if not catalog_paths:
        catalog_paths.append(camxora / "video-templates.json")

    for path in catalog_paths:
        _upsert_templates(path, templates)

    ready_dir = camxora / "ready-templates" / "phase1-spectrum"
    for tpl in templates:
        _write_ready_pack(ready_dir, tpl)

    print(f"Updated catalogs: {len(catalog_paths)}")
    for path in catalog_paths:
        print(path)
    print(f"Templates upserted per catalog: {len(templates)}")
    print(f"Ready packs folder: {ready_dir}")


if __name__ == "__main__":
    main()
