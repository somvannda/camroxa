"""Composition Engine V1 — scene graph + fail-closed loader."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

COMPOSITION_SCHEMA_ID = "camxora.composition"
COMPOSITION_DOC_VERSION = 1
NONE = "none"

SCENE_OBJECTS: tuple[str, ...] = (
    "background",
    "spectrum",
    "logo",
    "text",
    "particles",
    "lighting",
    "camera",
    "audio",
    "overlay",
)


class CompositionContractError(ValueError):
    """Raised when a document is not a valid composition-engine scene."""


def default_composition() -> dict[str, Any]:
    return {
        "version": COMPOSITION_DOC_VERSION,
        "colorPalette": None,
        "background": {"image": None, "motion": "static", "atmosphere": NONE},
        "spectrum": {"shape": NONE, "material": NONE, "animation": NONE},
        "logo": {"enabled": True, "animation": NONE},
        "text": {"enabled": False},
        "overlay": {"enabled": False, "animation": NONE, "items": []},
        "particles": {"type": NONE, "behavior": NONE},
        "lighting": {"effect": NONE, "trigger": NONE},
        "camera": {"behavior": NONE},
        "postProcessing": {"effects": []},
        "audio": {"mapping": {}},
    }


def default_assets() -> dict[str, Any]:
    return {"backgroundImage": None, "logo": None, "audio": None}


def default_document() -> dict[str, Any]:
    return {
        "schema": COMPOSITION_SCHEMA_ID,
        "version": COMPOSITION_DOC_VERSION,
        "composition": default_composition(),
        "assets": default_assets(),
    }


def _nonempty(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def normalize_composition(raw: Any) -> dict[str, Any]:
    base = default_composition()
    if not isinstance(raw, dict):
        return base
    out = deepcopy(base)
    try:
        version = int(raw.get("version", COMPOSITION_DOC_VERSION))
    except (TypeError, ValueError):
        version = COMPOSITION_DOC_VERSION
    out["version"] = version if version > 0 else COMPOSITION_DOC_VERSION
    palette = raw.get("colorPalette")
    out["colorPalette"] = str(palette).strip() if palette not in (None, "") else None

    bg = raw.get("background") if isinstance(raw.get("background"), dict) else {}
    out["background"]["image"] = _optional(bg.get("image"))
    out["background"]["motion"] = _nonempty(bg.get("motion"), "static")
    out["background"]["atmosphere"] = _nonempty(bg.get("atmosphere"), NONE)

    spec = raw.get("spectrum") if isinstance(raw.get("spectrum"), dict) else {}
    out["spectrum"]["shape"] = _nonempty(spec.get("shape"), NONE)
    out["spectrum"]["material"] = _nonempty(spec.get("material"), NONE)
    out["spectrum"]["animation"] = _nonempty(spec.get("animation"), NONE)

    logo = raw.get("logo") if isinstance(raw.get("logo"), dict) else {}
    out["logo"]["enabled"] = bool(logo.get("enabled", True))
    out["logo"]["animation"] = _nonempty(logo.get("animation"), NONE)

    text = raw.get("text") if isinstance(raw.get("text"), dict) else {}
    out["text"]["enabled"] = bool(text.get("enabled", False))

    overlay = raw.get("overlay") if isinstance(raw.get("overlay"), dict) else {}
    out["overlay"]["enabled"] = bool(overlay.get("enabled", False))
    out["overlay"]["animation"] = _nonempty(overlay.get("animation"), NONE)
    items = overlay.get("items")
    out["overlay"]["items"] = list(items) if isinstance(items, list) else []

    particles = raw.get("particles") if isinstance(raw.get("particles"), dict) else {}
    out["particles"]["type"] = _nonempty(particles.get("type"), NONE)
    out["particles"]["behavior"] = _nonempty(particles.get("behavior"), NONE)

    lighting = raw.get("lighting") if isinstance(raw.get("lighting"), dict) else {}
    out["lighting"]["effect"] = _nonempty(lighting.get("effect"), NONE)
    out["lighting"]["trigger"] = _nonempty(lighting.get("trigger"), NONE)

    camera = raw.get("camera") if isinstance(raw.get("camera"), dict) else {}
    out["camera"]["behavior"] = _nonempty(camera.get("behavior"), NONE)

    post = raw.get("postProcessing") if isinstance(raw.get("postProcessing"), dict) else {}
    effects = post.get("effects")
    out["postProcessing"]["effects"] = (
        [str(x).strip() for x in effects if str(x).strip()] if isinstance(effects, list) else []
    )

    audio = raw.get("audio") if isinstance(raw.get("audio"), dict) else {}
    mapping = audio.get("mapping")
    out["audio"]["mapping"] = dict(mapping) if isinstance(mapping, dict) else {}
    return out


def normalize_assets(raw: Any) -> dict[str, Any]:
    base = default_assets()
    if not isinstance(raw, dict):
        return base
    out = dict(base)
    for key in ("backgroundImage", "logo", "audio"):
        out[key] = _optional(raw.get(key))
    return out


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass
class Scene:
    """In-memory composition scene (architecture tree)."""

    schema: str = COMPOSITION_SCHEMA_ID
    version: int = COMPOSITION_DOC_VERSION
    composition: dict[str, Any] = field(default_factory=default_composition)
    assets: dict[str, Any] = field(default_factory=default_assets)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "composition": deepcopy(self.composition),
            "assets": deepcopy(self.assets),
        }


def load_scene(doc: Any) -> Scene:
    """Fail-closed loader: composition is required; legacy-only docs are rejected."""
    if not isinstance(doc, dict):
        raise CompositionContractError("scene document must be a dict")

    # Hard cut: refuse documents that only have legacy authority fields.
    has_composition = isinstance(doc.get("composition"), dict) and bool(doc.get("composition"))
    if not has_composition:
        raise CompositionContractError(
            "missing composition — engine v1 requires schema camxora.composition "
            "(legacy style/particlesSettings-only templates are not supported)"
        )

    schema = str(doc.get("schema") or COMPOSITION_SCHEMA_ID).strip() or COMPOSITION_SCHEMA_ID
    if schema not in (COMPOSITION_SCHEMA_ID, "camxora.composition.v1"):
        # Allow missing schema when composition is present (in-memory drafts),
        # but reject explicit foreign schemas.
        if "schema" in doc and schema:
            raise CompositionContractError(f"unsupported scene schema: {schema!r}")

    try:
        version = int(doc.get("version", COMPOSITION_DOC_VERSION))
    except (TypeError, ValueError) as exc:
        raise CompositionContractError("invalid document version") from exc

    composition = normalize_composition(doc.get("composition"))
    assets = normalize_assets(doc.get("assets"))

    # Prefer composition.background.image when assets.backgroundImage empty.
    if not assets.get("backgroundImage") and composition["background"].get("image"):
        assets["backgroundImage"] = composition["background"]["image"]

    return Scene(schema=COMPOSITION_SCHEMA_ID, version=max(1, version), composition=composition, assets=assets)


def require_composition_document(doc: Any) -> dict[str, Any]:
    """Validate and return a normalized composition document."""
    scene = load_scene(doc)
    return scene.to_document()


__all__ = (
    "COMPOSITION_DOC_VERSION",
    "COMPOSITION_SCHEMA_ID",
    "CompositionContractError",
    "NONE",
    "SCENE_OBJECTS",
    "Scene",
    "default_assets",
    "default_composition",
    "default_document",
    "load_scene",
    "normalize_assets",
    "normalize_composition",
    "require_composition_document",
)
