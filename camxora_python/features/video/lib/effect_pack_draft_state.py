"""Effect pack draft apply/clear — port of effectPackDraftState.ts."""

from __future__ import annotations

from typing import Any

from features.video.lib.effect_pack_runtime import (
    build_template_effect_pack_apply_patch,
    build_template_effect_pack_reference_patch,
)
from features.video.lib.merge_records import merge_records
from features.video.lib.template_draft_domains import (
    pick_album_draft_slice,
    pick_background_draft_slice,
    pick_logo_draft_slice,
    pick_particles_draft_slice,
    pick_spectrum_draft_slice,
    pick_title_draft_slice,
)
from features.video.lib.video_template_draft import build_video_template_draft, clone_layer_records


def _merge_domain_draft(
    current_draft: dict[str, Any],
    resolved_draft: dict[str, Any],
    pick_slice,
) -> dict[str, Any]:
    domain_slice = pick_slice(resolved_draft)
    effect_packs = resolved_draft.get("effectPacks")
    next_draft = {**current_draft, **domain_slice}
    if isinstance(effect_packs, dict):
        next_draft["effectPacks"] = effect_packs
    return next_draft


def build_applied_effect_pack_draft_state(
    *,
    current_draft: dict[str, Any],
    current_template: dict[str, Any],
    logo_path: str,
    domain: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    template_patch = build_template_effect_pack_apply_patch(domain, item)
    next_template = merge_records(current_template, template_patch)
    resolved_draft = build_video_template_draft(next_template, logo_path=logo_path)

    if domain == "background":
        return {
            "nextDraft": _merge_domain_draft(current_draft, resolved_draft, pick_background_draft_slice),
            "nextLayers": None,
            "templatePatch": template_patch,
        }
    if domain == "logo":
        return {
            "nextDraft": _merge_domain_draft(current_draft, resolved_draft, pick_logo_draft_slice),
            "nextLayers": None,
            "templatePatch": template_patch,
        }
    if domain == "particles":
        return {
            "nextDraft": _merge_domain_draft(current_draft, resolved_draft, pick_particles_draft_slice),
            "nextLayers": None,
            "templatePatch": template_patch,
        }
    if domain == "album":
        return {
            "nextDraft": _merge_domain_draft(current_draft, resolved_draft, pick_album_draft_slice),
            "nextLayers": None,
            "templatePatch": template_patch,
        }
    if domain == "title":
        return {
            "nextDraft": _merge_domain_draft(current_draft, resolved_draft, pick_title_draft_slice),
            "nextLayers": None,
            "templatePatch": template_patch,
        }

    return {
        "nextDraft": _merge_domain_draft(current_draft, resolved_draft, pick_spectrum_draft_slice),
        "nextLayers": clone_layer_records(next_template.get("layers")),
        "templatePatch": template_patch,
    }


def build_cleared_effect_pack_draft_state(
    *,
    current_draft: dict[str, Any],
    domain: str,
) -> dict[str, Any]:
    effect_packs = current_draft.get("effectPacks") if isinstance(current_draft.get("effectPacks"), dict) else {}
    return {
        "nextDraft": {
            **current_draft,
            "effectPacks": {**effect_packs, domain: None},
        },
        "templatePatch": build_template_effect_pack_reference_patch(domain, None),
    }


def apply_spectrum_pack_as_preset(
    *,
    current_draft: dict[str, Any],
    current_template: dict[str, Any],
    logo_path: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    """Apply installed spectrum pack visuals without writing effectPacks ref."""
    template_patch = item.get("templatePatch")
    patch = dict(template_patch) if isinstance(template_patch, dict) else {}
    next_template = merge_records(current_template, patch)
    resolved_draft = build_video_template_draft(next_template, logo_path=logo_path)
    next_draft = {**current_draft, **pick_spectrum_draft_slice(resolved_draft)}
    effect_packs = current_draft.get("effectPacks")
    if isinstance(effect_packs, dict):
        next_draft["effectPacks"] = effect_packs
    return {
        "nextDraft": next_draft,
        "nextLayers": clone_layer_records(next_template.get("layers")),
    }


def apply_particle_pack_as_preset(
    *,
    current_draft: dict[str, Any],
    current_template: dict[str, Any],
    logo_path: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    """Apply installed particle pack visuals without writing effectPacks ref."""
    template_patch = item.get("templatePatch")
    patch = dict(template_patch) if isinstance(template_patch, dict) else {}
    next_template = merge_records(current_template, patch)
    resolved_draft = build_video_template_draft(next_template, logo_path=logo_path)
    next_draft = {**current_draft, **pick_particles_draft_slice(resolved_draft)}
    effect_packs = current_draft.get("effectPacks")
    if isinstance(effect_packs, dict):
        next_draft["effectPacks"] = effect_packs
    return {
        "nextDraft": next_draft,
    }
