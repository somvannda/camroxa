# Studio manual QA: nine defects the independent runs found, all fixed with regressions

**Date:** 2026-11-17
**Surface:** `camxora.com/components/studio`, `camxora.com/app/globals.css`, `camxora.com/tests/e2e`
**Found by:** three independent manual runs — `2026-11-17-manual-run-b-e.md`,
`2026-11-17-manual-run-c.md`, `2026-11-17-manual-run-adf.md`

## Summary

510 checks were executed in a real browser against real fixtures: B (plugins, 138) + E
(viewports, 24), C (menus, dialogs, settings, home, share, onboarding, 210) and A (entry and
gates, 16) + D (arrangement, clip, warp, MIDI, 88) + F (async boundaries, 33). The rows that
failed were triaged into product defects and harness/fixture problems; every product defect
below has a regression that fails on the old code.

## Keyboard and focus

**C-08 — `ctrl shift ,` never opened Studio Settings from a real keyboard.** Shift+Comma
produces `key: "<"` (code `Comma`); the handler demanded `","`. Playwright's synthetic comma
masked it. The handler now accepts `,`, `<` and `code === "Comma"`, and the settings test
presses the physical `Shift+Comma`.

**C-109 — `Rename track` focused the field but left the caret at the end.** `onFocus` now
selects the whole name, so typing replaces it. The track test asserts
`selectionStart === 0 && selectionEnd === value.length`.

**D-71 — the first `Shift+1` after opening Clip Settings was dropped.** The panel's `keydown`
listener was re-subscribed on every render (the `onWarp` prop is an inline arrow); a re-render
caused by another keydown listener removed and re-added the listener *during* dispatch, and a
listener re-added mid-dispatch is not called for that event. Instrumentation showed capture
reaching `window`, the shell handler running, then “listener removed/attached” before the
panel's bubble listener could run. The listener is now attached once in a layout effect and
dispatches to the latest handler through a ref. Measured before: `1/8 → 1/8` then `1/16`.
After: `1/8 → 1/16` on the first press.

## Pointer and layout

**C-130 — the group chip collapsed only one member.** Each member was updated with
`updateTrack`, which maps over a `tracks` snapshot captured before the first update. One
`toggleGroupCollapse` now writes the whole group from `tracksRef`; the test adds a second
member and asserts both collapse in one saved document.

**D-43 — the footer Loop flipped the flag but seeded nothing.** The footer button was wired to
a bare `setLoop`; the header button and `Ctrl+L` go through `toggleLoop`, which seeds four
bars and persists `loopEnd`. Both surfaces now share `toggleLoop`. Test: footer click yields
one `.se-loop-band` and a stored `loopEnd` of 8 s at 120 BPM.

**A-14 — a fresh load rendered an empty bottom band.** The dock rendered only when
`selectedTrack` was set, and a fresh project selects nothing. The band now renders its shell
with “Select a track to see its effects.” and yields to the plugin dock on selection.

**D-50 — section-marker labels truncated at the widest zoom-out.** The label span was
absolutely positioned with only `left`, so it shrink-wrapped to the 16 px marker box (48 px/bar
zoom). `width:max-content; max-width:none` keeps the text.

## Errors that were invisible

**C-11 — a failed project-menu action was silent.** Every row closes the menu first, and the
error was rendered inside that menu, so the user saw nothing. The error now also renders
outside a closed menu (`role="alert"`), suppressed while a dialog is open because dialogs
print their own copy. Test: Duplicate is mocked to 500 and the alert is asserted after the
menu closes.

## Earlier in the same pass (area B/E)

EQ drag now moves Freq (`1khz → 16.6khz`, no trailing `.0`), the undo rail refreshes per undo
(2 → 0 → 1 → 2 slots), chorus settings are sanitised on load, the clip menu scrolls
(`overflow-y:auto`, 889 of 1070 px inside 768×1024), a load failure shows its panel, upload
metadata and the kHz readout are correct, the 768 px header keeps its controls, and the popped
out plugin is a placeholder rather than a blank card.

## Verification

Typecheck clean · Vitest **415** · Playwright **201 passed / 2 skipped / 0 failed** (64 product
specs, 7.2 m) · `check:ui` and `check:mojibake` clean · `check:clone` satisfied (73/73 screens,
8 metrics at 0, 70/70 strings).

The two skips are the env-gated rows (`STUDIO_UPLOAD_PROXY_URL`, `STUDIO_EXPECT_UPLOADS`)
that need a storage-backed upload path; they are unrelated to these fixes.

## Also fixed in the QA tooling

`scripts/dev/provider-matrix.mjs` refused a healthy stack because the **first** Node fetch to
MusicAPI on this host stalls past the 10 s guard and later calls answer in ~1 ms. The
precondition probe now retries three times with its own timeout per attempt, and a negative
`/web-music/studio/readiness` snapshot is re-read once. A genuinely broken stack still fails.
