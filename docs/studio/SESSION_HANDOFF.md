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
| Reference tab | Suno Studio, **signed in**, demo project loaded — reuse, never close |

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
- **25 documented** (S01–S04, plus most of S07–S15, S18, S26, S34–S41, S49, S52)
- **Next: S05 — new empty project** (click `New Project` from the My Projects modal)
- Then S16 onward (arrangement)

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
| PowerShell `Set-Content -Encoding utf8` writes a BOM | it broke PostCSS; write via the write tool or strip the BOM |
| CSS font sizes below 11 px fail `check:ui` | 11/12/13/14/15/16/18/22/24/26/28/30/32 only |
| raw hex outside the palette fails `check:ui` | use `var(--token)` |
| canvas-rendered UI (rulers, waveforms, clips inside Suno) | only screenshots read it; DOM probes return nothing |

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
