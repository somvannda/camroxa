# PROJECT PROGRESS

## Session 2026-10-30 — decompilation groundwork + architecture correction

### Completed

| # | Work | Artifact |
|---|---|---|
| 1 | Repository audit; identified that the independent editor (`StudioEditorView`) is on `main` and the Suno-contract editor (`StudioShell`) is on `feat/studio-shell` | this doc |
| 2 | Programme documentation set (12 documents) | `docs/studio/*.md` |
| 3 | Feature inventory with permanent IDs (221 rows) | `SUNO_STUDIO_FEATURE_INVENTORY.md` |
| 4 | Architecture decisions, including the owner's correction of the target | `PROJECT_DECISIONS.md` (D-008) |
| 5 | Reference extraction toolkit (fetch + extract + parity) | `tools/suno-re/` |
| 6 | Public-bundle extraction: 101 chunks → 255 endpoints | `reference/endpoint-inventory.*` |
| 7 | **Authenticated** bundle extraction: 134 chunks (11.9 MB) → **322 endpoints, 81 studio-related** | `reference/endpoint-inventory.*` |
| 8 | UI string mining: 9,679 candidates, **2,400 in studio chunks** | `reference/ui-strings.md` |
| 9 | **First measured layout capture** (1958×1245): tokens, header 52 px, track panel 260 px, control geometry | `reference/live-studio-layout.md` |
| 10 | Studio home implementation (resume, grid, search, sort, create, per-card actions) | `components/studio/StudioHome.tsx` |
| 11 | Marketing page extracted to its own component; `/studio` now routes by auth | `components/studio/StudioMarketing.tsx`, `app/(site)/studio/page.tsx` |

### Tests executed

| Check | Result |
|---|---|
| `npm run typecheck` (baseline `origin/main`) | pass |
| Bundle fetch (anonymous) | 101/101 chunks, 7,275 KB |
| Bundle fetch (authenticated) | 134/134 chunks, 11,884 KB |
| Endpoint extraction | 322 unique, 81 studio-related |
| String extraction | 9,679 unique, 2,400 studio-chunk |
| Layout capture | complete for 1 viewport (1958×1245) |

Not run: `typecheck`/`check:ui` after the Studio home commit; no E2E; no accessibility run.

### Newly discovered (from the authenticated bundle/session)

- Studio endpoints beyond the previously documented set (81 studio-related paths total).
- Onboarding overlay with four entry cards + "Empty Project" + "Browse Studio projects".
- Header composition: transport centred, session settings right-aligned ~550 px apart.
- Track panel is a fixed 260 px column; control height 32 px, compact 28 px.
- App typeface is Neue Montreal (commercial — we must substitute).

### Coverage snapshot

| Metric | Value |
|---|---|
| Inventory rows | 221 |
| `VERIFIED` | **0** |
| `TESTING` | 0 |
| `IMPLEMENTED` (typechecks only) | 184 |
| Reference endpoints recovered | 322 (81 studio) |
| Reference UI strings recovered | 9,679 (2,400 studio) |
| Layout checkpoints captured | 1 of 4 planned viewports |

### Session close-out — 2026-10-30

Delivered this session: 12 programme documents + 45-section implementation spec,
78-target capture matrix, 5-layer capture protocol, 5-item backend spec, decompile
toolkit (`tools/suno-re/`), 322-endpoint inventory, 9,679-string corpus, 17 derived
feature areas, measured layout, four menus, full keyboard map, settings/share/history
semantics, and the corrected clip model.

Not delivered (needs different evidence types): 27 capture targets — pixel-only
geometry, paid-flow dialogs, collaboration surfaces, induced failure states, and
responsive widths.

Next session: run `CAPTURE_PROTOCOL.md` §3 per surface, or begin implementation at
spec §2/§3/§5 (header, track panel, Magic Bar) which are already measured.
