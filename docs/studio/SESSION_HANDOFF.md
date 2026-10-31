# SESSION HANDOFF — read this first, nothing else

Compacted state as of 2026-10-30. A new session should need only this file plus
`SCREEN_MANIFEST.md`.

## Where things are

| | |
|---|---|
| Worktree | `C:\Users\Kong Somvannda\.local\share\opencode\worktree\d16337\studio-rebuild` |
| Branch | `feat/studio-rebuild` — clean, pushed |
| PR | https://github.com/somvannda/camroxa/pull/new/feat/studio-rebuild |
| Web | `localhost:3103` (this worktree) |
| Platform API | `localhost:8100` (runs from canonical checkout) |
| MusicAPI | `localhost:4003` (runs from canonical checkout) |
| Reference tab | **not persisted** — browser tabs are per-session; re-open `suno.com` and sign in again |

## The working loop (proven, use it for every screen)

```
1. snapshot the reference tab while the screen is open
2. find "<label>" → click that ref        (synthetic .click() does NOT work)
3. screenshot
4. write the spec section in SUNO_STUDIO_IMPLEMENTATION_SPEC.md
5. commit; tick the row in SCREEN_MANIFEST.md
```

One screen = one screenshot + one spec section + one commit. Never two at once.

## Position

- 65 screens in `docs/studio/reference/SCREEN_MANIFEST.md`
- **29 DONE, 5 PART, 31 OPEN** (counted from the manifest rows, not the old tally)
- **S05 DONE §59** — new empty project: one `Audio Track` created automatically,
  120 BPM / 4/4, bar labels every 2 bars at default zoom.
- **S19 PART §61** — track options menu, DOM-measured but no screenshot. The menu
  is opened by right-clicking the **track name** only; there is no options button.
- **Next: S16 (arrangement)** — the editor with content. S19 needs a re-shot with
  the window visible to become DONE.
- The reference tab is signed in again as of this session — reuse it, don't close it.

## What is actually built (code)

`/studio` project home · `/studio/editor` reference-layout shell · `/studio/editor/classic`
(old editor) · deep link `?project=` · transport that plays (clips with `audioUrl`) ·
dual rulers · clips with header band + selection outline · two sliders per track row ·
semantic track colours · plugin dock (9 effects, presets, modes, bypass, popout) ·
editable tempo and add-track, both persisted.

## What is NOT built

Magic Bar (geometry in §54) · trim/drag/split · take lanes · warp markers · EQ bands ·
compressor sidechain · mixer · export dialog · waveforms · plugin audio processing ·
generation inside the editor · B1–B5 backend handlers.

## Traps that cost time

| Trap | Avoid |
|---|---|
| `element.click()` doesn't open their menus | use `snapshot` → `find` → `click ref` |
| refs expire after a nav or a new snapshot | do find → click → screenshot in one pass |
| the Studio editor exposes **no** a11y refs (all canvas) | `snapshot`/`find` return an empty tree — read `innerText` via `evaluate`, locate the control by `aria-label`, then dispatch a full pointer sequence (pointerover → pointerdown → mousedown → pointerup → mouseup → click) |
| a control's only handle is its `aria-label` | e.g. the onboarding `×` is `Skip to the empty project`; search by label, never by glyph |
| PowerShell `Set-Content -Encoding utf8` writes a BOM | it broke PostCSS; write via the write tool or strip the BOM |
| CSS font sizes below 11 px fail `check:ui` | 11/12/13/14/15/16/18/22/24/26/28/30/32 only |
| raw hex outside the palette fails `check:ui` | use `var(--token)` |
| canvas-rendered UI (rulers, waveforms, clips inside Suno) | only screenshots read it; DOM probes return nothing |
| browser tabs do **not** survive into a new session | re-open `suno.com` and sign in; never plan around "the tab is still there" |
| a `DONE` row can be wrong | verify the cited § section really shows that screen before trusting it |

## Gates before every commit

```
cd camxora.com && npm run typecheck && npm run check:ui
```

## Open product decisions (unanswered)

1. Canvas renderer or DOM clips for the arrangement.
2. Adopt the full clip model `edits[] + takes[] + fx[]` now or later.
3. Wavetable / IR Designer in scope or cut.
4. Do we keep `/studio` as a page, given the reference has no landing page at all
   (it reopens the last project; everything else is the My Projects modal)?

## Docs worth reading (in order)

1. `reference/SCREEN_MANIFEST.md` — the contract
2. `SUNO_STUDIO_IMPLEMENTATION_SPEC.md` §44–§56 — measured layouts
3. `SUNO_STUDIO_UX_UI_FLOW.md` — how it behaves
4. `PROJECT_DECISIONS.md` — why things are the way they are
