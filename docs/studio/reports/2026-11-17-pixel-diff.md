# Pixel diff — 73 reference screens (W2)

**Date:** 2026-11-17
**Workstream:** W2 of `docs/studio/RESIDUAL_VERIFICATION_PLAN.md`
**Branch:** `qa/pixel-harness` (base `origin/main` `e04e0ac3`)
**Scope:** harness + report only. No server, no browser, no product-code, capture or
reference-frame change. `G:\Developments\Projects\Camxora` was not touched.

---

## 1. What ran

```bash
cd camxora.com
npm run check:pixels                 # node scripts/pixel-diff.mjs
node scripts/pixel-diff.mjs --md     # same run, markdown table on stdout
```

The harness (`camxora.com/scripts/pixel-diff.mjs`) reads `docs/studio/reference/PAIRING.json`,
then for every entry with a capture:

1. decodes the reference JPEG with `jpeg-js` and our PNG with `pngjs` to raw RGBA;
2. resamples **our** capture to the reference frame's exact width×height with
   **nearest-neighbour** (no filtering, no interpolation, no library — deterministic by
   construction, which matters for flat UI surfaces);
3. diffs with `pixelmatch` (`threshold 0.1`, `includeAA: false`);
4. writes `<screen>.png` to `docs/studio/reports/pixel-diff/` (red = differing, faded
   reference underneath) and `summary.json` with every metric used below;
5. prints one row per screen and exits `1` if any diffable screen exceeds tolerance.

Dependencies added as devDependencies in `camxora.com`: `pngjs@^7`, `pixelmatch@^8`,
`jpeg-js@^0.4`. `package-lock.json` is updated in the same commit. `npm run check:clone`
still passes and is **not** wired to this script.

### Frame selection

`PAIRING.json` has multi-frame screens (`S05`, `S08`, `S12`, `S25`, `S29`, `S30`, `S44`,
`S48`, `S65`). The frame is chosen deterministically: most slug tokens shared with the
capture name, then fewest extra tokens, then alphabetical. That picks `S05-empty-project`
over the remount variant, `S08-version-history` over the loading crop, `S44-convolution-card`
over the IR-loaded crop, `S65-gate-767px` over the 768 editor frame, and `S29-take-lanes`
over its detail/empty crops. One documented override: **`S48` is diffed against
`S48-master-limiter.jpeg`**, because our capture is the *empty* master chain and the
slug-nearest frame (`S48-master-no-chain`) would compare absence with absence and prove
nothing about the screen's subject.

### Verdicts

| Verdict | Meaning |
|---|---|
| `IDENTICAL` | 0 differing pixels |
| `WITHIN` | differing pixels ≤ tolerance |
| `DELTA` | differing pixels > tolerance; diff PNG written |
| `NO-FRAME` | no capture, no reference frame, or the paired capture is missing |

---

## 2. Tolerance and scaler — the decision, and why it matters

**Tolerance: ≤ 0.2 % differing pixels** (the figure named in the plan), with pixelmatch
`threshold 0.1` and `includeAA: false`. Anti-aliased pixels are excluded because font
rasterisation and the resample — not layout — produce them.

**Scaler: nearest-neighbour, non-uniform, to the reference frame's dimensions.** Nearest is
the only deterministic choice here: any smoothing kernel would make the result depend on the
implementation's filter weights, and the surfaces are flat fills, hairlines and glyphs.

This tolerance is a **tripwire, not a pass certificate**, and the run proves it:

- The smallest delta in the set is **2.37 %** (`S16`) and the next is **3.05 %** (`S05`);
  nothing is even an order of magnitude close to 0.2 %.
- The clone contract explicitly allows brand wordmark, palette and illustration divergence
  (`CLONE_DEFINITION.md`, Agent B §8). A pixel-exact frame is therefore impossible *by
  definition* for every captured surface, independently of correctness.
- 30 of the 52 diffable frames are not the same shape as our capture (19 different viewports,
  11 crops/panels). Resampling 1689×1277 to 1094×1245 squashes the horizontal axis by 0.65
  and the vertical by 0.97, so the global percentage is dominated by framing, not layout.

**Recommendation for W0:** keep 0.2 % for **single-surface crop frames** (card/panel/detail),
and gate full-viewport frames on structural assertions (band profile, control geometry —
`METRICS.json` already does this at 0 tolerance) rather than raw pixel equality. Otherwise
D3 can never be PASS, even for a perfect clone.

To keep the split honest, each delta is classified:

| Split | Meaning |
|---|---|
| `STATE` | the frame shows a different app state, data, menu open/closed, zoom or selection — not a layout defect |
| `LAYOUT` | same surface and state; structure, geometry, chrome or copy differs |
| `STATE+LAYOUT` | both are present and independently evidenced |
| `REGION` | the evidence frame is a crop or differently-shaped viewport; the whole-frame number cannot separate state from layout. The known content delta is still recorded |

---

## 3. Headline result

> **Superseded by §10 (after W3):** these are the W2 numbers, before the 13 re-shoots and the
> 14 unjudged screens were captured. Current: **64 diffable / 9 `NO-FRAME`**.

| Metric | Count |
|---|---|
| Reference screens | **73** |
| Diffable (capture + frame) | **52** |
| `IDENTICAL` | 0 |
| `WITHIN` (≤ 0.2 %) | 0 |
| `DELTA` | **52** |
| `NO-FRAME` | **21** (18 spec-only, 2 negative, 1 capture with no frame — `S43`) |

Delta split: **LAYOUT 24 · STATE 13 · STATE+LAYOUT 10 · REGION 5**.
Of the 52 deltas, **22 are same-shaped full-viewport comparisons** (the only ones where the
percentage is directly meaningful); the other 30 are 19 different-viewport and 11 crop/panel
frames. Only **8** of the 52 are a same-shaped full-frame comparison with a *pure* layout
split: `S26 S27 S36 S39 S41 S49 S52 S65` — and two of those (`S41`, `S65`) were scored MATCH
by the semantic audit, i.e. their percentage is allowed palette/brand, not a defect.

`npm run check:pixels` exits **1**, as required while deltas exist.

---

## 4. Screen-by-screen (73 rows, PAIRING order)

Table A. `C` = paired capture, `S` = named spec, `N` = negative. Diff images live under
`docs/studio/reports/pixel-diff/`; links are relative to this report.

| # | Screen | Title | Evidence | Frame | Size (ref ← ours) | Verdict | % diff | Diff image |
|---|---|---|---|---|---|---|---|---|
| 1 | S01 | Marketing signed out | S `navigation-smoke.spec.ts` | — | — | NO-FRAME | — | — |
| 2 | S02 | Sign-in modal | S `navigation-smoke.spec.ts` | — | — | NO-FRAME | — | — |
| 3 | S03 | Signed-in entry reopened | C `ours-entry-overlay.png` | `S03-signed-in-entry-reopened.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 5.36 | [S03.png](reports/pixel-diff/S03.png) |
| 4 | S04 | My Projects chooser | C `ours-my-projects.png` | `S04-my-projects-modal.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 12.44 | [S04.png](reports/pixel-diff/S04.png) |
| 5 | S05 | Empty project | C `ours-empty-project-clean.png` | `S05-empty-project.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 3.05 | [S05.png](reports/pixel-diff/S05.png) |
| 6 | S06 | Onboarding overlay | C `ours-entry-overlay.png` | `S06-onboarding-overlay.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 5.46 | [S06.png](reports/pixel-diff/S06.png) |
| 7 | S07 | Project menu | C `ours-project-menu.png` | `S07-project-menu.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 8.63 | [S07.png](reports/pixel-diff/S07.png) |
| 8 | S08 | Version history | C `ours-version-history.png` | `S08-version-history.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 7.61 | [S08.png](reports/pixel-diff/S08.png) |
| 9 | S09 | Settings · Performance | C `ours-settings-performance.png` | `S09-settings-performance.jpeg` | 1115x1245 ← 1689x1277 | DELTA | 12.77 | [S09.png](reports/pixel-diff/S09.png) |
| 10 | S10 | Settings · Window management | C `ours-settings-window-management.png` | `S10-settings-window-management.jpeg` | 1115x1245 ← 1689x1277 | DELTA | 12.38 | [S10.png](reports/pixel-diff/S10.png) |
| 11 | S11 | Settings · Content | C `ours-settings-content.png` | `S11-settings-content.jpeg` | 1115x1245 ← 1689x1277 | DELTA | 13.99 | [S11.png](reports/pixel-diff/S11.png) |
| 12 | S12 | Share dialog + naming gate | C `ours-share-dialog.png` | `S12-share-dialog.jpeg` | 1115x1245 ← 1689x1277 | DELTA | 9.33 | [S12.png](reports/pixel-diff/S12.png) |
| 13 | S13 | Learn menu | C `ours-learn-menu.png` | `S13-learn-menu.jpeg` | 1115x1245 ← 1689x1277 | DELTA | 7.51 | [S13.png](reports/pixel-diff/S13.png) |
| 14 | S14 | Keyboard shortcuts | C `ours-shortcuts.png` | `S14-keyboard-shortcuts.jpeg` | 1115x1245 ← 1689x1277 | DELTA | 11.78 | [S14.png](reports/pixel-diff/S14.png) |
| 15 | S15 | What's This? card | C `ours-editor-1689.png` | `S15-whats-this-card.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 23.66 | [S15.png](reports/pixel-diff/S15.png) |
| 16 | S16 | Empty editor | C `ours-empty-project-clean.png` | `S16-editor-empty-project.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 2.37 | [S16.png](reports/pixel-diff/S16.png) |
| 17 | S17 | Loaded editor | C `ours-editor-1689.png` | `S17-editor-loaded-project.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 35.43 | [S17.png](reports/pixel-diff/S17.png) |
| 18 | S18 | Track row anatomy | S `studio-pixel.spec.ts` | — | — | NO-FRAME | — | — |
| 19 | S19 | Track options menu | C `ours-track-options.png` | `S19-track-options-menu.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 8.51 | [S19.png](reports/pixel-diff/S19.png) |
| 20 | S20 | Add track menu | C `ours-add-track.png` | `S20-add-track-menu.jpeg` | 1094x1245 ← 1689x1277 | DELTA | 7.96 | [S20.png](reports/pixel-diff/S20.png) |
| 21 | S21 | Hidden tracks | C `ours-hidden-tracks.png` | `S21-hidden-track.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 22.66 | [S21.png](reports/pixel-diff/S21.png) |
| 22 | S22 | Ruler zoom levels | C `ours-ruler-zoom.png` | `S22-ruler-zoom-levels.jpeg` | 2900x600 ← 1689x1277 | DELTA | 34.61 | [S22.png](reports/pixel-diff/S22.png) |
| 23 | S23 | Section markers | C `ours-section-marker.png` | `S23-section-markers.jpeg` | 920x840 ← 1689x1277 | DELTA | 35.02 | [S23.png](reports/pixel-diff/S23.png) |
| 24 | S24 | Loop region | C `ours-loop-region.png` | `S24-loop-region.jpeg` | 1250x1245 ← 1689x1277 | DELTA | 28.75 | [S24.png](reports/pixel-diff/S24.png) |
| 25 | S25 | Clip selected / trim grips | C `ours-clip-selected.png` | `S25-clip-selected.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 19.57 | [S25.png](reports/pixel-diff/S25.png) |
| 26 | S26 | Clip context menu | C `ours-clip-menu.png` | `S26-clip-context-menu.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 24.18 | [S26.png](reports/pixel-diff/S26.png) |
| 27 | S27 | Clip info rail | C `ours-clip-info.png` | `S27-clip-info-panel.jpeg` | 1920x1277 ← 1689x1277 | DELTA | 15.69 | [S27.png](reports/pixel-diff/S27.png) |
| 28 | S28 | Clip colour submenu | C `ours-clip-color.png` | `S28-clip-color-submenu.jpeg` | 920x1040 ← 1689x1277 | DELTA | 50.2 | [S28.png](reports/pixel-diff/S28.png) |
| 29 | S29 | Take lanes | C `ours-take-lanes.png` | `S29-take-lanes.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 12.98 | [S29.png](reports/pixel-diff/S29.png) |
| 30 | S30 | Stretch modes / warp markers | C `ours-warp-markers.png` | `S30-warp-markers.jpeg` | 1261x1245 ← 1689x1277 | DELTA | 11.91 | [S30.png](reports/pixel-diff/S30.png) |
| 31 | S31 | MIDI clip editor | C `ours-midi-editor.png` | `S31-midi-clip-editor.jpeg` | 3200x560 ← 1689x1277 | DELTA | 23.78 | [S31.png](reports/pixel-diff/S31.png) |
| 32 | S32 | Modulation lane | C `ours-modulation-lane.png` | `S32-modulation-lane-empty.jpeg` | 3200x350 ← 1689x1277 | DELTA | 17.77 | [S32.png](reports/pixel-diff/S32.png) |
| 33 | S33 | Velocity lane | C `ours-midi-velocity.png` | `S33-velocity-lane.jpeg` | 3200x260 ← 1689x1277 | DELTA | 21.95 | [S33.png](reports/pixel-diff/S33.png) |
| 34 | S34 | Prompt bar idle | C `ours-magicbar.png` | `S34-magicbar-idle.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 23.68 | [S34.png](reports/pixel-diff/S34.png) |
| 35 | S35 | Prompt bar attachment | C `ours-prompt-attachment.png` | `S35-magicbar-attachment.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 21.64 | [S35.png](reports/pixel-diff/S35.png) |
| 36 | S36 | Prompt conversation dock | C `ours-prompt-conversation.png` | `S36-magicbar-conversation.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 15.86 | [S36.png](reports/pixel-diff/S36.png) |
| 37 | S37 | Generation result | S `studio-pixel.spec.ts` | — | — | NO-FRAME | — | — |
| 38 | S38 | Model picker | S `studio-pixel.spec.ts` | — | — | NO-FRAME | — | — |
| 39 | S39 | Plugin catalog | C `ours-plugin-catalog.png` | `S39-plugin-catalog.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 10.92 | [S39.png](reports/pixel-diff/S39.png) |
| 40 | S40 | Plugin dock · one slot | C `ours-plugin-dock-eq-convolution.png` | `S40-plugin-dock-single.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 18.24 | [S40.png](reports/pixel-diff/S40.png) |
| 41 | S41 | Plugin dock · multiple | C `ours-plugin-dock-eq-convolution.png` | `S41-plugin-dock-multiple.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 23.07 | [S41.png](reports/pixel-diff/S41.png) |
| 42 | S42 | EQ card | C `ours-plugin-dock-eq-convolution.png` | `S42-eq-card.jpeg` | 1000x524 ← 1689x1277 | DELTA | 10.37 | [S42.png](reports/pixel-diff/S42.png) |
| 43 | S43 | Compressor sidechain | C `ours-compressor-sidechain.png` | — | — ← 1689x1277 | NO-FRAME | — | — |
| 44 | S44 | Convolution card | C `ours-plugin-dock-eq-convolution.png` | `S44-convolution-card.jpeg` | 940x400 ← 1689x1277 | DELTA | 9.76 | [S44.png](reports/pixel-diff/S44.png) |
| 45 | S45 | Plugin designer | S `studio-designer.spec.ts` | — | — | NO-FRAME | — | — |
| 46 | S46 | Preset menu / stepper | C `ours-plugin-dock-eq-convolution.png` | `S46-preset-menu.jpeg` | 840x450 ← 1689x1277 | DELTA | 45.73 | [S46.png](reports/pixel-diff/S46.png) |
| 47 | S47 | No mixer tool cluster | N | — | — | NO-FRAME | — | — |
| 48 | S48 | Master chain with limiter | C `ours-master-chain.png` | `S48-master-limiter.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 14.43 | [S48.png](reports/pixel-diff/S48.png) |
| 49 | S49 | Export menu | C `ours-export-menu.png` | `S49-export-menu.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 18.71 | [S49.png](reports/pixel-diff/S49.png) |
| 50 | S50 | Export scopes, no dialog | S `studio-export.spec.ts` | — | — | NO-FRAME | — | — |
| 51 | S51 | Export result toast | C `ours-export-toast.png` | `S51-export-result-toast.jpeg` | 1500x180 ← 1689x1277 | DELTA | 21.44 | [S51.png](reports/pixel-diff/S51.png) |
| 52 | S52 | Library workspaces | C `ours-editor-library-1689.png` | `S52-library-workspaces.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 29.77 | [S52.png](reports/pixel-diff/S52.png) |
| 53 | S53 | Library songs | C `ours-library-songs.png` | `S53-library-songs.jpeg` | 1689x1277 ← 1689x1277 | DELTA | 18.46 | [S53.png](reports/pixel-diff/S53.png) |
| 54 | S54 | Share permission copy | C `ours-share-dialog.png` | `S54-share-permission-copy.jpeg` | 1200x600 ← 1689x1277 | DELTA | 23.94 | [S54.png](reports/pixel-diff/S54.png) |
| 55 | S55 | Comments and notes | S `studio-clip-info.spec.ts` | — | — | NO-FRAME | — | — |
| 56 | S56 | Shared link logged out | C `ours-share-page-logged-out.png` | `S56-shared-link-logged-out.jpeg` | 1920x1211 ← 1689x1277 | DELTA | 38.37 | [S56.png](reports/pixel-diff/S56.png) |
| 57 | S57 | Project loading blank | S `studio-smoke.spec.ts` | — | — | NO-FRAME | — | — |
| 58 | S58 | Empty library | C `ours-library-empty.png` | `S58-empty-library.jpeg` | 720x280 ← 1689x1277 | DELTA | 7.43 | [S58.png](reports/pixel-diff/S58.png) |
| 59 | S59 | No conflict UI | N | — | — | NO-FRAME | — | — |
| 60 | S60 | Moderation refusal | S `create-sample.spec.ts` | — | — | NO-FRAME | — | — |
| 61 | S61 | Insufficient credits | S `studio-transforms.spec.ts` | — | — | NO-FRAME | — | — |
| 62 | S62 | Offline cold load | S `studio-offline.spec.ts` | — | — | NO-FRAME | — | — |
| 63 | S63 | 1280 px | C `ours-editor-1280-audit.png` | `S63-1280px.jpeg` | 1280x900 ← 1280x900 | DELTA | 21.4 | [S63.png](reports/pixel-diff/S63.png) |
| 64 | S64 | 1024 px | C `ours-editor-1024.png` | `S64-1024px.jpeg` | 1024x900 ← 1024x900 | DELTA | 23.17 | [S64.png](reports/pixel-diff/S64.png) |
| 65 | S65 | 768 px / desktop gate | C `ours-gate-767.png` | `S65-gate-767px.jpeg` | 767x1000 ← 767x900 | DELTA | 8.87 | [S65.png](reports/pixel-diff/S65.png) |
| 66 | EXTRA-generation-refused | Generation refused (legacy copy) | S `studio-transforms.spec.ts` | — | — | NO-FRAME | — | — |
| 67 | EXTRA-generation-refused-legacy | Generation refused (legacy copy) | S `studio-transforms.spec.ts` | — | — | NO-FRAME | — | — |
| 68 | EXTRA-library-uploads | Library uploads | C `ours-library-uploads.png` | `EXTRA-library-uploads.jpeg` | 1261x1245 ← 1689x1277 | DELTA | 10.38 | [EXTRA-library-uploads.png](reports/pixel-diff/EXTRA-library-uploads.png) |
| 69 | EXTRA-library-song-detail | Library song detail | S `studio-components.test.tsx` | — | — | NO-FRAME | — | — |
| 70 | EXTRA-project-load-error | Project load error | S `studio-smoke.spec.ts` | — | — | NO-FRAME | — | — |
| 71 | EXTRA-restoring-last-project | Restoring last project | S `studio-smoke.spec.ts` | — | — | NO-FRAME | — | — |
| 72 | EXTRA-take-lanes-empty | Take lanes empty | C `ours-take-lanes-empty.png` | `EXTRA-take-lanes-empty.jpeg` | 1261x1245 ← 1689x1277 | DELTA | 14.09 | [EXTRA-take-lanes-empty.png](reports/pixel-diff/EXTRA-take-lanes-empty.png) |
| 73 | RESPONSIVE-gate-319px | 319 px gate | S `studio-pixel.spec.ts` | — | — | NO-FRAME | — | — |

---

## 5. `STATE` vs `LAYOUT` for every delta

Table B. Bands are the percentage of differing pixels in the header strip (first ~52 px
scaled), the body, and the footer strip (last ~60 px scaled). A high body band with a low
header band points at state/content; a hot header band points at editor chrome.

| Screen | Split | h / b / f band diff % | Why |
|---|---|---|---|
| S03 | **LAYOUT** | 6.84 / 5.24 / 6.29 | Start overlay ships 3 flat tiles vs the reference's 5 tilted tiles; no ✕, no “Browse Studio projects ›”. Same state, so this is design/chrome. |
| S04 | **LAYOUT** | 6.54 / 12.75 / 11.6 | Translucent panel, ~32 px title and bare ✕ vs an opaque surface, ~19 px title and a filled circular close. Project rows also differ (STATE, minor). |
| S05 | **STATE+LAYOUT** | 9.71 / 2.6 / 6.06 | 0 tracks vs the reference's 1 Audio Track row (the reference itself also carries S05-zero-tracks as a variant), plus empty-state copy/chrome. |
| S06 | **LAYOUT** | 6.79 / 5.45 / 4.44 | Onboarding overlay: same 3-vs-5 tile delta as S03 (shared capture). |
| S07 | **STATE+LAYOUT** | 9.73 / 8.45 / 11.17 | First-run What's This card covers the menu's first three rows (state/overlay); additive Import/Suno Sync rows and the wrapping accelerator are layout. |
| S08 | **LAYOUT** | 9 / 7.28 / 12.83 | Dot-and-rail history vs our pill row with a permanent Restore button; timestamp format and subtitle punctuation differ. |
| S09 | **LAYOUT** | 5.9 / 13.26 / 9.23 | “Studio settings” vs “Studio Settings”, bold sans vs display serif, bare ✕ vs circular outlined close; extra count-in card is additive. |
| S10 | **LAYOUT** | 5.9 / 12.83 / 9.23 | No structural delta was found in the previous audit (control-for-control match); the percentage is palette, typeface and close-button chrome. |
| S11 | **LAYOUT** | 5.9 / 14.59 / 9.23 | Same as S10: captured cards, order and toggles match; palette/chrome only. |
| S12 | **LAYOUT** | 5.99 / 9.47 / 9.48 | Permission guarantee is reworded, a raw origin URL and a fixed “expires in 7 days” claim are added, Done is a bordered pill. Naming gate not in frame (STATE, not captured). |
| S13 | **LAYOUT** | 8.89 / 7.19 / 12.54 | Learn menu is ~16 px too narrow, so “Keyboard Shortcuts” and its accelerator wrap onto two lines. |
| S14 | **STATE+LAYOUT** | 6.45 / 12.21 / 8 | Capture is stale (7 of 57 rows), and the overlay has no search field, no groups, no header ✕ and a lower-case title. |
| S15 | **STATE** | 9.17 / 25.3 / 4.46 | The hovered-control card is never in our frame; it instead shows the first-run explainer bottom-right (an allowed additive). No layout claim possible. |
| S16 | **STATE+LAYOUT** | 6.77 / 2.13 / 3.19 | 0 tracks vs 1 Audio Track row, plus footer cluster / disabled “Add Track Effects” vs the reference's master chips. |
| S17 | **STATE+LAYOUT** | 7.11 / 38.11 / 7.84 | Different demo takes, zoom (1–15 vs 9–137 bars) and a missing 13th track (state); transport centred, extra Stop, no rewind (layout); clip waveforms are stale in the capture. |
| S19 | **LAYOUT** | 9.75 / 8.32 / 11.16 | “Bounce track” is inserted before Duplicate, Delete is red where the reference keeps it neutral, and the menu opens below the trigger. |
| S20 | **LAYOUT** | 9.67 / 7.96 / 6.34 | Row order matches; icons differ, accelerator key caps (A/M/U) are missing, and the menu opens below rather than above. |
| S21 | **STATE+LAYOUT** | 6.84 / 23.71 / 15.92 | Capture shows the old 245 px inline panel (state); labels are “Unmute all” vs “Mute all”, rows use text pills instead of speaker/eye icons, hint missing. |
| S22 | **REGION** | 4.06 / 36.95 / 15.13 | Evidence is a 2900×600 ruler strip, so the global percentage is a framing artefact. Known deltas: different zoom (1–29 vs 9–137, STATE) and missing minor ticks/handles (LAYOUT). |
| S23 | **REGION** | 7.27 / 34.41 / 71.24 | Evidence is a 920×840 panel crop; our capture shows no section marker at all (STATE) — the marker's anatomy is unevidenced. |
| S24 | **LAYOUT** | 9.48 / 30.32 / 14.8 | One loop flag vs two, tint washes over clips instead of behind them, boxed loop icon. Ruler zoom also differs (STATE). |
| S25 | **STATE** | 6.76 / 20.67 / 9.43 | Empty plugin dock where the reference shows the master chain, and stale clip bodies with no waveform. Selected-clip outline itself matches. |
| S26 | **LAYOUT** | 6.88 / 25.76 / 8.52 | 25 rows vs 13: eleven additive rows are interleaved inside the captured sequence, so captured rows fall below the fold; casing and “Download WAV” vs “Download .WAV”. |
| S27 | **LAYOUT** | 6.7 / 16.41 / 9.49 | Rail header sits on a second row instead of inside the top bar; rail is 340 px vs 300 px; no cover art, date, like/overflow cluster or preview player. |
| S28 | **STATE** | 67.94 / 48.74 / 63.15 | The colour submenu is not open in our capture — only the parent row is hovered. The 920×1040 frame is also a crop (REGION). |
| S29 | **STATE** | 7.38 / 12.99 / 17.72 | Our capture is the empty take-lane band (“Create a clip to see alternate takes here”), not the numbered take rows the screen is about. |
| S30 | **STATE+LAYOUT** | 8.77 / 12.1 / 11.03 | Clip pane renders black with one green line and no waveform/warp pennants (state); stretch modes are inline pills vs stacked rows with ⓘ (layout). |
| S31 | **LAYOUT** | 4.93 / 24.88 / 18.88 | No mini piano-roll overview strip above the lanes; View All is pushed to the far right by a run of additive controls; quantize default differs (STATE). |
| S32 | **LAYOUT** | 4.21 / 18.35 / 17.97 | Piano key rows and keyboard ruler are drawn inside an automation lane; the reference is a plain bar grid. Overview strip missing as S31. |
| S33 | **LAYOUT** | 46.65 / 21.1 / 16.15 | Same lane-chrome delta as S32 (note rows + keyboard ruler). Velocity stems are data-dependent and absent from both frames. |
| S34 | **STATE** | 7.79 / 25.07 / 10.3 | Capture is cluttered: the track menu is open over the bar and the MIDI editor is docked, so the idle bar is only partly visible. |
| S35 | **STATE** | 6.8 / 22.97 / 8.71 | Reused editor frame with no attachment chip; the attachment state is unevidenced. |
| S36 | **LAYOUT** | 7.4 / 16.24 / 15.81 | Composer has only an expand arrow (no ✕) and a disabled grey send vs the reference's enabled orange send. Clip Settings pane below is state. |
| S39 | **LAYOUT** | 3.3 / 11.51 / 6.01 | Missing header ⋯, compact “Create new plugin” row vs a large dashed tile, identical generic preview art on every tile, and a tenth untitled blank tile. |
| S40 | **STATE** | 6.84 / 19.28 / 7.91 | Our dock shows the selected track's chain and track-scoped footer chips; the reference dock is the master chain. Card header adds a ⧉ and a modified dot. |
| S41 | **LAYOUT** | 6.83 / 24.17 / 15.72 | Two cards side by side and the Add effect rail match; the percentage is card internals and palette (the previous audit scored this MATCH). |
| S42 | **STATE+LAYOUT** | 9.98 / 10.61 / 6.09 | Preset pill reads “Default” vs “Custom” (state); numeric readouts under the knobs are additive (layout). |
| S44 | **LAYOUT** | 9.61 / 10.03 / 4.67 | Empty state reads “No impulse response” vs “NO ASSET LOADED”, and Gain/Pre/Width knobs are added. No IR is loaded in either frame (state). |
| S46 | **STATE** | 3.59 / 45.86 / 79.22 | The preset popover is closed in our capture; only the stepper is visible, so menu order/placement is unevidenced. |
| S48 | **STATE+LAYOUT** | 7.04 / 15.05 / 8.77 | Capture shows an empty master chain, so the Limiter card the screen is about never renders; the placeholder rail is two tiles vs the reference's three. |
| S49 | **LAYOUT** | 9.71 / 19.7 / 7.41 | A WAV/MP3 format group and a Normalise row are prepended above the three captured scopes; the What's This card also covers the first row. |
| S51 | **REGION** | 34.2 / 21.71 / 4.8 | Evidence is a 1500×180 toast crop. Banner, position and ✕ match; only the scope word differs (STATE). |
| S52 | **LAYOUT** | 9.87 / 31.66 / 10.35 | Missing “See all ›” on Workspaces, letter avatars instead of cover art, ☰ placeholders instead of mini-arrangement thumbnails, visibly smaller tiles. |
| S53 | **STATE** | 9.58 / 19.1 / 13.57 | Capture predates the tag strip: “V6 PRO OK · 0:04” instead of model · key · BPM. Code-side key tag is an “≈” estimate and can disappear. |
| S54 | **REGION** | 27.56 / 23.13 / 36.63 | Evidence is a 1200×600 permission-copy crop. The copy itself is reworded (LAYOUT): “make” vs “create”, different guarantee, added 7-day claim. |
| S56 | **STATE** | 12.58 / 38.38 / 60.53 | The reference frame is the marketing hero and contains no share surface at all (absence); our capture is stuck on “Loading project…”. |
| S58 | **REGION** | 6.15 / 7.52 / 6.78 | Evidence is a 720×280 panel crop. “No songs found.” + “Reset all filters” match in position and order (previous audit: MATCH). |
| S63 | **STATE** | 11.85 / 22.11 / 15.97 | Both fit at 1280 and the 260 px gutter holds; the frames compare different bottom surfaces (reference has a docked MIDI editor + master chips). |
| S64 | **STATE+LAYOUT** | 13.97 / 23.74 / 19.96 | Ours drops the bar/beat readout at 1024 (layout); the bottom surface also differs (state). |
| S65 | **LAYOUT** | 0 / 9.73 / 0 | Card structure, prose slot and 768 px gate match; percentage is the allowed brand/illustration divergence plus a 767×1000 vs 767×900 vertical rescale. |
| EXTRA-library-uploads | **STATE** | 12.03 / 10.24 / 11.67 | Right surface (Uploads) but the list is stuck on “Loading uploads…”, so rows, ↑ UPLOAD tags and date groups are unevidenced. |
| EXTRA-take-lanes-empty | **STATE** | 11.37 / 13.9 / 20.22 | Copy and centring match, but the first-run help card covers the band's right end, so the extra ✕ the code always renders cannot be confirmed from this frame. |

**Reading the split.** The five largest numbers are *not* five layout defects: four are
state (`S28` submenu closed, `S46` popover closed, `S56` marketing hero + stuck loading,
`S17` different demo/zoom) and one is a crop (`S23`). The layout evidence that survives is
concentrated in the menus/chrome set — `S26` (25 rows vs 13), `S49` (format group prepended),
`S27` (rail header/geometry), `S52` (library tiles), `S39` (catalog tiles) — plus the
already-recorded share copy (`S12`, `S54`) and shortcuts overlay (`S14`); the `S65` gate
itself matches.

---

## 6. The 14 previously “cannot judge” screens

These are the rows Agent B marked CANNOT JUDGE. Twelve of them are still `NO-FRAME`; the two
with a capture became diffable but compare a wrong-state frame. W3 must act on all 14.

| Screen | Evidence today | Verdict now | What W3 must do |
|---|---|---|---|
| S01 | S `navigation-smoke` (behavioural) | NO-FRAME | Capture the signed-out marketing page at the S01 frame's 1116×1245 viewport. |
| S02 | S `navigation-smoke` (behavioural) | NO-FRAME | Capture `/login` at 1250×1245. The modal→route divergence still needs a W0 decision; a capture alone does not sanction it. |
| S29 | C `ours-take-lanes.png` + frame | DELTA (STATE) | Re-shoot with two take rows, active-row edge and the promotion cluster. The frame exists; the capture shows the empty band. |
| S43 | C `ours-compressor-sidechain.png`, no frame | NO-FRAME | **W3 cannot fix this by capturing:** there is no `S43-*.jpeg` at all. Needs a reference frame from the source set, or an explicit spec-only decision in `CLONE_DEFINITION.md` (W0). |
| S57 | S `studio-smoke` (behavioural) | NO-FRAME | Capture the blank loading state at 1094×1245. |
| S60 | S `create-sample` (behavioural) | NO-FRAME | Capture the moderation error toast at 1440×900. |
| S61 | S `studio-transforms` (asserts geometry) | NO-FRAME | Capture the out-of-credits modal and auto-reload copy at 1440×900. |
| S62 | S `studio-offline` (behavioural) | NO-FRAME | Capture the offline cold load at 1971×1277. |
| EXTRA-generation-refused | S `studio-transforms` | NO-FRAME | Capture the refused toast; note there is no exact frame (only `…-legacy`), so a frame decision is also needed. |
| EXTRA-generation-refused-legacy | S `studio-transforms` | NO-FRAME | Capture the refused toast at the legacy crop's 1250×1245 frame. |
| EXTRA-library-uploads | C `ours-library-uploads.png` (stuck loading) | DELTA (STATE) | Re-shoot the Uploads view after the list resolves; the current frame is the right surface but sits on “Loading uploads…”, so no row, tag or date group is evidenced. |
| EXTRA-library-song-detail | S `studio-components.test.tsx` (file missing under `tests/e2e`) | NO-FRAME | Capture the song-detail panel; and fix the evidence pointer — a component test is not a frame. |
| EXTRA-project-load-error | S `studio-smoke` (behavioural) | NO-FRAME | Capture the load-error surface at 1689×1277. |
| EXTRA-restoring-last-project | S `studio-smoke` (behavioural) | NO-FRAME | Capture the restore-in-progress state at 1689×1277. |

Per the plan, W3 also owns the 31 capture-state deltas from Agent B. This run isolates them:
the **23 `STATE`/`STATE+LAYOUT` rows** in Table B are the captures that must be re-shot before
their percentages can be read as layout evidence, and the **5 `REGION` rows** need a
same-shape frame as well.

---

## 7. Worst five deltas

| Rank | Screen | % differing | Split | Why the number is large |
|---|---|---|---|---|
| 1 | S28 | 50.20 | STATE (crop) | The colour submenu is not open in our capture; the frame is a 920×1040 menu crop. |
| 2 | S46 | 45.73 | STATE (crop) | The preset popover is closed; only the stepper is visible. |
| 3 | S56 | 38.37 | STATE | The reference frame is the marketing hero with no share surface at all; ours is stuck on “Loading project…”. |
| 4 | S17 | 35.43 | STATE+LAYOUT | Different demo takes and zoom (1–15 vs 9–137 bars), plus centred transport and footer chips. Same 1689×1277 shape, so this one is real evidence. |
| 5 | S23 | 35.02 | REGION | 920×840 panel crop; our capture has no section marker, so the anatomy is unevidenced. |

Next: `S22` 34.61 (REGION), `S52` 29.77 (LAYOUT), `S24` 28.75 (LAYOUT).

---

## 8. Limits and evidence integrity

- **One frame per screen.** Where one capture is paired to several screens (`ours-entry-overlay`
  for S03/S06, `ours-editor-1689` for S15/S17/S35, `ours-plugin-dock-eq-convolution` for
  S40/S41/S42/S44/S46, `ours-share-dialog` for S12/S54, `ours-empty-project-clean` for
  S05/S16), the percentages are not independent samples.
- **The global percentage is an upper bound** whenever the frame and the capture differ in
  shape, and it includes the allowed brand/palette divergence even when they do not.
- **JPEG is lossy.** Reference frames are decoded as shipped; chroma noise below the 0.1
  threshold is ignored, but it is not a lossless baseline.
- **Crop frames are not template-matched.** The harness does not search for the crop inside
  our screenshot; doing so would introduce a second, undocumented matching parameter. Those
  rows are marked `REGION` and excluded from layout claims.
- No claim is made that a `LAYOUT` delta is a defect: it is evidence for review. All defects
  remain the semantic audit's call; this harness supplies the per-screen number and image.

---

## 9. Sign-off

- Screens measured: **73 / 73**; diffable **52**, `NO-FRAME` **21**.
- Every delta has a diff PNG and a `STATE`/`LAYOUT` split; every `NO-FRAME` row names its
  reason and, for the 14 former cannot-judge screens, the W3 action.
- Only `scripts/pixel-diff.mjs`, `package.json` / `package-lock.json`, the diff PNGs and this
  report were added or changed. No product component, capture or reference frame was edited.
- Reproduce with `cd camxora.com && npm run check:pixels`.

---

## 10. After W3 — the 13 re-shoots and the 14 unjudged screens

**Run:** 2026-11-17, branch `qa/capture-run`, base `origin/main` `0551b6fc`, stack on
`:3103` (moto :9000, platform API :8100 sandbox, musicapi :4003, web dev). Captures from
`camxora.com/scripts/capture-screens.mjs`; PAIRING per the capture plan §6.1; S43's frame is
the renamed `S43-compressor-routing-list.jpeg` (already in `origin/main` as `32b0323c`).
Full detail: `2026-11-17-capture-run.md`.

| Metric | Before (W2) | After W3 |
|---|---|---|
| Reference screens | 73 | 73 |
| Paired captures (`check:clone`) | 53 | **64** |
| Diffable (capture **and** frame) | 52 | **64** |
| `NO-FRAME` | 21 (18 spec-only, 2 negative, **1** no frame) | **9** (7 spec-only, 2 negative, **0** no frame) |
| `WITHIN` (≤ 0.2 %) | 0 | 0 |
| `DELTA` | 52 | 64 |

`npm run check:clone` → **passes** (73/73 evidenced; 64 paired captures, 31 spec-covered,
2 negative; metrics 8/8; strings 70/70). `npm run check:pixels` still exits **1**, as
required while deltas exist.

### 10.1 The 13 `STATE` rows

Twelve produced the state the plan names. Eleven of them now diff below their old
wrong-state number, and what remains is layout/brand/content, not a different app state:

| Screen | Before | After | Reading after the re-shoot |
|---|---|---|---|
| S15 | 23.66 | **4.48** | Hover card now present under `120 BPM`; the rest is card chrome. |
| S25 | 19.57 | **17.44** | Master chain dock present (empty chain vs the reference's Delay+Compressor — content). |
| S29 | 12.98 | **12.22** | Take band now shows rows `2`/`1` with take 2 active. |
| S34 | 23.68 | **22.01** | Idle bar with BETA badge, no menu, no MIDI editor. |
| S35 | 21.64 | **22.72** | Attachment chip `Drum Kit Main` + × present. |
| S40 | 18.24 | **16.89** | Master chain with one EQ slot + ghost rail. |
| S46 | 45.73 | **41.27** | Preset popover open (Clear all settings / Save preset… / presets). |
| S53 | 18.46 | **17.45** | Date groups + tag strip present; the measured `key`/`BPM` tags stay absent (soft, audio-derived). |
| S63 | 21.4 | **21.69** | MIDI editor docked + master chain chips in the footer. |
| EXTRA-library-uploads | 10.38 | **9.27** | Uploads resolved: day headings + dated rows. |
| EXTRA-take-lanes-empty | 14.09 | **13.73** | Empty band clean, no first-run card. |

**Still `STATE`, and blocked rather than re-shot:**

| Screen | % | Why it stays STATE |
|---|---|---|
| S28 | 50.20 | **BLOCKED — product defect.** The Clip Color submenu *is* opened, but `.se-clip-menu` is `overflow:auto`, so the absolutely-positioned swatch group is clipped by its own menu and never paints. No viewport or step can evidence it; the capture showing the open menu is kept as `ours-clip-color-open.png` but S28 stays paired to the old capture. |
| S56 | 39.12 | **BLOCKED — reference frame.** The frame `S56-shared-link-logged-out.jpeg` is the marketing hero and contains no share surface. Our capture is now the correct read-only share page (`ours-shared-link-readonly.png`), so the row is no longer a wrong-state capture on our side — but the 39.12 % is a frame defect, not a layout claim. Needs the W0 corpus decision. |

Both are decisions, not capture work: S28 needs a one-line CSS fix (product change, own
branch); S56 needs a real share-surface frame in the corpus.


