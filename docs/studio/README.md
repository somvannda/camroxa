# Camxora Studio — Reconstruction Program

**Objective:** a production-grade AI music studio with coverage of the observable
Suno Studio experience, implemented independently on Camxora's own stack.

This directory is the permanent record of the program. It is written so that a new
session can resume without re-discovering anything.

## Read in this order

| # | Document | Purpose |
|---|---|---|
| 0 | [PROJECT_NEXT_ACTIONS.md](PROJECT_NEXT_ACTIONS.md) | **Start here.** The exact next task. |
| 0b | [SUNO_STUDIO_IMPLEMENTATION_SPEC.md](SUNO_STUDIO_IMPLEMENTATION_SPEC.md) | **Build from this.** Every captured surface, control, placement and API capability, plus the capture backlog. |
| 1 | [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) | What is done, what changed, what was tested. |
| 2 | [PROJECT_MASTER_PLAN.md](PROJECT_MASTER_PLAN.md) | Milestones M0–M12 and their gates. |
| 3 | [PROJECT_DECISIONS.md](PROJECT_DECISIONS.md) | Architectural decisions and why. |
| 4 | [PROJECT_BLOCKERS.md](PROJECT_BLOCKERS.md) | What cannot proceed and what unblocks it. |
| 5 | [SUNO_STUDIO_FEATURE_INVENTORY.md](SUNO_STUDIO_FEATURE_INVENTORY.md) | Every observed reference feature, with ID. |
| 6 | [SUNO_STUDIO_FEATURE_MATRIX.md](SUNO_STUDIO_FEATURE_MATRIX.md) | Coverage dashboard: status per feature. |
| 7 | [SUNO_STUDIO_NAVIGATION_MAP.md](SUNO_STUDIO_NAVIGATION_MAP.md) | Routes, regions, and how they connect. |
| 8 | [SUNO_STUDIO_UX_ANALYSIS.md](SUNO_STUDIO_UX_ANALYSIS.md) | Interaction quality: states, feedback, keyboard, a11y. |
| 9 | [SUNO_STUDIO_UI_COMPONENT_CATALOG.md](SUNO_STUDIO_UI_COMPONENT_CATALOG.md) | Component inventory and reuse rules. |
| 10 | [SUNO_STUDIO_INTERACTION_SPECIFICATION.md](SUNO_STUDIO_INTERACTION_SPECIFICATION.md) | Per-control behaviour contracts. |
| 11 | [SUNO_STUDIO_WORKFLOW_DOCUMENTATION.md](SUNO_STUDIO_WORKFLOW_DOCUMENTATION.md) | End-to-end user journeys. |
| 12 | [SUNO_STUDIO_TECHNICAL_ARCHITECTURE.md](SUNO_STUDIO_TECHNICAL_ARCHITECTURE.md) | How our system is built. |
| 13 | [SUNO_STUDIO_API_INTEGRATION_MAP.md](SUNO_STUDIO_API_INTEGRATION_MAP.md) | Frontend → API → provider call map. |
| 14 | [SUNO_STUDIO_GAP_ANALYSIS.md](SUNO_STUDIO_GAP_ANALYSIS.md) | Reference vs. ours, honestly scored. |
| 14b | [BACKEND_SPEC.md](BACKEND_SPEC.md) | Five backend work items: unified ops, clip edit chain, analysis endpoints, clip social layer, render artifacts. |
| 15 | [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Ordered work with dependencies. |
| 16 | [TESTING_AND_ACCEPTANCE_CRITERIA.md](TESTING_AND_ACCEPTANCE_CRITERIA.md) | Definition of done, per feature. |

## Evidence tags

Every reference claim carries a tag. Never upgrade a tag without new observation.

| Tag | Meaning |
|---|---|
| `B` | Read from Suno's publicly shipped JavaScript bundle (contract-level: endpoints, payloads, state shape). |
| `H` | Suno help centre / release notes (user-facing wording and flow). |
| `L` | Observed in a live, signed-in Studio session. |
| `P` | Captured in a previous Camxora session and recorded in `docs/studio-*.md`. |
| `?` | Not evidenced. **Do not build on `?`.** |

## Status vocabulary (mandatory)

`NOT_DISCOVERED` → `DISCOVERED` → `DOCUMENTED` → `DESIGNED` → `IMPLEMENTING` →
`IMPLEMENTED` → `TESTING` → `VERIFIED` · `BLOCKED`

Rules:

- `IMPLEMENTED` means the code path exists and typechecks — not that it works.
- `VERIFIED` requires a named test or a recorded manual run **in this repository's
  current HEAD**, noted in the matrix.
- `BLOCKED` always names the blocker and the document that records it.

## Related historical documents

The prior `docs/studio-*.md` files remain valid evidence and are not duplicated here:

- `docs/studio-state-schema.md` — Suno's arrangement document shape.
- `docs/studio-1to1.md` — verified endpoint contracts (reference only; we do not
  call Suno from the product path — see D-002).
- `docs/studio-flows.md`, `docs/studio-audit-a-z.md`, `docs/studio-controls-from-i18n.md`
  — feature-by-feature observations.
- `docs/studio-clone-status.md` — the retired `feat/studio-shell` work (D-003).

## Reference capture directory

| File | Contents |
|---|---|
| `reference/CAPTURE_PROTOCOL.md` | Defines "captured" as 5 layers (structure, geometry, text, behaviour, data); lists the 27 surfaces and the per-surface recipe. |
| `reference/CAPTURE_MATRIX.md` | 78 capture targets with status (done / partial / open / blocked). |
| `reference/CAPTURE_LOG.md` | Every run: what, how, result, dead ends, and the method that worked. |
| `reference/live-studio-layout.md` | Measured editor frame at 1958×1245. |
| `reference/endpoint-inventory.{json,md}` | 322 endpoints (81 studio-related) from the shipped bundle. |
| `reference/ui-strings.{json,md}` | 9,679 candidate UI strings; 2,400 in studio chunks. |
| `reference/derived-features.md` | Strings bucketed into 14 capability areas; source of `ST-NEW-01…17`. |
| `tools/suno-re/` | Re-runnable toolkit: fetch bundle, fetch list, extract contracts, extract strings, bucket features. |

## Backend artifacts

| Artifact | Contents |
|---|---|
| `musicapi/migrations/0043_studio_ops_social_render.sql` | `studio_operations`, `studio_clip_analysis`, `clip_permissions`, `clip_permission_grants`, `clip_comments`, `clip_comment_settings`, `studio_render_jobs`, `studio_render_artifacts`. |
