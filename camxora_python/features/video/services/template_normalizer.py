"""Electron/workspace draft → Composition Engine V1 renderer dict.

Hard cut: composition is required. Legacy style/particlesSettings-only
templates are rejected. GPU receives compiler output from ``compile_scene``.
"""

from __future__ import annotations

from typing import Any

from features.video.lib.text_domain_runtime import inject_text_domains_into_template
from visualizer.composition_renderer import CompositionContractError, document_to_renderer_dict, merge_workspace_assets
from visualizer.scene import default_composition, default_document


def _composition_from_draft_domains(
    *,
    base: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    """Build a composition document from UI draft axes (composition-first)."""
    doc = default_document()
    existing = base.get("composition") if isinstance(base.get("composition"), dict) else {}
    composition = default_composition()
    if existing:
        from visualizer.scene import normalize_composition

        composition = normalize_composition(existing)

    # Prefer explicit composition axes on draft when present.
    spectrum = composition["spectrum"]
    if draft.get("compositionSpectrumShape"):
        spectrum["shape"] = str(draft["compositionSpectrumShape"]).strip() or spectrum["shape"]
    if draft.get("compositionSpectrumMaterial"):
        spectrum["material"] = str(draft["compositionSpectrumMaterial"]).strip() or spectrum["material"]
    if draft.get("compositionSpectrumAnimation"):
        spectrum["animation"] = str(draft["compositionSpectrumAnimation"]).strip() or spectrum["animation"]

    particles = composition["particles"]
    if draft.get("compositionParticleType"):
        particles["type"] = str(draft["compositionParticleType"]).strip() or particles["type"]
    if draft.get("compositionParticleBehavior"):
        particles["behavior"] = str(draft["compositionParticleBehavior"]).strip() or particles["behavior"]

    if draft.get("compositionColorPalette"):
        composition["colorPalette"] = str(draft["compositionColorPalette"]).strip() or None

    if draft.get("compositionLogoAnimation"):
        composition["logo"]["animation"] = str(draft["compositionLogoAnimation"]).strip() or "none"

    # Fallback: if composition spectrum still none but draft carried new axis keys only — keep none.
    doc["composition"] = composition
    if isinstance(base.get("assets"), dict):
        doc["assets"] = dict(base["assets"])
    return doc


class TemplateNormalizer:
    def to_renderer_dict(
        self,
        *,
        base: dict[str, Any],
        draft: dict[str, Any],
        layers: list[dict[str, Any]],
        workspace: dict[str, Any],
        track_paths: list[str] | None = None,
        pipeline_album: str = "",
        active_track_path: str | None = None,
        lightning_layers: list[dict[str, Any]] | None = None,
        spectrum_instances: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _ = (layers, lightning_layers, spectrum_instances)  # legacy inputs ignored as authority
        draft_rec = draft if isinstance(draft, dict) else {}
        base_rec = base if isinstance(base, dict) else {}

        if isinstance(base_rec.get("composition"), dict) and base_rec.get("composition"):
            doc = {
                "schema": "camxora.composition",
                "version": int(base_rec.get("version") or 1),
                "composition": base_rec["composition"],
                "assets": dict(base_rec.get("assets") or {}),
            }
            # Overlay draft axis patches.
            patched = _composition_from_draft_domains(base=doc, draft=draft_rec)
            doc["composition"] = patched["composition"]
        elif draft_rec.get("compositionSpectrumShape") or draft_rec.get("compositionParticleType"):
            doc = _composition_from_draft_domains(base=base_rec, draft=draft_rec)
        else:
            raise CompositionContractError(
                "TemplateNormalizer requires composition — legacy templates are not supported in engine v1"
            )

        doc = merge_workspace_assets(doc, workspace)
        rendered = document_to_renderer_dict(doc)

        paths = track_paths
        if paths is None:
            raw = workspace.get("trackPaths") if isinstance(workspace, dict) else None
            paths = [str(item) for item in raw] if isinstance(raw, list) else []
        album = str(pipeline_album or (workspace or {}).get("pipelineAlbum") or "").strip()
        active = str(
            active_track_path
            or (workspace or {}).get("selectedMp3Path")
            or (workspace or {}).get("activeTrackPath")
            or ""
        ).strip()

        # Keep composition on the payload (no strip).
        return inject_text_domains_into_template(
            rendered,
            track_paths=paths,
            pipeline_album=album,
            active_track_path=active or None,
        )


def ensure_composition_document(template: dict[str, Any]) -> dict[str, Any]:
    """Attach a default composition document when migrating workspace saves."""
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    if isinstance(template.get("composition"), dict) and template.get("composition"):
        template.setdefault("schema", "camxora.composition")
        template.setdefault("assets", {"backgroundImage": None, "logo": None, "audio": None})
        return template
    raise CompositionContractError("missing composition on template")


# Back-compat name used by older imports during cutover.
def strip_composition_for_renderer(template: dict[str, Any]) -> dict[str, Any]:
    """Deprecated no-op: composition is required and must not be stripped."""
    if not isinstance(template, dict) or not isinstance(template.get("composition"), dict):
        raise CompositionContractError("cannot strip — composition is required")
    return template
