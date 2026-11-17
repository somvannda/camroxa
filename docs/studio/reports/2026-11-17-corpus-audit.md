# Corpus audit — functional strings, metrics and pairing evidence

**Date:** 2026-11-17
**Workstream:** W8 (residual verification — capture-derived corpus)
**Branch:** `qa/corpus-audit`
**Base:** `origin/main` `4abff799`
**Scope:** `docs/studio/reference/FUNCTIONAL_STRINGS.json` (70 strings),
`METRICS.json` (8 metrics), `PAIRING.json` (65+ entries) against the 85 frames in
`docs/studio/reference/screens/`.
**No file under `docs/studio/reference/` was edited.** Corrections are proposed as a patch (§5).

---

## 1. Headline

**The `Download WAV` correction (commit `a4740b0c`) is wrong and must be reverted.**

S26 does **not** say "Download WAV". It says **`Download .WAV`** — there is a period
before the extension. Verified at 8× nearest-neighbour zoom on two independent frames
(S26 clip menu, S28 clip menu + colour flyout) and corroborated by Suno's own shipped
string in the extracted bundle (`ui-strings.json:17746` → `"text": "Download .WAV"`).

The bad edit was made from **our** button label, not the frame: `camxora.com/components/studio/StudioEditorShell.tsx:6644`
renders `Download WAV`, and the file's own doc comment at line 3610 says
`/** Clip menu – Download .WAV */` (i.e. the comment knew the right string). The gate
then made the error permanent, because `check-clone-parity.mjs` only asserts that each
corpus string appears *somewhere* in our source (`source.includes(text)`), so a corpus
entry edited to match a wrong label passes forever.

The other prior fix — `No impulse response` → **`NO ASSET LOADED`** (commit `68a67e07`) —
is **correct** (§4, C-1).

Net effect of this audit: **one wrong "fix" reverted, one genuine clone deviation exposed**
(our clip menu and song-detail download label must become `Download .WAV`), plus seven
dropped trailing characters that the gate cannot see.

---

## 2. Counts

| Verdict | Count | Meaning |
|---|---|---|
| **Verified in a frame** | **52** | the string is rendered in a named frame and matches character-for-character |
| **Mismatch** | **2** | the frame shows different characters (`Download .WAV`, `Save preset…`) |
| **Cannot read** | **16** | no frame renders the text (§6 breaks this down) |
| **Total** | **70** | |

Of the 16 unreadable: 9 are shipped and traceable to a non-frame reference artefact
(bundle string, spec heading, operation inventory), **4 are our own additions presented as
captured** (`Project (JSON)`, `Normalise mix to`, `Import project…`, `Sends`), and 3 only
appear in an uncaptured state (expanded search, collapsed track panel, add-track heading).

Also found: **1 captured string missing from the corpus** — `Open a copy in v1` (S07, row 7).

---

## 3. Method

- Every frame was read at native resolution; ambiguous glyphs were re-cropped with
  `System.Drawing` + nearest-neighbour upscaling (2×–11×) and re-read. Nothing is
  inferred from a filename or from `SCREENSHOT_INDEX.md`.
- Punctuation was checked deliberately: the dot in `Download .WAV`, the ellipsis in
  `Save preset…`, the apostrophe style in `What's This?`.
- Metric claims were measured by pixel scan of S17 (accent-strip pitch, gutter boundary,
  ruler tick spacing, header pill height), not by eye.
- Frame content was compared with each `PAIRING.json` title; a title that names a surface
  the frame does not show is recorded as an evidence defect (§7).
- "Confidence" is about the **frame read**: HIGH = glyph-level crop at ≥3×; MEDIUM =
  read at 1× or inferred from a partly occluded/hover state.

---

## 4. Verification table (all 70)

| # | String as recorded | Frame evidence (file — what the frame shows) | Verdict | Conf. |
|---|---|---|---|---|
| 1 | `New Project` | `S07-project-menu.jpeg` — menu row 1; also `S04` card | MATCH | HIGH |
| 2 | `Open Project` | `S07` — row 2 | MATCH | HIGH |
| 3 | `Rename` | `S07` — row 3 | MATCH | HIGH |
| 4 | `Duplicate Project` | `S07` — row 4 | MATCH | HIGH |
| 5 | `Version History` | `S07` — row 5 | MATCH | HIGH |
| 6 | `Share Project` | `S07` — row 6 | MATCH | HIGH |
| 7 | `Studio Settings` | `S07` — row 8, accelerator `ctrl shift ,`; dialog title in `S11` | MATCH | HIGH |
| 8 | `Show Quick Start again` | `S07` — row 9 | MATCH | HIGH |
| 9 | `Name project before sharing` | `S12-share-naming-gate.jpeg` — dialog title | MATCH | HIGH |
| 10 | `Copy Link` | `S12-share-dialog.jpeg`, `S54` — primary pill | MATCH | HIGH |
| 11 | `Full Song` | `S49-export-menu.jpeg`, `S50` — row 1 | MATCH | HIGH |
| 12 | `Selected Time Range` | `S49`, `S50` — row 2 (disabled in S50) | MATCH | HIGH |
| 13 | `Multitrack` | `S49`, `S50` — row 3 | MATCH | HIGH |
| 14 | `Project (JSON)` | — no frame shows it (S49/S50 have 3 rows only) | CANNOT READ | — |
| 15 | `Normalise mix to` | — no frame; our export checkbox reads `Normalise mix to -1 dBFS` | CANNOT READ | — |
| 16 | `Clear all settings` | `S46-preset-menu.jpeg` — first menu row | MATCH | HIGH |
| 17 | `Save preset` | `S46` — second row reads **`Save preset…`** (trailing ellipsis, U+2026) | **MISMATCH** → `Save preset…` | HIGH (ellipsis) |
| 18 | `Add effect` | `S49`/`S40`/`S48` — `+ Add effect` button in the dock | MATCH | HIGH |
| 19 | `Search plugins` | `S39-plugin-catalog.jpeg` — search field placeholder | MATCH | HIGH |
| 20 | `Create new plugin` | `S39` — dashed card under MY PLUGINS | MATCH | HIGH |
| 21 | `Audio` | `S20-add-track-menu.jpeg` — row 1 | MATCH | HIGH |
| 22 | `MIDI` | `S20` — row 2 | MATCH | HIGH |
| 23 | `Upload` | `S20` — row 3 | MATCH | HIGH |
| 24 | `Add new track` | `S16-editor-empty-project.jpeg`, `S05`, `S07` — gutter action | MATCH | HIGH |
| 25 | `Rename track` | `S19-track-options-menu.jpeg`, `S41` — row 1 | MATCH | HIGH |
| 26 | `Collapse controls` | `S19`, `S41` — row 3 | MATCH | HIGH |
| 27 | `Expand controls` | — no frame (only the collapsed/expanded inverse of row 3; never captured) | CANNOT READ | — |
| 28 | `Duplicate` | `S19` row 4; `S26` row 3 | MATCH | HIGH |
| 29 | `Hide & Mute Track` | `S19`, `S41` — row 5 | MATCH | HIGH |
| 30 | `Delete` | `S19` row 6; `S26` row 4 | MATCH | HIGH |
| 31 | `Copy` | `S26-clip-context-menu.jpeg` row 1 (`ctrl C`); `S28` | MATCH | HIGH |
| 32 | `Paste` | `S26` row 2 (`ctrl V`) | MATCH | HIGH |
| 33 | `Heal Edits` | `S26` row 5; `S28` | MATCH | HIGH |
| 34 | `Split` | `S26` row 6 (`ctrl E`) | MATCH | HIGH |
| 35 | `Clip Info` | `S26` row 8 | MATCH | HIGH |
| 36 | `Clip Color` | `S26` row 9 (`▸`); `S28` flyout parent row | MATCH | HIGH |
| 37 | `Get Stems` | `S26` row 10 | MATCH | HIGH |
| 38 | `Download WAV` | `S26` row 11 and `S28` read **`Download .WAV`** (dot before the extension, 8× crop) | **MISMATCH** → `Download .WAV` | HIGH |
| 39 | `Download MIDI` | — not in the captured clip menu (S26 has `Get MIDI` only); bundle has it (`ui-strings.json:17762`) | CANNOT READ | — |
| 40 | `Get MIDI` | `S26` row 12 | MATCH | HIGH |
| 41 | `Remove FX` | `S26` row 13 | MATCH | HIGH |
| 42 | `Add FX` | — not in S26 (no Add-FX row); our label is `Add FX…` | CANNOT READ | — |
| 43 | `Extend` | — generate row, never captured; bundle has bare `Extend` (`ui-strings.json:1850`) | CANNOT READ | — |
| 44 | `Cover` | — never captured; bundle has bare `Cover` (`:1846`), PIXEL_PARITY §95 records `Cover…` | CANNOT READ | — |
| 45 | `Remaster` | — never captured | CANNOT READ | — |
| 46 | `Vocals` | — never captured; PIXEL_PARITY §95 records `Vocals…` | CANNOT READ | — |
| 47 | `Instrumental` | — never captured; §95 records `Instrumental…` | CANNOT READ | — |
| 48 | `Mashup` | — never captured; §95 records `Mashup…` | CANNOT READ | — |
| 49 | `Replace` | — never captured; §95 records `Replace…` | CANNOT READ | — |
| 50 | `All Songs` | `S52-library-workspaces.jpeg` — tile 1 | MATCH | HIGH |
| 51 | `Liked` | `S52` — tile 2 | MATCH | HIGH |
| 52 | `Stems` | `S52` tile 3; `S53` — toolbar tab | MATCH | HIGH |
| 53 | `Uploads` | `S52` — tile 4 | MATCH | HIGH |
| 54 | `New workspace` | `S52` — Workspaces header row (lowercase *w*) | MATCH | HIGH |
| 55 | `Search library` | — S52/S53 render a magnifier only; placeholder appears on expand (never captured) | CANNOT READ | — |
| 56 | `No songs found.` | `S58-empty-library.jpeg` — centred, period included | MATCH | HIGH |
| 57 | `Reset all filters` | `S58` — pill below | MATCH | HIGH |
| 58 | `Learn` | `S13-learn-menu.jpeg` + footer pill in every editor frame | MATCH | HIGH |
| 59 | `Keyboard Shortcuts` | `S13` row 1 (`shift ?`); `S14` overlay title | MATCH | HIGH |
| 60 | `Learning Center` | `S13` row 3 | MATCH | HIGH |
| 61 | `What's This?` | `S13` row 4; hover cards in `S15`, `S17`, `S19`… — apostrophe is **straight** (`'`), not curly | MATCH | HIGH |
| 62 | `Comments and notes` | `S55-comments-thread.jpeg`; also `S27`/`S48` clip rail | MATCH | HIGH |
| 63 | `Hidden tracks` | `S21-hidden-track.jpeg` — popover header | MATCH | HIGH |
| 64 | `Unmute all` | `S21` — row 2 | MATCH | HIGH |
| 65 | `Show All Hidden Tracks` | `S21` — row 3 (`shift alt H`); `S14` shortcut list | MATCH | HIGH |
| 66 | `NO ASSET LOADED` | `S44-convolution-card.jpeg` — IR slot, all caps, no period | MATCH | HIGH |
| 67 | `Add a track` | — S20 renders the menu **without** a heading; string exists only in the spec (§8.3) | CANNOT READ | — |
| 68 | `Import project` | — not in S07 (the captured project menu has `Open a copy in v1` there instead) | CANNOT READ | — |
| 69 | `Wavetable Designer` | `S11-settings-content.jpeg` — body copy "Sound-design tools like the **Wavetable Designer** and Impulse Response Designer" | MATCH | HIGH |
| 70 | `Sends` | — no frame; no literal label in our source either (gate matched inside `sanitizeSends`) | CANNOT READ | — |

**Found in a frame but absent from the corpus:** `Open a copy in v1`
(`S07` row 7, between `Share Project` and `Studio Settings`; 9 rows total, matching the
index's "9 items"). Our UI ships it (`StudioProjectMenu.tsx:487`), so the gate never
noticed the corpus omitted it.

**Copy note (not a defect):** `S60` shows a *Create-page* `New Workspace` with a capital
W, while the Studio library (§54) uses `New workspace`. The corpus records the Studio
form, which is correct for the surface it gates — but the two spellings are easy to
confuse when re-deriving strings.

---

## 5. Corrections

### 5.1 Frame-verified (apply as-is)

| # | Recorded | Correct | Evidence | Conf. |
|---|---|---|---|---|
| C-1 | `Download WAV` | `Download .WAV` | S26 row 11 (8× crop), S28 (2×), `ui-strings.json:17746`. **Reverts `a4740b0c`.** | HIGH |
| C-2 | `Save preset` | `Save preset…` (U+2026) | S46 row 2 shows three trailing dots; our label is U+2026 (`StudioPluginDock.tsx:859`) | HIGH on the characters, MEDIUM on glyph choice (U+2026 vs `...` — both are 3 dots in this font; U+2026 matches our shipped label) |

### 5.2 Not frame-verifiable — trailing characters dropped, same defect class

These six are never captured. Their recorded forms are **strict prefixes** of the shipped
labels, which is why `source.includes()` passes them. PIXEL_PARITY §95 records the
reference operation strings with the ellipsis; our labels carry U+2026.

| # | Recorded | Proposed | Basis | Conf. |
|---|---|---|---|---|
| C-3 | `Cover` | `Cover…` | PIXEL_PARITY §95; `StudioEditorShell.tsx:6707` | MEDIUM |
| C-4 | `Vocals` | `Vocals…` | §95; `:6737` | MEDIUM |
| C-5 | `Instrumental` | `Instrumental…` | §95; `:6754` | MEDIUM |
| C-6 | `Mashup` | `Mashup…` | §95; `:6776` | MEDIUM |
| C-7 | `Replace` | `Replace…` | §95; `:6794` | MEDIUM |
| C-8 | `Add FX` | `Add FX…` | clip-insert row, `:6818`; never captured | MEDIUM |

`Extend` and `Remaster` stay **bare** — PIXEL_PARITY §95 has no ellipsis for them and the
bundle string is bare `Extend`. Do not "fix" them.

### 5.3 Remove / relocate

| # | Item | Action | Evidence |
|---|---|---|---|
| C-9 | `Sends` | **Remove.** It is not a shipped label: the gate matched the identifier `sanitizeSends` in `StudioEditorShell.tsx:113/2521`. No frame, no bundle string, and `STUDIO_VS_SUNO_3COL.md` states "no FX sends … in any capture". | HIGH |
| C-10 | `Project (JSON)`, `Normalise mix to`, `Import project…` | **Move out of the captured-strings gate.** All three are our own additions (`StudioHeader.tsx:402/405`, `StudioProjectMenu.tsx:516`); `CLONE_DEFINITION.md` lists project JSON among permitted divergences. As long as they sit in `strings`, the gate compares our copy with itself. | HIGH |
| C-11 | `Open a copy in v1` | **Add** — frames show it, corpus lacks it | HIGH |

### 5.4 UI changes the corpus correction requires (not a docs edit)

- `camxora.com/components/studio/StudioEditorShell.tsx:6644` — `Download WAV` → `Download .WAV`
- `camxora.com/components/studio/StudioSongDetail.tsx:280` — `Download WAV` → `Download .WAV`
- `camxora.com/components/studio/StudioPluginDock.tsx:859` — already `Save preset…`; only the doc comments (`:66`, `studio-plugins.ts:323`) still say `Save preset.`

Do not apply these in this branch (docs-only worktree).

### 5.5 Proposed patch — `docs/studio/reference/FUNCTIONAL_STRINGS.json`

Abridged diff (hunk headers are illustrative; the array order is unchanged apart from
the one insertion). Applying it by hand gives the file below it.

```diff
--- a/docs/studio/reference/FUNCTIONAL_STRINGS.json
+++ b/docs/studio/reference/FUNCTIONAL_STRINGS.json
@@ -1,6 +1,7 @@
 {
-  "_comment": "Functional strings captured from Suno Studio and shipped by us verbatim. Prose is intentionally excluded (see CLONE_DEFINITION.md rule 5). YouTube Tutorials is the only sanctioned absence.",
+  "_comment": "Functional strings captured from Suno Studio and shipped by us verbatim. Prose is intentionally excluded (see CLONE_DEFINITION.md rule 5). YouTube Tutorials is the only sanctioned absence. Ellipses are significant: the clip menu reads 'Download .WAV' (dot) and menus that open a dialog end in U+2026. Every entry below is rendered by a frame in screens/ unless listed in _notCaptured.",
+  "_notCaptured": ["Project (JSON)", "Normalise mix to", "Import project…"],
   "strings": [
     "New Project",
     "Open Project",
     "Rename",
     "Duplicate Project",
     "Version History",
     "Share Project",
+    "Open a copy in v1",
     "Studio Settings",
     "Show Quick Start again",
@@
-    "Save preset",
+    "Save preset…",
     "Add effect",
     "Search plugins",
     "Create new plugin",
     "Audio",
     "MIDI",
     "Upload",
     "Add new track",
     "Rename track",
     "Collapse controls",
     "Expand controls",
     "Duplicate",
     "Hide & Mute Track",
     "Delete",
     "Copy",
     "Paste",
     "Heal Edits",
     "Split",
     "Clip Info",
     "Clip Color",
     "Get Stems",
-    "Download WAV",
+    "Download .WAV",
     "Download MIDI",
     "Get MIDI",
-    "Add FX",
+    "Add FX…",
     "Extend",
-    "Cover",
+    "Cover…",
     "Remaster",
-    "Vocals",
-    "Instrumental",
-    "Mashup",
-    "Replace",
+    "Vocals…",
+    "Instrumental…",
+    "Mashup…",
+    "Replace…",
     "All Songs",
     "Liked",
     "Stems",
     "Uploads",
     "New workspace",
     "Search library",
     "No songs found.",
     "Reset all filters",
     "Learn",
     "Keyboard Shortcuts",
     "Learning Center",
     "What's This?",
     "Comments and notes",
     "Hidden tracks",
     "Unmute all",
     "Show All Hidden Tracks",
     "NO ASSET LOADED",
     "Add a track",
     "Import project…",
-    "Wavetable Designer",
-    "Sends"
+    "Wavetable Designer"
   ]
 }
```

Resulting `strings` array (70 entries, file order, for paste-back):

```
New Project, Open Project, Rename, Duplicate Project, Version History, Share Project,
Open a copy in v1, Studio Settings, Show Quick Start again, Name project before sharing,
Copy Link, Full Song, Selected Time Range, Multitrack, Clear all settings, Save preset…,
Add effect, Search plugins, Create new plugin, Audio, MIDI, Upload, Add new track,
Rename track, Collapse controls, Expand controls, Duplicate, Hide & Mute Track, Delete,
Copy, Paste, Heal Edits, Split, Clip Info, Clip Color, Get Stems, Download .WAV,
Download MIDI, Get MIDI, Add FX…, Extend, Cover…, Remaster, Vocals…, Instrumental…,
Mashup…, Replace…, All Songs, Liked, Stems, Uploads, New workspace, Search library,
No songs found., Reset all filters, Learn, Keyboard Shortcuts, Learning Center,
What's This?, Comments and notes, Hidden tracks, Unmute all, Show All Hidden Tracks,
NO ASSET LOADED, Add a track, Import project…, Wavetable Designer
```

with `_notCaptured: ["Project (JSON)", "Normalise mix to", "Import project…"]` and
`"Sends"` removed. If the manager prefers not to change the schema, dropping only
`"Sends"` and applying C-1…C-8 is a safe subset — `check-clone-parity.mjs` reads
`.strings` only.

### 5.6 Gate hardening (recommended, separate change)

`camxora.com/scripts/check-clone-parity.mjs:190-206` tests `source.includes(text)`.
That check cannot fail for a dropped trailing `…`/`.` and cannot distinguish a label from
an identifier (`sanitizeSends` satisfied `Sends`). Two cheap fixes:

1. Require the match to sit between a JSX text boundary or a quote:
   `new RegExp('[>"]' + escape(text) + '[<"]')`.
2. Add the inverse check: every `se-` menu row label in our source must appear in the
   corpus (this is what would have caught the missing `Open a copy in v1` and the wrong
   `Download WAV`).

---

## 6. Cannot read — why (16)

| String | Why no frame shows it | Where the string really comes from |
|---|---|---|
| `Project (JSON)`, `Normalise mix to` | S49/S50 export menu has exactly 3 rows | our export additions (`StudioHeader.tsx:402/405`), `PROJECT_DECISIONS.md:360`, `IMPLEMENTATION_ROADMAP.md:71` |
| `Import project…` | S07 (9 rows) has `Open a copy in v1` where this would be | spec `ADV-011`; our menu `StudioProjectMenu.tsx:516` |
| `Sends` | no capture; no label | identifier match only (§5.3) |
| `Download MIDI` | S26/S28 clip menus show `Get MIDI`; PIXEL_PARITY §94 confirms the captured menu never had it | bundle `ui-strings.json:17762`; our row `StudioEditorShell.tsx:6808` |
| `Add FX…` | S26 has `Remove FX` only | clip inserts, PIXEL_PARITY §63; our row `:6818` |
| `Extend`, `Cover…`, `Remaster`, `Vocals…`, `Instrumental…`, `Mashup…`, `Replace…` | PIXEL_PARITY §95: "its clip menu was never captured" | reference operation strings + our rows `:6690-6794` |
| `Expand controls` | only the expanded state (⇒ `Collapse controls`) was captured | inverse label, `StudioTrackPanel.tsx:338` |
| `Search library` | S52/S53 show a magnifier; text appears only after expanding (PIXEL_PARITY §89) | `StudioLibrary.tsx:328` placeholder/aria-label |
| `Add a track` | S20 pops the menu with no heading; the heading exists only in the spec | spec §8.3 |

**Provenance defect:** `FUNCTIONAL_STRINGS.json` says "captured from Suno Studio", but at
least four entries were authored by us. That is the same failure mode as `Download WAV`
(asserting our copy as the reference's), and it inflates the gate's coverage claim
("70/70 present") by 4.

---

## 7. PAIRING / evidence cross-check

Method: for each screen number, the reference frame named by `SCREENSHOT_INDEX.md` was
compared with the `PAIRING.json` title. Titles verified as accurate: S01, S02, S04, S05,
S06, S07, S08, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25,
S27, S28, S29, S30, S31, S32*, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43*,
S44, S45, S46, S47, S48, S49, S50, S51, S52, S53, S54, S55, S57, S58, S59, S60, S61, S62,
S63, S64, S65 (*with the caveats below). Dimensions confirm the viewport titles:
S63 = 1280×900, S64 = 1024×900, S65 = 767×1000 / 768×1000.

**Evidence defects:**

| Screen | PAIRING title | What the frame actually shows | Action |
|---|---|---|---|
| **S56** | `Shared link logged out` | the **marketing hero**, identical to S01: "Studio 2.0: Be a control freak.", `Log in` / `Open Studio`, nav Products/Resources/Pricing/Careers. No share token, no logged-out share gate. (Confirms Agent B.) | re-capture, or record as a corpus gap (`RECORDED GAP`); do not diff against it |
| **S43** | `Compressor sidechain` | the only reference frame is `screens/S46-compressor-routing-list.jpeg` (the sidechain menu listing every track as `— Pre-fx` / `— Post-fader`), which the index maps to S43 but is **filed under S46**. The residual plan therefore counts S43 as "no reference frame" while a frame exists. | copy/rename to `S43-compressor-routing-list.jpeg` (or add an alias in the pixel harness) and fix the index; S46 keeps its own `S46-preset-menu.jpeg` |
| **S03** | `Signed-in entry reopened` | frame is the onboarding overlay over an empty editor (same state as S06). Nothing in it evidences "reopened". | rename to `Onboarding overlay (entry)` or re-capture the reopened-project state |
| **S20** | `Add track menu` | frame shows the 3-row menu with **no** `Add a track` heading (the index text implies one) | fix `SCREENSHOT_INDEX.md`, not PAIRING — this is what made `Add a track` look frame-attested |
| **S08** | `Version history` | panel header reads `History`; the `Version History` *string* is verified in S07, not S08 | cosmetic; leave title |
| **S38** | `Model picker` | 3 model rows + `Create Custom Model (Beta)` (index says "4 cards") | fix the index description |

`S12`/`S54` both legitimately show the share dialog (unnamed vs named project) and
`S05`/`S16` share the empty-editor state — those `sharedWith` links are honest.

---

## 8. METRICS.json — what a frame can prove

Measured on `S17-editor-loaded-project.jpeg` (1689×1277, DPR 1) by pixel scan.

| id | expected | frame measurement | verdict |
|---|---|---|---|
| `rowStep` | 86 | accent-strip starts at y = 82, 168, 254, 340, 426, 512, 598, 684, 770, 856, 942, 1028 → **pitch 86 exactly** | **frame-verified** |
| `trackRowHeight` | 85 | colour strip spans y 82→167 = **86** | frame-verified ±1 (the 85 came from a 1958 px viewport; treat 85/86 as the same row) |
| `barWidth` | 96 | ruler labels `1,3,5,…` at ~191 px per 2 bars ⇒ **95.5** | frame-verified ±1 |
| `pillHeight` | 36 | header `Export`/`BPM` pill spans y 8→43 ⇒ **35–36** | frame-verified |
| `gutterWidth` | 260 | gutter bg → lane bg transition at **x = 266** | **+6 px off** at this viewport — re-probe, do not cite as measured |
| `transportTarget` | 36 | not cleanly separable from the transport pill in S17 | probe-only |
| `footerHeight` | 52 | the footer band is partially occluded by the Magic Bar in every full frame | probe-only |
| `footerGroupHeight` | 36 | same | probe-only |

Consequence: the `check:clone` note "metrics 8 asserted at 0 tolerance" is true of **our own
probe**, but 4 of the 8 numbers cannot be sourced from these frames. Recommend the
metrics comment stop implying all 8 were read off the capture set: mark the four
probe-only rows and re-measure `gutterWidth` at the 1689 viewport.

---

## 9. Recommendations (ordered)

1. **Revert `a4740b0c`** and fix the two UI labels to `Download .WAV` (§5.1, §5.4). This is
   the only item that changes what the product shows.
2. Apply C-2…C-8 (ellipses) and C-9 (drop `Sends`), C-11 (add `Open a copy in v1`).
3. Move `Project (JSON)`, `Normalise mix to`, `Import project…` to `_notCaptured` so the
   coverage number means something.
4. Fix S56 and the S43 filename, then re-run `check:clone` and the pixel harness.
5. Harden the string gate (§5.6) so a dropped trailing character can never pass again.

---

## 10. Limitations

- Frames are JPEG at native scale; sub-pixel antialiasing means a `…` and `...` cannot be
  distinguished absolutely. C-2 is therefore recorded as "three dots present, glyph
  U+2026" with that caveat.
- 16 strings have no frame at all (§6), so this audit cannot make them right — only make
  them honest.
- S56, S43, S03 and the S20/S38 descriptions are index/pairing defects, not string
  defects; fixing them needs a new capture, which is W3's scope.
- No server, no `:3103`, no deploy, no push was used for this audit.

---

*W8 — corpus audit. Branch `qa/corpus-audit`. Reference files unchanged; patch proposed in §5.5.*
