# AI-powered Motion Graphics Platform — build requirements

**Branch / worktree:** `feature/studio-v1` (`MusicGenerator-composition-p0`)  
**Role:** North-star product docs for Composition Engine + Studio (separate from Video pipeline chrome).

Imported from Downloads (2026-08-09). Read in number order.

| # | Document | Use for |
|---|----------|---------|
| 01 | Business Requirement (BRD) | Why / business scope |
| 02 | Product Requirement (PRD) | What we ship |
| 03 | Engine Architecture | Layers, scene objects, ownership |
| 04 | Motion Graphics Engine Spec | Engine capabilities |
| 05 | AI Designer Engine | AI later (after JSON + catalogs) |
| 06 | Complete UI/UX Design System | Creator Studio layout & progressive disclosure |
| 07 | Expert Mode UI/UX | Expert surface (not MVP default) |
| 08 | Asset Library Metadata | Catalog knowledge base (mood/genre/tags) |
| 09 | JSON Schema | Project / scenes / objects / components |
| 10 | Component Library | Component catalog |
| 11 | Plugin SDK | Extensions / marketplace later |

## How this relates to the current build

- **Authoring authority (v1):** `schema: camxora.composition` axes under `visualizer/scene` + Studio.
- **Studio page:** docs-first Creator shell (`features/studio/`). Video page stays frozen for pipeline/export.
- **Living implementation notes:** `docs/COMPOSITION_ENGINE_V1.md`, `docs/COMPOSITION_STUDIO_V1.md`, `docs/VISUALIZER_COMPOSITION_ENGINE_ALIGNMENT.md`.

Do not treat these platform docs as permission to rewrite GPU to full ECS or ship AI/plugins before engine + Studio fidelity.
