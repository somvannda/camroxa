# Composition Studio v1 (docs-first)

**Branch:** `feature/studio-v1`  
**Updated:** 2026-08-09

## Decision

The AI Motion Graphics Platform docs under
`docs/AI-powered Motion Graphics Platform/` are the product source of truth
for Studio (see that folder’s `README.md` for reading order).

**Video page is frozen** for this work. Studio is a sibling sidebar route that
does not import Video inspectors, style registries, or draft hydrate paths.

## Layout (doc 06 Creator)

```text
Toolbar: New | Save | Undo | Browse assets | Audio | Export JSON | Export Video | project | name
Scene Tree | Live Preview | Inspector + Export panel
Transport (Play / scrub / time) — NLE timeline is future-only
```

Inspectors are axes-only (Level 2 progressive disclosure): Creator catalogs use **dropdowns**;
Expert settings live in a separate **frame card** and use **Video-style horizontal sliders** (`Label (value)` + track).  
**Browse assets** opens the Asset Library drawer (discovery). Scene Tree owns structure.  
Wiring status: [`COMPOSITION_STUDIO_WIRING.md`](COMPOSITION_STUDIO_WIRING.md).

## Engine

Studio saves `schema: camxora.composition` documents and previews via
`compile_scene` / `document_to_renderer_dict`.

Projects live in per-user `studio-projects/` (not Video templates).

## Follow-ups (shipped on this branch)

| Area | Status |
|------|--------|
| Asset Library metadata (doc 08) | Shipped — search/apply panel |
| Project schema bridge (doc 09) | Shipped — projection; composition authoritative |
| Studio export JSON / video | Shipped — readiness gate; reuses Video export worker |
| Preview media + GPU bridge | Shipped — loads bg/logo/audio; bridges camera/lighting/atmosphere to GPU |
| Platform phases P1–P7 | Shipped as vertical slices — see `docs/MOTION_GRAPHICS_PLATFORM_PHASES.md` |
| AI Designer | Shipped — rule-based Generate/Modify/Improve (LLM provider adapter later) |
| Expert inspectors | Shipped — denser axis sliders (Creator combos + Expert tuning) |
| Timeline | Shipped — pinned under shell (Creator/Expert); play/seek stub (not full NLE) |
| Video background | Shipped — OpenCV plate decode into preview GL texture |
| Plugin SDK / Marketplace | Shipped — loader + sample plugin; marketplace/cloud stubs |
| Music→Video pipeline cutover | Still deferred (Video frozen) |

## Key modules

- `features/studio/` — shell, inspectors, store, export
- `features/studio/lib/schema_bridge.py` — `composition_to_project` / `project_to_composition`
- `visualizer/presets/metadata.py` — catalog metadata + `search_assets`
