"""AI Designer Engine v1 — rule-based scene composer (docs 05).

Edits Scene JSON only. Provider adapter allows swapping in an LLM later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from features.studio.lib.scene_document import apply_axis_patch, blank_studio_document, normalize_studio_document


@dataclass(frozen=True, slots=True)
class AiDesignerResult:
    document: dict[str, Any]
    explanation: str
    mode: str


class AiDesignerEngine:
    """Prompt → composition axes via keyword intent + asset heuristics."""

    def generate(self, prompt: str, *, base: dict[str, Any] | None = None) -> AiDesignerResult:
        text = str(prompt or "").strip()
        doc = normalize_studio_document(base) if base else blank_studio_document(name="AI Scene")
        intent = _detect_intent(text)
        patch = _patch_from_intent(intent)
        if intent.get("name"):
            patch["name"] = intent["name"]
        out = apply_axis_patch(doc, patch)
        explain = _explain(intent, patch)
        return AiDesignerResult(document=out, explanation=explain, mode="generate")

    def modify(self, prompt: str, doc: dict[str, Any]) -> AiDesignerResult:
        intent = _detect_intent(prompt)
        patch = _patch_from_intent(intent, modify=True)
        out = apply_axis_patch(doc, patch)
        return AiDesignerResult(document=out, explanation=_explain(intent, patch), mode="modify")

    def improve(self, doc: dict[str, Any]) -> AiDesignerResult:
        patch = {
            "compositionPostEffectsAppend": "bloom",
            "compositionCameraBehavior": "drift",
            "compositionBackgroundAtmosphere": "haze",
        }
        out = apply_axis_patch(doc, patch)
        return AiDesignerResult(
            document=out,
            explanation="Increased bloom, softened atmosphere, calmer camera drift.",
            mode="improve",
        )


def _detect_intent(prompt: str) -> dict[str, Any]:
    p = prompt.lower()
    intent: dict[str, Any] = {
        "energy": "medium",
        "palette": "cyberpunk",
        "shape": "circle",
        "material": "neon",
        "particles": "sparkles",
        "lighting": "lightning",
        "camera": "shake",
        "atmosphere": "fog",
        "motion": "ken_burns",
        "name": None,
    }
    if any(w in p for w in ("trap", "dark", "aggressive")):
        intent.update(energy="high", palette="monochrome", material="carbon", lighting="strobe_flash", camera="punch_in", atmosphere="void")
    if any(w in p for w in ("festival", "tomorrowland", "edm")):
        intent.update(energy="high", palette="cyberpunk", material="neon", lighting="lightning", particles="confetti", camera="shake", atmosphere="stars")
    if any(w in p for w in ("cinematic", "film", "epic")):
        intent.update(energy="low", palette="sunset", material="glass", lighting="god_rays", camera="dolly", atmosphere="fog", motion="slow_zoom")
    if any(w in p for w in ("lofi", "calm", "chill", "dreamy")):
        intent.update(energy="low", palette="ocean", material="ice", lighting="aura", camera="drift", atmosphere="mist", particles="dust")
    if "purple" in p or "neon" in p:
        intent.update(palette="cyberpunk", material="neon")
    if "rain" in p:
        intent["atmosphere"] = "rain"
    if "snow" in p:
        intent["atmosphere"] = "snow"
    if "bars" in p:
        intent["shape"] = "bars"
    # Short title from prompt
    cleaned = " ".join(prompt.strip().split()[:6]).strip()
    if cleaned:
        intent["name"] = cleaned[:48]
    return intent


def _patch_from_intent(intent: dict[str, Any], *, modify: bool = False) -> dict[str, Any]:
    patch = {
        "compositionColorPalette": intent["palette"],
        "compositionSpectrumShape": intent["shape"],
        "compositionSpectrumMaterial": intent["material"],
        "compositionSpectrumAnimation": "pulse" if intent["energy"] != "low" else "breathing",
        "compositionParticleType": intent["particles"],
        "compositionParticleBehavior": "pulse",
        "compositionLightingEffect": intent["lighting"],
        "compositionLightingTrigger": "bass",
        "compositionCameraBehavior": intent["camera"],
        "compositionBackgroundAtmosphere": intent["atmosphere"],
        "compositionBackgroundMotion": intent["motion"],
        "compositionPostEffects": ["bloom", "vignette"] if intent["energy"] != "low" else ["soft_diffusion", "vignette"],
        "compositionAudioMapping": {
            "lighting": "bass",
            "particles": "kick",
            "camera": "bass",
            "logo": "vocals",
        },
    }
    if modify and intent["energy"] == "high":
        patch["compositionPostEffectsAppend"] = "chromatic_aberration"
    return patch


def _explain(intent: dict[str, Any], patch: dict[str, Any]) -> str:
    return (
        f"Intent energy={intent.get('energy')}. "
        f"Palette={patch.get('compositionColorPalette')}, "
        f"spectrum={patch.get('compositionSpectrumShape')}/{patch.get('compositionSpectrumMaterial')}, "
        f"lighting={patch.get('compositionLightingEffect')}, "
        f"camera={patch.get('compositionCameraBehavior')}, "
        f"atmosphere={patch.get('compositionBackgroundAtmosphere')}."
    )
