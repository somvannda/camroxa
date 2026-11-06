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

---

## D-009 — Studio operations price from `credit_pricing`, never from `plans`
**Date:** 2026-11-05 · **Status:** accepted — **owner direction** ("we can go on", narrow scope)

**Decision.** Studio charge, quote and refund go through
`CreditsOnlyBillingService` and read prices from `credit_pricing`:

| Operation | Row | Credits |
|---|---|---|
| `studio_edit` | `suno/studio_edit` | 12 |
| `studio_stems_2` | `suno/studio_stems_2` | 12 |
| `studio_stems_12` | `suno/studio_stems_12` | 60 |

`WebMusicChargeBridge` no longer resolves a charge plan for studio ops. Music, lyric,
style, title, album, image, video and merge keep their existing behaviour, so this change
cannot move any other price.

**Why.** Migration 174 dropped `plans`, but the Studio path still asked for a plan before
reading a price, so every stems/extend/cover request died with
`UndefinedTableError: relation "plans" does not exist`. Project rules already say credit
costs belong to the pricing table; the charge bridge was wired to the retired one.

**Consequences.**

- Recreating a `plans` row, or inventing a per-operation allowance, stays forbidden: it
  would hide the defect and price studio work from a table the product no longer has.
- Studio pricing has no plan-specific discount by construction. If a per-plan discount is
  ever wanted, introduce it deliberately in `credit_pricing`/billing rather than
  resurrecting plan columns.
- Regression tests: `test_web_music_v3_charge.py` proves studio quote/charge/refund work
  against a store whose `resolve_charge_plan` raises, and that `music` still resolves a
  plan; `test_v3_credits_only.py` proves the billing service prices a studio op from
  `credit_pricing`.

---

## D-011 — Project menu keeps the captured order, disabling what we cannot honour

**Date:** 2026-11-05 · **Status:** accepted (G23)

**Decision.** The project chip opens the nine items captured in §18.1/§44.2, in that
order. Eight are wired: **New Project**, **Open Project**, **Rename**, **Duplicate
Project**, **Version History** (list + restore), **Share Project** (D-012), **Studio
Settings** (D-013) and **Show Quick Start again**. One is rendered **disabled with the
reason in its tooltip**: Open a copy in v1.

**Why.** Hiding the missing three would break the muscle-memory order the capture
records, and showing them enabled would promise surfaces that do not exist. A disabled
row with a truthful tooltip is the same pattern the editor already uses for Tools, Draw,
List and the microphone.

**Consequences.**

- "Open a copy in v1" is not implementable here at all: this product has no v1 Studio.
  It stays as a disabled marker so nobody re-adds it by accident.
- Settings now exists with only its one captured setting (D-013).
- Sharing exists in the API but not in the editor; wiring it is its own surface.
- Settings has no captured layout, so building it now would be guessing.
- Rename updates the header title but does not touch the arrangement document, so it
  never participates in the 409 version check.

---

## D-012 — Share links are view-and-copy, minted lazily, reused while live

**Date:** 2026-11-05 · **Status:** accepted (G23)

**Decision.** Project menu → Share Project follows the captured semantics (§24): a link
delivers a **view** of the project and lets the visitor fork their own editable copy; the
owner's document is never co-edited. An unnamed project hits the naming gate first
(§24.1), where Skip shares without renaming. The editor reuses an existing live link
rather than minting a new one each time, and new links live 7 days.

**Why.**

- The capture is explicit that sharing is an invitation to open the editor, not real-time
  collaboration; copy in the dialog says so rather than leaving it implied.
- Minting a token per visit would litter `studio_project_shares` and silently invalidate
  links the user already sent out.
- Seven days matches the API default and keeps the dialog honest: the link is not
  permanent, and the dialog says when it expires.
- The naming gate exists because an "Untitled project" link is indistinguishable in a
  recipient's editor; Skip stays available because forcing a name would block sharing.

**Consequences.** Revoking a link is a backend/admin action for now — the dialog does not
expose it. The public route is `/studio/shared/{token}` and the API answers
`GET /api/v3/web-music/studio/shares/{token}` without editor auth, which the e2e suite
asserts.

---

## D-013 — Ghost drag is the one Studio setting we ship

**Date:** 2026-11-05 · **Status:** accepted (G24)

**Decision.** Studio Settings (§22) contains exactly the setting the capture documents:
**Ghost drag for arrangement moves**, default **On**, read once when a drag gesture
starts.

| Mode | During a move | On drop |
|---|---|---|
| On (default) | audio keeps playing the pre-drag arrangement | one apply: playback re-schedules from the playhead with the new positions |
| Off | every move frame re-schedules the engine | nothing extra |

Settings live in `localStorage` (`studio:settings`), not in the project document.

**Why.**

- The capture lists three sections but expands only this one; the other two are shown as
  "not captured yet" rather than invented (C-11).
- The captured wording is explicit that the value is read at gesture start, so a settings
  change mid-drag must not alter the gesture — hence `dragApplyPlan()` takes the mode and
  the session stores it.
- Editor preferences are not arrangement data: storing them in `data` would make toggling
  a checkbox undoable and sync it to collaborators who forked the project.
- Ghost drag needs cheap restarts, so decoded buffers are cached by URL; without that,
  "apply on drop" would refetch and re-decode every clip.

**Consequences.** With ghost drag off, each pointermove stops and restarts every source —
faithful to the capture but not free; the buffer cache keeps it usable at moderate clip
counts. The panel is a browser preference, so it does not follow the user across devices.

---

## D-014 — What's This? is opt-in help, with our own words

**Date:** 2026-11-05 · **Status:** accepted (G25)

**Decision.** The footer's **Learn** pill opens the four captured rows in order
(Keyboard Shortcuts · YouTube Tutorials · Learning Center · What's This?). What's This?
is a global toggle, default **on** like the capture, persisted in Studio settings, and it
drives lightweight cards on any control marked `data-help`.

**Why.**

- The capture calls this "a real feature": every control has an explanation, not just a
  title attribute. Ours uses one delegated listener and a registry, so adding help to a
  control is a `data-help` attribute, not a new component.
- Two destinations do not exist in this product (a tutorial channel, a learning centre),
  so those rows are disabled with the reason instead of removed — the captured row order
  is the parity part.
- Their card copy is theirs; every title and sentence in `lib/studio-help.ts` is written
  for this editor (D-004). The one thing borrowed is the *shape*: name, then one or two
  sentences about the consequence.
- The first-run card appears once per browser profile (`studio:help:seen`); dismissing it
  must not switch behaviour off, so Dismiss and Turn off are separate actions.

**Consequences.** The intro card sits on a light surface, so controls reused inside it
need light-surface colours (`.se-help-actions`); the axe pass caught exactly that when the
system landed. Help copy lives in one file, which means a new control without an entry
shows no card rather than an empty one — `helpFor` returns null.

---

## D-015 — Project versions are captured automatically, throttled server-side

**Date:** 2026-11-06 · **Status:** accepted (G28)

**Decision.** Every successful project save asks the API for an automatic snapshot. The
**server** enforces at most one per project per 20 seconds and keeps the newest 50; the
client fires and forgets, and a snapshot failure never surfaces as a save failure. Manual
snapshots (labelled) are never throttled.

**Why.**

- §25 captures the reference stating *"Projects are saved automatically"* and shows
  entries seconds apart, so a version list that only grows when someone calls an endpoint
  is the wrong shape.
- Throttling must be server-side: several tabs (or the same account on two devices) would
  otherwise multiply snapshots for the same document, and a client clock cannot be
  trusted for a shared resource.
- The history has to be bounded or the table grows without limit. The existing writer
  already pruned to 50; the automatic path reuses that writer, so nothing new can leak.
- Snapshotting after the save (not before) means a version always corresponds to
  something the server accepted — never to a 409 or an offline draft.

**Consequences.** An editing burst produces versions at most every 20 s, which matches
the captured clustering without recording every keystroke-sized change. Restoring still
reloads the editor, and the panel now says versions are automatic rather than
"snapshots you save on purpose".

---

## D-010 — Export normalisation is sample-peak, mix-only, opt-in

**Date:** 2026-11-05 · **Status:** accepted (G11)

**Decision.** The export menu carries one checkbox: **Normalise mix to −1 dBFS**. When
on, `renderMix` scales the finished mix (and the selection render) so its loudest sample
sits at −1 dBFS. Per-track exports are never normalised. The setting is off by default
and lives in component state for the session — it is not written into the project.

**Why.**

- The export dialog was never captured (`reference/CAPTURE_GAPS.md`, C-02), so inventing
  a full mastering UI would be guessing. A single, measurable option closes the real gap
  (exports of the same project landing at different levels) without pretending to know
  their dialog.
- **Sample peak, not LUFS**: integrated loudness needs a BS.1770 meter. We have a 4x
  inter-sample estimate, labelled as such — aiming a LUFS target with it would be a
  number that looks authoritative and is not.
- **Mix-only**: normalising each track file independently would flatten the arrangement's
  relative balance. A mixer must be able to reimport stems and keep their levels.
- **−1 dBFS** matches the default limiter threshold in `lib/studio-master-bus.ts`, so the
  target and the chain agree.
- **Opt-in**: existing exports stay byte-identical unless the box is ticked, which keeps
  the W4.3 byte-exact expectations meaningful.

**Consequences.** The gain is computed after the master chain, so the chain still shapes
the sound; only the final level moves. If LUFS matching is ever wanted, add a real meter
first — do not relabel this one.

