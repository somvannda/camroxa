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
Toolbar: New | Save | Undo | Audio | Export JSON | Export Video | project picker | name
Scene Tree + Asset Library | Live Preview | Inspector
```

Inspectors are axes-only (Level 2 progressive disclosure).

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
| AI Designer | Out of scope |
| Timeline | Out of scope |
| Plugin SDK / Marketplace | Out of scope |
| Music→Video pipeline cutover | Out of scope |

## Key modules

- `features/studio/` — shell, inspectors, store, export
- `features/studio/lib/schema_bridge.py` — `composition_to_project` / `project_to_composition`
- `visualizer/presets/metadata.py` — catalog metadata + `search_assets`
