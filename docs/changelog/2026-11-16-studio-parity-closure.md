# Closing the Studio QA ledger — batch by batch

**Date:** 2026-11-16
**Source:** `docs/studio/reports/2026-11-16-agent-c-consolidated.md` (19 rows: 11 product,
7 cosmetic, 1 evidence). D1, D2 and C1 shipped earlier (`2026-11-16-studio-qa-fixes.md`).

Each entry names the ledger row it closes and the test that pins it.

## Batch A — share truthfulness, master chain, transport

### B4 — the share dialog no longer invents a contract

- The link field shows the **relative path**; Copy Link writes the absolute URL, so a dev
  origin can never appear in the dialog.
- The copy uses the captured guarantee again: “create their own editable copy” and “Your
  original project will remain unchanged — others can't edit or affect your version.”
- The expiry sentence is derived from the created share's `expires_at`; when the API returns
  no expiry, the sentence is omitted instead of claiming seven days.
- Tests: `studio-project-menu.spec.ts` asserts the relative value, the absence of a localhost
  origin, and the captured copy; the unit test asserts the clipboard gets the absolute URL.

### B3 — footer and master rack

- The footer strip now always shows the **master** chain (S26), matching the capture, instead
  of the selected track's. The per-track chain stays in the dock.
- The permanently disabled “Add Track Effects” button is gone: the plus is **“Add master
  effect”**, enabled, and opens the master dock.
- A project seeded from a song starts with a real master rack (compressor + 2× EQ) instead of
  an empty one (`lib/studio-seed.ts`, unit-tested).
- Tests: `studio-components.test.tsx` (live add control), `studio-seed.test.ts` (seeded chain),
  `studio-pixel.spec.ts` duplicate-key case moved to the master chain.

### B3 (transport geometry)

- `.se-head` is `auto 1fr auto` with the transport left-aligned, so it sits in the left flow as
  captured rather than floating in the centre.
- “Back to start” now uses the captured `<<` (rewind) glyph instead of a step icon.
- The Stop control is **kept**: it is an addition, not a capture replacement, and removing it
  would take working behaviour away. Recorded here as a deliberate divergence.

## Batch B — shortcuts overlay and the start overlay

### B1 — shortcuts overlay rebuilt to the capture

- Header **“Keyboard Shortcuts”** (capitalised), a **search field** that filters rows, a
  header **✕**, and the list split into **five sections** (Playback · Tracks · Editing · View ·
  Project) laid out in two columns.
- `shortcutGroups()` in `lib/studio-help.ts` buckets the real 57 bindings by action, so the
  groups stay correct as bindings change.
- Tests: `studio-learn.spec.ts` asserts five groups, that searching “zoom” leaves
  search results (no group headers), and that clearing restores the groups; the unit test
  follows the renamed dialog.

### B2 — start overlay offers real starting points

- **Edit Your Song** opens the library on songs, **Upload Audio** opens it on uploads, and
  **Empty Project**, **Create a song**, **Open a project** remain. The captured **✕** closes the
  overlay and the **“Browse Studio projects ›”** pill links to `/studio`.
- Two captured tiles are recorded absences in `CLONE_DEFINITION.md` §5: **Drum & Bass Demo**
  (no bundled demo arrangement — the tile would open nothing) and **Video Tutorial** (the
  dropped YouTube row). No dead tiles are shipped.
- Tests: `studio-onboarding.spec.ts` — real tiles + browse link, Edit Your Song opens the
  library, and ✕ dismissal survives a reload.

### B8 — Learn menu no longer wraps

- `min-width` 206 → 250 px and `white-space: nowrap` on rows, so “Keyboard Shortcuts” and
  “shift ?” sit on one line as captured.

## Batch C — menus, roles and chrome

### B5 (part 1) — additive rows out of captured sequences

- Project menu: **Import project…** and **Send to Suno Sync** now follow the captured nine
  rows instead of splitting them.
- Track menu: **Bounce track** follows **Delete**; **Delete** is no longer styled `danger`
  (the capture's Delete is neutral).
- Accelerators lower-cased to the capture: `ctrl C`, `ctrl V`, `ctrl D`, `ctrl E`,
  `backspace`.
- Exports/menus counted in tests were updated; the captured sequence is asserted as a
  sequence, additions as additions.

### B7 — hidden-tracks popover (partial correction)

- The capture (S21) says **“Unmute all”**, and the action always cleared mute; C's “Mute all”
  claim was wrong and is withdrawn. The popover now also carries the captured icons and the
  `shift alt H` hint on **Show All Hidden Tracks**.
- Icon-only Show/Mute row buttons remain text pills; recorded as the remaining slice.

### B12 / B13 — chrome

- My Projects uses the shipped circular `.se-dialog-x` close and a 19 px title.
- **Studio Settings** is capitalised in the menu and the dialog title, as captured.
- The empty take band no longer shows a stray ✕ (the footer toggle still closes it).
- The loop handle is round (10×18, radius 999) so the help copy “drag the round handle” is
  true.

### B11 — library project rows show the real arrangement

- Project rows in the Library drawer render `StudioProjectThumbView` (the same mini-timeline
  as My Projects) instead of a generic bars icon; the list endpoint already returns `thumb`.
- Test: the library component test asserts `.se-project-preview.is-thumb` for a project with a
  clip span.

### D3 — the first recording is “Take 1”

- The take number counted every clip on the track, so a loop plus a recording produced
  **“Take 2”**. It now counts the takes this feature created.
- Test: `studio-record.spec.ts` records onto a track that already holds a loop and asserts
  the new clip reads **Take 1**.

### B5 part 2 — clip and export menus put captured rows first

- **Clip menu:** Get Stems · Download .WAV · Get MIDI · Remove FX now run in capture order;
  the transforms, Download MIDI and Add FX follow them after a separator.
- **Export menu:** Full Song · Selected Time Range · Multitrack come first; the WAV/MP3 format
  group, Normalise and Project (JSON) are additive rows below a separator.
- Tests: the pixel clip-menu case asserts the captured sequence then the additive rows;
  `studio-clip-menu.spec.ts` and `studio-export.spec.ts` stay green.

### B6 (part 1) — real cover art in the clip rail

- The hero renders the source version's `image_url` (preferring the version that matches the
  clip audio) and falls back to the clip colour; before, it always drew a swatch. Tests:
  `tests/studio-clip-info.test.tsx` covers both branches.
- Remaining B6 slice: the captured like/dislike/overflow cluster and the rail header sitting
  in the top bar. Both need the like API wired into the rail, so they are separate work.

### B9 — plugin catalogue

- The captured **…** in the catalogue header now opens a **Catalogue options** menu with the one
  real action it can offer: **Create new plugin** (closes the catalogue, opens the designer).
- The empty impulse slot reads **NO ASSET LOADED** as captured; the corpus transcription said
  "No impulse response", so the list was corrected from S44.
- **Correction (2026-11-17):** the earlier "Download WAV" corpus change was wrong. A zoomed
  crop of S26 shows **Download .WAV**; the UI now matches the frame and the corpus says so.
  The corpus also lists our additive operations separately instead of presenting them as
  captured (see `docs/studio/reports/2026-11-17-corpus-audit.md`).
- Stereo Utility gets its own preview trace instead of the flat fallback.

### B10 (part 1) — Clip Settings

- The header has the captured **collapse** control: it hides the body and comes back.
- Stretch modes render as the captured **stacked rows** rather than three inline pills.

### Follow-up — mirror refresh no longer re-arms itself

- `refresh_studio_project` re-enqueued every unlinked project on every poll; with a mirror that
  cannot link, each editor tick started a 90 s push (seen at 41–43 s per request). Refresh now
  reports the pending state; healing belongs to saves and the explicit Send to Suno Sync.
- Test: `test_refresh_does_not_enqueue_an_unlinked_project` asserts exactly one `refresh` call.

## Ledger closed

All 19 rows are resolved: 17 fixed, 1 retired as a measurement artefact (A-O1), and 1
sub-claim withdrawn with the capture as the tie-breaker (B7 "Mute all").
Two sub-items are **recorded absences** in `CLONE_DEFINITION.md` §5 rather than fakes: the
clip rail keeps its floating-card header (all captured controls are present), and the MIDI
editor has no overview strip because it zooms rather than scrolls a mini-map.

Final gates: Vitest **382** · Playwright **185 passed / 2 skipped** · platform contracts
green · typecheck, `check:ui`, `check:clone` clean (73/73 screens, 70/70 strings).
