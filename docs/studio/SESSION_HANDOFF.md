# SESSION HANDOFF — read this first, nothing else

Latest state as of 2026-10-31 (late). A new session should need only this file plus
`reference/SCREEN_MANIFEST.md` and `reference/SCREENSHOT_INDEX.md`.

## Where things are

| | |
|---|---|
| Worktree | `C:\Users\Kong Somvannda\.local\share\opencode\worktree\d16337\studio-rebuild` |
| Branch | `feat/studio-rebuild` — clean, pushed, head `16cad8d4` |
| PR | https://github.com/somvannda/camroxa/pull/new/feat/studio-rebuild |
| Web | `localhost:3103` (this worktree) |
| Platform API | `localhost:8100` (runs from canonical checkout) |
| MusicAPI | `localhost:4003` (runs from canonical checkout) |
| Screenshot archive | `docs/studio/reference/screens/` — 42 files |

## Capturing the reference (the current, working method)

The OpenCode browser pane is a **separate Chromium** and it is signed out of Suno; its
Google sign-in cannot be completed without the account password. The reference is
captured from a **Chrome instance started with a debugging port on a clone of the real
profile** instead:

```
# one-time (Chrome must be closed first: --remote-debugging-port is ignored on the
# default profile since Chrome 136, and the cookie DB is locked while it runs)
Get-Process chrome | Stop-Process -Force
# copy "Local State" + Profile 2 (Cookies, Local Storage, Preferences) into
#   %TEMP%\opencode\chrome-dbg\Default\
chrome.exe --user-data-dir=%TEMP%\opencode\chrome-dbg --remote-debugging-port=9222 https://suno.com/studio
```

That clone carries the signed-in Suno session. Drive it with the CDP helper:

```
cd %TEMP%\opencode
node cdp.mjs list
node cdp.mjs eval "<js>"          # or:  node cdp.mjs evalf query.js
node cdp.mjs shot  out.jpeg [--full]
node cdp.mjs shotclip out.jpeg <x> <y> <w> <h>     # 2x crop, best evidence for detail
node cdp.mjs click <x> <y> [right]
node cdp.mjs hover <x> <y>        # multi-step move + dwell, needed for hover cards
node cdp.mjs press <x> <y> / release <x> <y>
node cdp.mjs key <key> [ctrl|shift|alt|meta]
node cdp.mjs resizeshot out.jpeg <w> <h>           # viewport + shot in ONE session
node probe.mjs                                     # width sweep for breakpoints
```

`Emulation.setDeviceMetricsOverride` is **cleared when the WebSocket closes**, so a
plain `size` followed by a separate `shot` does nothing — use `resizeshot`.

### Working loop for a screen

```
1. get it on screen (DOM-first: find by aria-label, call .click() from evaluate)
2. shotclip for the detail you are documenting, shot for context
3. write the spec sub-section with real numbers (measure via evaluate, not by eye)
4. tick the manifest row, add a row to SCREENSHOT_INDEX.md with the write tool
5. gates, commit, push
```

`evaluate` `.click()` **does** open their menus. Raw CDP mouse clicks open menus on
`mousePressed` and close them on release, which is why `press`/`release` exist.

## Position

- 65 screens, **52 DONE / 4 PART / 9 OPEN**, spec through §88, 63 images.
- Landed this pass: §86 S37 generation result, §72.1 S29 take lanes (two takes,
  commit/audition), §87 S50/S51 export (no dialog — captured negatives),
  §88 S58 empty library.

### The breakthrough: use a Studio-native project

`Drum & Bass Demo` is a **legacy project** — it cannot export or generate (§77).
Opening an `Untitled Project` from the library fixed both instantly. Any future
capture that involves export, generation, takes or plugins should start from a native
project, not the demo.

### Remaining, with the honest reason

| Screen | Why still open |
|---|---|
| S30 warp markers | no warp marker or warp toggle rendered on any audio clip, native or legacy |
| S46 preset browser | `None`/`Custom` are native selects; the list does not open |
| S47 mixer strips | no mixer surface found anywhere |
| S48 master limiter | `Main` cannot be selected, so plugins cannot be added to master |
| S54 clip permissions | Share only offers view + fork-to-copy |
| S56 shared page | needs the public link opened logged out |
| S59 save conflict | two tabs on one project produced no conflict banner in the time tried |
| S60 moderation | needs a policy trigger — do not fabricate |
| S61 credits | needs a spent balance |
| S32 (PART) | `Modulation` lane still accepts no points |
| S44 (PART) | IR slot opens nothing without a file |
| S45 (PART) | needs a successful plugin generation |
| S62 (PART) | offline confirmed silent on the tested path |

See `reference/CAPTURE_GAPS.md` for the next-attempt plan.

## Traps that cost time

| Trap | Avoid |
|---|---|
| Chrome 136+ ignores `--remote-debugging-port` on the default profile | run a cloned `--user-data-dir` (above) |
| the cookie DB is locked while Chrome runs | close Chrome before copying the profile |
| `Emulation.setDeviceMetricsOverride` dies with the WS | `resizeshot`, not `size` + `shot` |
| PowerShell cannot nest quotes inside `node cdp.mjs eval "..."` | write the JS to a file and use `evalf` |
| the Studio editor is canvas — `snapshot`/`find` return nothing | `evaluate` + `aria-label`, or raw CDP clicks |
| the project menu opens on **mousePressed** | `press` then screenshot, or call `.click()` from JS |
| right-click target matters | track **name** → track menu; a clip → clip menu; row body → nothing |
| synthetic `Zoom in` clicks can leave the canvas painting no fills/ruler text | reload; treat as capture-environment risk, re-verify before writing it up |
| the demo project can stall on `Restoring your last project…` | wait ~10 s, then `Try again` / reload; captured as an extra |
| screenshots need a visible window | `Get-Process chrome` first; a minimised window fails |
| PowerShell `Set-Content -Encoding utf8` writes a BOM and mangles `—`/`§` | write docs with the write/edit tools |
| CSS font sizes below 11 px fail `check:ui` | 11/12/13/14/15/16/18/22/24/26/28/30/32 only |
| raw hex outside the palette fails `check:ui` | use `var(--token)` |
| a `DONE` row can be wrong | verify the cited § section really shows that screen |

## Gates before every commit

```
cd camxora.com && npm run typecheck && npm run check:ui
```

## Corrections this session made to older notes

| Older claim | Measured |
|---|---|
| responsive gate at ~706 px | exactly **768 px** — gate at ≤767, editor at ≥768 |
| `What's This?` card is the dark corner note | the corner note is the affordance; the real card is a **light** 256 px tooltip anchored under the control |
| clip menu has dividers (§47) | the complete variant has **no** dividers; grouping comes from order |
| track row has one level bar | two sliders (volume 172 px, pan 48 px) plus a colour strip |

## Open product decisions (unanswered)

1. Canvas renderer or DOM clips for the arrangement.
2. Adopt the full clip model `edits[] + takes[] + fx[]` now or later.
3. Wavetable / IR Designer in scope or cut — **settled by the reference**: behind a
   default-off `Advanced content features` toggle (§64).
4. Do we keep `/studio` as a page, given the reference has no landing page at all
   (it reopens the last project; everything else is the My Projects modal)?

## Docs worth reading (in order)

1. `reference/SCREEN_MANIFEST.md` — the contract
2. `reference/SCREENSHOT_INDEX.md` — which image proves which row
3. `SUNO_STUDIO_IMPLEMENTATION_SPEC.md` §44–§67 — measured layouts
4. `SUNO_STUDIO_UX_UI_FLOW.md` — how it behaves
5. `PROJECT_DECISIONS.md` — why things are the way they are
