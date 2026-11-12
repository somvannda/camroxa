# SUNO STUDIO UX ANALYSIS

Reference-first analysis of interaction quality, then what ours does and what it
must fix. Evidence tags per `README.md`. Nothing here is speculation presented as
fact: unverified behaviours are marked `?` and must not be built.

## 1. Principles extracted from the reference

1. **The arrangement is the page.** Chrome is minimal and dark; the timeline takes
   the viewport. Panels slide over rather than push layout.
2. **No modal for the primary act.** Generating or adding audio happens at the
   playhead, not in a wizard.
3. **Everything is persisted, nothing is "Save"d.** (H) There is no save button; the
   document is continuously versioned. Visible save state is therefore about
   *trust*, not control.
4. **Progressive disclosure.** Transport essentials are always visible; BPM, grid,
   zoom and master live in the footer; per-clip depth is in the inspector.
5. **Destructive actions confirm; creative actions do not.** Delete asks; split,
   duplicate, fade, reverse act immediately and are undoable.
6. **Every paid action shows its cost first.** (B) Credits are money; a silent spend
   is a UX defect.
7. **Failure is stated in the user's terms.** Provider refusals are surfaced as a
   sentence next to the object that failed, not a toast that disappears.

## 2. Region-by-region assessment

### 2.1 Landing → editor

- Reference: the landing is a *chooser* (resume, recent, start-from-song) (`H P`).
- Ours: `/studio` is marketing copy; the DAW is at `/studio/editor` with an in-app
  project dialog. A first-time user must guess that the editor exists.
- Verdict: **structural gap.** Fix is roadmap W1. Severity: high.

### 2.2 Header

- Ours carries project switcher, title, undo/redo, versions, share, export and
  panel toggles. Density matches the reference, but undo/redo and save state are
  visually equal to destructive/paid actions.
- Fixes: group *reversible* actions (undo/redo) left, *committing* actions
  (versions, share, export) right, and move save state next to the title where the
  mental model lives ("is my work safe?").

### 2.3 Track panel

- Ours: number, name, colour, volume, pan, mute, solo, meter, collaborator avatars,
  groups, add-track, per-track menu. This exceeds the reference's observed density
  and is defensible for a professional tool.
- Risk: seven controls per row in a narrow column → cramped targets below 1280 px.
  Mitigation: collapse to name + meter + M/S under 1100 px, full controls in the
  mixer, which is where a professional expects them.

### 2.4 Timeline

- Working: ruler, grid, zoom, playhead drag, clip drag/trim/split/duplicate/delete,
  cross-lane drag, drop from library, markers, loop region, snap.
- Missing vs. reference: marquee multi-select (ARR-025), multi-clip drag, copy/paste
  (ARR-014), snap guideline (UX-005), virtualisation (ARR-031).
- Interaction defects to fix:
  1. A drag begins on pointer-down; there is no threshold, so a click that moves 2 px
     repositions a clip. Add a 3 px threshold before committing to a drag.
  2. Trim handles are only visible on hover; on touch there is no affordance.
  3. Deleting a clip does not move focus anywhere, so keyboard users lose position.

### 2.5 Inspector

- Ours: clip timing/mix/fades/speed/takes, track EQ/filter/sends/dynamics/presets,
  automation editors, lyrics, personas, piano roll. Very complete.
- Defect: the inspector has no empty-selection teaching state beyond one line; a new
  user gets no hint that clips and tracks edit different things.
- Fix: two-tab empty state ("Select a clip" / "Select a track") with a one-line
  explanation of each.

### 2.6 Library drawer

- Ours: songs/liked tabs, search, filters, drag-to-lane, click-to-add. Missing
  uploads/stems/projects tabs (PRJ-022..024) — deliberate until the source exists.
- Defect: with zero results the drawer shows an empty list and no recovery action.
  Fix: "No songs match" + clear-filters button.

### 2.7 Footer / transport

- Ours: start/play/end, clock, bar.beat, BPM, grid, zoom, loop, metronome, master,
  Studio AI. Density is right.
- Defect: the clock has three competing time representations without labels; a user
  cannot tell which is bars and which is time. Fix: label on hover + `aria-label`.

## 3. State coverage audit

| State | Required | Ours | Note |
|---|---|---|---|
| Project loading | skeleton, no layout shift | partial | add a fixed-height skeleton |
| Project empty | teach the first action | yes | "Create a track" |
| Project failed to load | message + retry + back | yes | |
| Save in progress | subtle, non-blocking | yes | |
| Save failed | persistent, retryable | yes | no retry button yet |
| Conflict (shared) | choose reload/re-apply | no | W2.2 |
| Offline | banner + local draft | no | W2.3 |
| Generation queued | placeholder on the lane | yes | |
| Generation failed | provider message on the clip | yes | |
| Insufficient credits | cost + purchase path | yes | |
| Export running | progress + cancel | yes | |
| Export refused (moderation) | verbatim reason | yes | |
| Permission denied (share) | terminal, no loop | yes | |
| Empty library/search | recovery action | partial | add clear-filters |

## 4. Keyboard model

Implemented: `Space` play/pause · `Cmd/Ctrl+Z` undo · `Cmd/Ctrl+Shift+Z` redo ·
`Delete`/`Backspace` delete clip · `S` split · `D` duplicate · `M` mute ·
`L` loop · `R` record · `←/→` seek · `Home/End` start/end · `Escape` close menu.

Gaps:

- No `?` shortcut sheet (UX-017 shows a static help popover; bind `?` to it).
- No `Tab` order contract inside the timeline; clip focus is mouse-only.
- No `Cmd/Ctrl+C/V` for clips (ARR-014).
- Musical typing swallows letters when a text field is not focused; must be gated on
  "no editable element focused" (verify, then test).

## 5. Accessibility

- Icon buttons generally carry `aria-label` (verified by extraction: 60+ labels).
- Missing: focus-visible styling audit across the footer, `aria-live` for save and
  export status, reduced-motion support, 44 px touch targets, and a skip link into
  the timeline.
- Plan: W5.5 axe pass, then fix by severity. Do not claim compliance before the run.

## 6. Copy and tone

- Reference uses short, confident, second-person copy (`H`). We keep the tone but
  never copy lines verbatim; all Studio strings are original Camxora copy.
- Error copy rule: what happened → why → what to do. Example:
  "Couldn't save this project. The server rejected the write (409). Reload to get the
  latest version, then re-apply your change."
