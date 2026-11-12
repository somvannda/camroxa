# SUNO STUDIO INTERACTION SPECIFICATION

Behaviour contracts per control. Format: **initial → interaction → expected result →
failure**. A control with no row here is not allowed to ship.

## 1. Global

### 1.1 Keyboard map

| Key | Context | Action |
|---|---|---|
| `Space` | editor, no text field focused | play/pause |
| `Cmd/Ctrl+Z` | editor | undo |
| `Cmd/Ctrl+Shift+Z` | editor | redo |
| `Delete` / `Backspace` | clip focused, no text field | delete clip |
| `S` | editor | split selected clip at playhead |
| `D` | editor | duplicate selected clip |
| `M` | track selected | mute/unmute track |
| `L` | editor | toggle loop |
| `R` | editor | arm record |
| `←` / `→` | editor | seek −/+ one grid step |
| `Home` / `End` | editor | seek to start/end |
| `Escape` | any overlay | close overlay, restore focus |
| `Cmd/Ctrl+C/V` | clip focused | copy/paste clip (not yet implemented — ARR-014) |

Gate: musical typing and single-letter shortcuts must be disabled whenever the
event target is an `input`, `textarea`, `select`, or `contenteditable`.

### 1.2 Autosave

- Initial: `saved` when the document matches the server.
- Any arrangement mutation → `saving` after a short debounce.
- Success → `saved` + "Saved just now" relative time.
- Failure → `error` with the message and a **Retry** action; the document stays
  dirty and retries are not automatic beyond one backoff.
- No mutation while idle.

## 2. Header

### 2.1 Project title (APP-010)
Inline editable text. `Enter` or blur commits; `Escape` reverts. Empty title is
rejected and reverts. Commit goes through the same autosave path.

### 2.2 Undo / Redo (APP-009)
Disabled when the respective stack is empty. Undo restores the previous arrangement
snapshot *and* selection if the selection still exists. Bounded depth; oldest
snapshot is dropped.

### 2.3 Export (APP-012, ADV-006..012)
1. Click opens the export menu with format (WAV/MP3), range (full/loop/selection),
   and targets (mix, per-track, stems).
2. Running shows progress and a cancel that aborts encoding and leaves the project
   untouched.
3. Refusal (policy/moderation) is shown verbatim with a retry that is disabled until
   the user changes the content.
4. Success triggers a file download; no server state changes.

### 2.4 Share (PRJ-011..013)
Create link → choose permission (view/edit) and expiry → copy. Revoking makes the
token terminal for everyone; the dialog states this before confirming.

## 3. Tracks

### 3.1 Add track (TRK-001/002/003/004)
Menu offers audio, MIDI, import audio, import MIDI. Choosing audio inserts an empty
lane at the bottom and selects it. Import opens a file picker; invalid files produce
an inline error on the new lane row, never a silent no-op.

### 3.2 Volume / pan (TRK-011/012)
Continuous controls. Value changes are applied to audio immediately (preview) and
committed to state on change end, so a single drag produces one history entry.

### 3.3 Mute / Solo (TRK-013/014)
Independent booleans. Solo on any track mutes all non-soloed tracks for playback and
render, and must be reflected in the mixer. Muting a soloed track clears solo? No —
solo wins; the UI shows both states distinctly.

### 3.4 Delete track (TRK-009)
Confirmation names the track and states how many clips will be removed. Deleting the
last track leaves an empty project, not a broken editor.

### 3.5 Reorder (TRK-007)
Moves the lane and its clips atomically; undo restores order.

## 4. Clips

### 4.1 Drag (ARR-008/009)
- Pointer-down on a clip body starts a *pending* drag.
- Movement under 3 px keeps it a click (selection only).
- Once past threshold, a translucent ghost follows the pointer, snapped per grid.
- Dropping inside another clip is allowed (overlap), but the clip must be visible
  and selectable.
- `Escape` during drag cancels and restores the original position.

### 4.2 Trim (ARR-010)
Edge handles only. Minimum clip length is 3 units (`MIN_CLIP`). Trimming changes the
source offset, not the source file. `Escape` cancels.

### 4.3 Split (ARR-011)
Splits at the playhead, producing two clips that together cover the original span
with no gap or overlap. Both keep the source id; the second carries a new clip id.

### 4.4 Delete (ARR-013)
Immediate, undoable. Focus moves to the nearest remaining clip on the same lane, or
to the lane header if none.

### 4.5 Fades / speed / volume / pan (ARR-016..019)
Edited in the inspector, previewed live, committed on release. Values are clamped to
documented ranges; out-of-range input is rejected with an inline message.

### 4.6 Context menu (ARR-023)
Right-click or the row's menu button opens: split, duplicate, reverse, colour, take,
remove from session. Menu items that cannot apply are disabled with a reason tooltip.

## 5. Transport

### 5.1 Play (PLY-001)
Starts from the playhead, respects loop region, pauses the global player, and
resumes scheduling from the current time. Audio context is created on first play
(user gesture).

### 5.2 Loop (PLY-014)
When enabled, playback wraps from loop end to loop start. Loop handles are editable
numerically and by dragging in the ruler; start must be < end (invalid input is
rejected, not clamped silently).

### 5.3 Metronome (PLY-013)
Clicks on every beat with a downbeat accent from the first time-signature entry.
Toggling while playing starts/stops clicks without interrupting audio.

## 6. Paid operations (GEN-014..023, ADV-001..003)

Contract for every one:

1. Confirm dialog states the action, the target clip, and the credit cost from
   `getStudioPricing`.
2. Confirm → optimistic row on the clip ("Preparing…") → polling
   `getStudioOperation`.
3. Success → result placed on the timeline with a link to the source clip; credit
   deduction visible in the balance.
4. Failure → the credit charge is reversed, the message shown on the clip, and a
   retry offered.
5. Insufficient credits → dialog shows the shortfall and a purchase path; the
   operation is not started.

## 7. Home (new)

### 7.1 New project
Creates a project named "Untitled project" with the default BPM/time signature, then
navigates to `/studio/editor?project=<id>`. The button is disabled while the request
is in flight and re-enabled on failure with an inline error.

### 7.2 Open project
Navigates to the editor deep link. The editor loads that exact project; if the id is
unknown or not owned, it shows a terminal error with a link back to `/studio`.

### 7.3 Rename / duplicate / pin / archive / delete
Each is a direct API call with optimistic UI and rollback on failure. Delete requires
typing-free but explicit confirmation naming the project.

### 7.4 Search and sort
Client-side over the loaded page (50). Search matches title and tags. Sort is
`updated` (default, pinned first) or `title`. Clearing search restores the full list.
