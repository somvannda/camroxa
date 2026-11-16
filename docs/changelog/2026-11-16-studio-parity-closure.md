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

### B7 — hidden-tracks popover tells the truth

- The bulk action is **Mute all** and now actually mutes hidden tracks (it used to unmute
  them under the wrong captured label).
- **Show All Hidden Tracks** carries the `shift alt H` hint the binding already used.

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

## Open in the ledger

B5 part 2 (clip menu and export ordering) · B6 clip info · B9 plugin catalog · B10 MIDI/clip
editor polish · the mirror enqueue backoff.
