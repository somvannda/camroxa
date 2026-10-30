# PROJECT DECISIONS

Architectural decisions with long-term consequences. Add, never rewrite history.

---

## D-001 — The Studio is a first-class product surface

**Date:** 2026-10-30 · **Status:** accepted

**Decision.** Studio ships as its own route group with a chrome-free layout, its own
home, and its own API surface, rather than as a page inside the marketing site.

**Why.** A DAW needs the viewport, a stable keyboard model, and a project lifecycle.
Embedding it in site chrome (sidebar/topbar/player) steals ~140 px and breaks
shortcut expectations.

**Consequences.** `/studio` becomes the authenticated home; the marketing page moves
behind the signed-out state. Site navigation points at `/studio`, not the editor.

---

## D-002 — No reference-platform coupling in the product path

**Date:** 2026-10-30 · **Status:** ⚠️ **superseded by D-008** (owner direction, 2026-10-30)

**Decision.** The Studio calls only Camxora APIs. Provider-specific code lives in
`musicapi` behind an adapter. The reference platform's private endpoints stay
documentation-only evidence of *behaviour*, never a runtime dependency.

**Why.** A product that cannot generate music when someone else's undocumented
endpoint changes is not a product. It also creates legal and operational exposure.

**Consequences.**

- `feat/studio-shell` (the `StudioShell.tsx` proxy editor) is retired and not merged.
- The independent `StudioEditorView` on `main` is the product path.
- `docs/studio-1to1.md` keeps its value as behaviour evidence; its "1:1 clone" framing
  is superseded: we match workflows, not internals.

---

## D-003 — Retire `feat/studio-shell`

**Date:** 2026-10-30 · **Status:** ⚠️ **superseded by D-008**

**Decision.** The 85-commit `feat/studio-shell` branch is abandoned rather than
merged. Its useful ideas (Suno-parity layout, panel order, footer arrangement) are
re-implemented independently where they genuinely improve usability.

**Why.** It is built on D-002's rejected premise, duplicates the editor, and its
`StudioShell.tsx` (2.9k lines) cannot coexist with `StudioEditorView` (6.9k lines)
without two competing state models.

**Consequences.** No cherry-picks unless a specific interaction is worth porting and
is re-tested in the independent editor.

---

## D-004 — Original identity, comparable experience

**Date:** 2026-10-30 · **Status:** accepted

**Decision.** All copy, assets, colour tokens and component names are Camxora's.
Behaviour (what a control does, where it lives, what happens on failure) is matched;
pixels and words are not.

**Consequences.** No verbatim strings from the reference beyond generic UI nouns.
Screenshots of the reference never enter the repo.

---

## D-005 — Keep the single-editor-component shape for now

**Date:** 2026-10-30 · **Status:** accepted, revisit after W3

**Decision.** Do not split `StudioEditorView` yet. Extract hooks/regions only when a
change requires it or when W5 tests can protect the refactor.

**Why.** A split of 6.9k lines with no test suite is a high-risk change with zero
user-visible benefit. Feature gaps (W1–W3) come first.

**Revisit trigger.** Either: a second surface needs the arrangement engine, or W5 L2
tests exist for the reducer and mixer invariants.

---

## D-006 — JSON document persistence, versioned snapshots

**Date:** 2026-10-30 · **Status:** accepted

**Decision.** Store the arrangement as a versioned JSON document in
`studio_projects.data`; expose immutable snapshots via project versions.

**Why.** The arrangement is deeply nested and evolves quickly. Normalising it now
would slow every feature and require migrations per control.

**Consequences.** Server-side querying of arrangement internals is impossible; any
future analytics over clips needs a projection table. Validation must happen at the
API boundary (shape + size) because the DB only enforces `jsonb`.

---

## D-007 — Browser-first rendering, server render for fidelity

**Date:** 2026-10-30 · **Status:** accepted

**Decision.** The default export path is an `OfflineAudioContext` render in the
browser. Server-side `render-state` exists for high-fidelity/paid renders and must
consume the same arrangement document.

**Why.** Instant, free, private exports for the common case; server render when the
user pays for fidelity.

**Consequences.** Two renderers must stay in sync — a documented risk. Any mix
feature must be implemented in both, or the browser path must be disabled for it
with a clear message.

---

## D-008 — Target architecture is a Suno-facing clone (supersedes D-002, D-003)

**Date:** 2026-10-30 · **Status:** accepted — **owner direction**

**Decision (owner's words):** "clone 1:1 with suno and using musicapi to build api
that can talk to suno interface."

Concretely:

1. The Studio UI reproduces the reference's layout, control placement, flows and
   behaviour as closely as we can measure and verify — not merely "comparable
   quality".
2. `musicapi` is the adapter that speaks the reference's studio interface
   (`/api/studio/*`): create/load project, save-project versioning, render-state,
   stems, clip edits, personas, uploads. The browser never talks to the reference
   directly; musicapi owns auth, pooling, retries and credits.
3. Discovery is decompilation-assisted: we analyse the publicly shipped client
   bundle and a signed-in session to recover contracts, labels, state shape and
   measured layout, then implement against those facts.

**Rationale:** the owner's product goal is parity with the reference experience, and
`musicapi` already operates the provider integration in production. D-002's
"no coupling" premise does not match the business.

**Consequences**

- `feat/studio-shell` (`StudioShell.tsx`, Suno-contract editor) is the *reference
  implementation* again, not a retired branch. Its proven contracts should be merged
  into the product editor rather than discarded.
- `docs/studio-1to1.md` is re-promoted from "behaviour evidence only" to the contract
  source of truth for the adapter.
- Every endpoint in `docs/studio/reference/endpoint-inventory.json` is a candidate
  for the musicapi surface; coverage is tracked per capability.
- Decompiled artifacts are specifications. We still write our own code.

**Guardrails that remain (non-negotiable, and they are what keeps this shippable)**

| Guardrail | Why |
|---|---|
| Do not ship reference code, fonts, artwork or copy verbatim | Copyright/trade-dress exposure; we reimplement from behaviour |
| Do not lift their proprietary typeface (Neue Montreal) | Commercial licence; substitute our own grotesque |
| No credentials in the repo; cookies stay encrypted in the pool | Security |
| Cache/bundle artifacts never committed — only derived facts | Keeps the repo clean and reviewable |
| Provider failures must degrade to an explicit message, never silent breakage | The clone inherits provider risk; the UI must own it |

**Verification impact:** "1:1" becomes measurable. Layout is compared against
`reference/live-studio-layout.md`; contracts against
`reference/endpoint-inventory.json`; labels against `reference/ui-strings.md`.
