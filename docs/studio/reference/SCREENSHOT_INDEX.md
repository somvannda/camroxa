# SCREENSHOT INDEX

Evidence archive for the 65-screen contract. One file per captured screen, named
`S<nn>-<slug>.jpeg` in `screens/`.

**The rule:** a row in `SCREEN_MANIFEST.md` may only be `DONE` if it has both a
spec section and a file listed here. `PART` means the section exists but the
evidence is incomplete.

Backfill status is deliberately visible: **26 captures cover 22 of the 31 DONE
rows.** The rest were documented from live DOM measurement and earlier sessions,
before this archive existed — they have a spec section but no image. They are not
being re-marked `PART` in bulk; each one is promoted to fully evidenced as it is
re-shot.

## Captured

| Screen | File | What it shows |
|---|---|---|
| S01 | `screens/S01-marketing-signed-out.jpeg` | `/studio-welcome` hero, nav, CTA — signed out |
| S02 | `screens/S02-sign-in-modal.jpeg` | `Welcome to Suno` modal over the dimmed marketing page — 3 providers + 3 secondary |
| S03 | `screens/S03-signed-in-entry-reopened.jpeg` | `/studio` reopening the last project + onboarding overlay |
| S04 | `screens/S04-my-projects-modal.jpeg` | My Projects modal — grid, `Legacy` tags, mini-timeline thumbnails |
| S05 | `screens/S05-empty-project.jpeg` | New project, one `Audio Track`, overlay dismissed |
| S05 | `screens/S05-zero-tracks-after-remount.jpeg` | Same project after a remount — **zero** tracks (pre-autosave) |
| S06 | `screens/S06-onboarding-overlay.jpeg` | `How do you want to start?` over the empty project |
| S07 | `screens/S07-project-menu.jpeg` | Project menu — 9 items, Settings accelerator |
| S15 | `screens/S15-whats-this-card.jpeg` | Hover card on `120 BPM` — light 256 px card, `Tempo` + body, anchored under the control |
| S16 | `screens/S16-editor-empty-project.jpeg` | Empty project: one `Audio Track`, `Add new track`, `00:00.000`, Magic Bar with `Tab` hint |
| S17 | `screens/S17-editor-loaded-project.jpeg` | Drum & Bass Demo at 174 BPM — 12 tracks, clips, FX strip, `Press play to hear the demo` |
| S18 | `screens/S18-track-row-anatomy.jpeg` | Track row and clip band measured from the loaded demo |
| S19 | `screens/S19-track-options-menu.jpeg` | Track options menu, 6 items with icons |
| S08 | `screens/S08-version-history.jpeg` | History panel populated — date navigator, expanded newest entry |
| S08 | `screens/S08-version-history-loading.jpeg` | Same panel in its `Loading...` state |
| S09 | `screens/S09-settings-performance.jpeg` | Studio Settings → Performance, ghost-drag toggle on |
| S10 | `screens/S10-settings-window-management.jpeg` | Studio Settings → Window management, 3-way segmented control |
| S11 | `screens/S11-settings-content.jpeg` | Studio Settings → Content, auto-stretch on / advanced off |
| S12 | `screens/S12-share-naming-gate.jpeg` | Share blocked on an unnamed project — `Name project before sharing` |
| S12 | `screens/S12-share-dialog.jpeg` | Share dialog — view + fork copy, Done / Copy Link |
| S13 | `screens/S13-learn-menu.jpeg` | Learn popover — 4 rows, `shift ?` meta, `What's This?` on |
| S14 | `screens/S14-keyboard-shortcuts.jpeg` | Shortcuts overlay — 2 columns, per-key chips, `GENERAL` … `CLIP EDITOR · MIDI` |
| S20 | `screens/S20-add-track-menu.jpeg` | `Add a track` — Audio / MIDI / Upload |
| S26 | `screens/S26-clip-context-menu.jpeg` | Clip menu, complete variant — 13 items, accelerators, `Clip Color ▸` |
| S57 | `screens/S57-project-loading-blank.jpeg` | Load state: blank frame, `canvas` 0, no text |
| — | `screens/RESPONSIVE-gate-319px.jpeg` | §60 desktop-only gate at 319 px (no manifest row) |

## Missing — DONE rows with no image yet (9)

| Screen | Spec | Needs |
|---|---|---|
| S34 | §54 | Magic Bar idle |
| S35 | §54 | Magic Bar with attachment |
| S38 | §6 | model picker |
| S39 | §48 | add-plugin catalog |
| S40 | §50 | plugin dock, one slot |
| S41 | §50 | plugin dock, several slots |
| S49 | §18.2 | Export menu |
| S52 | §19 | library workspaces |
| S65 | §46 | ~706 px narrow editor |

## Capture rules

1. Screenshot **first**, while the screen is open. Session temp files are deleted;
   copy the file into `screens/` before moving on.
2. Prefer a named state over a clean-looking frame: a menu open, an error shown,
   a value mid-drag.
3. Keep the desktop window visible — screenshots fail with
   `Screenshot needs a visible tab` when it is minimised or behind.
4. Never re-use one file for two rows. If two screens genuinely appear in one
   frame, capture twice.
5. Write this file with an editor or the write tool, **not** PowerShell
   `Set-Content -Encoding utf8` — it adds a BOM and mangles `—` and `§`.
