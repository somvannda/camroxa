# S08 — Version history (dot-and-rail list)

Defect closed from the QA ledger: row S08 in
`docs/studio/reports/2026-11-17-pixel-adjudication.md` (LAYOUT, 7.61% diff).

> Frame: dot list, selected row carries a chevron; ours: label + always-visible `Restore`
> pill + note, so a row is ~2× taller.

Reference frame: `docs/studio/reference/screens/S08-version-history.jpeg`.

## Frame anatomy

Read at 3× from the 1094×1245 capture (the History panel occupies x 8–316, y 0–1245).

| Part | Frame |
|---|---|
| Panel | 300 px wide, `#101012`, 12 px radius, no scrim behind it |
| Header | `History` (15 px semibold) left, `×` close right; hairline under the header |
| Subtitle | `Projects are saved automatically` — no trailing period; hairline under it |
| Date stepper | `<` · `10/31/2026` centered · `>`; chevrons faint (`#8b90a6`-ish), date `#f7f4ef` |
| Rail | One vertical hairline at x ≈ 24 inside the panel, running from the first row to past the last dot |
| Newest row | Full-width rounded highlight (`#1c1c1e`), white 8 px dot on the rail, `09:00 AM` semibold white, down-chevron at the right |
| Older rows | Gray 7 px dot on the rail, `09:42:06 AM` / `09:41:26 AM` in gray, **no** button and no chevron |
| Footer | Nothing — no explanatory note under the list |

Notable: the rows are **not** sorted by timestamp (`09:00 AM` sits above `09:42:06 AM`).
The list order is the server order — the first entry is the selected/current version, and the
highlight + chevron belong to it.

## What changed

`camxora.com/components/studio/StudioProjectMenu.tsx`

- `versionClock()` formats the captured timestamps in one locale: `hh:mm AM` for the newest
  row, `hh:mm:ss AM` for older rows (`en-US`, 12-hour). Falls back to `label`/`title` when a
  version has no parseable `created_at`.
- Each version is now `li.se-history-item` → `button.se-history-row`. The row itself is the
  restore action (`aria-label="Restore version from 09:00 AM"`), so clicking the row restores
  as the capture implies. A single focusable control per row keeps the list keyboard-accessible.
- Newest version (`versions[0]`, the endpoint's newest-first order) gets `.is-current`, a white
  dot, semibold timestamp and the captured down-chevron.
- Older rows render the `Restore` hint (`span.se-history-restore`, aria-hidden because the
  button name already says it) with `opacity: 0`; it is revealed on pointer hover or keyboard
  focus (`onPointerEnter`/`onFocus` → `.is-revealed`). It is no longer a permanent pill.
- The manual `label`, when present and different from the timestamp, rides along as muted meta
  on the same line instead of replacing the captured timestamp.
- Subtitle lost its trailing period (`Projects are saved automatically`).
- The permanent footer note (`Restoring replaces the arrangement and reloads the editor.`) is
  gone; the restore still calls `restoreStudioProjectVersion` and reloads the editor.

`camxora.com/app/globals.css`

- Rebuilt `.se-history-*`: rail via `ul::before`, dot geometry matched to the capture
  (rail x 24, dot 7/8 px, 35 px rows), one `#1c1c1e` highlight for the current row, chevron and
  reveal styles, a divider under the subtitle, and slightly roomier stepper padding.
- Removed the per-row `.se-pill` sizing rule.

## What stayed

- The panel itself: 300 px fixed side panel, header/close, automatic-save subtitle, date
  stepper and per-day grouping (`historyDay`), loading and empty states.
- Restore wiring unchanged: `restoreStudioProjectVersion(projectId, versionId)`, then
  `window.location.reload()`. While a restore is in flight the rows are `disabled`.
- Escape closes the panel, the menu items and all other dialogs are untouched.
- No Playwright run, no server, no port, no deployment.

## Tests

`camxora.com/tests/studio-project-menu.test.tsx` (20 tests in the file):

- `renders a dot-and-rail list with the newest version selected` — three dots for three
  versions, newest row `.is-current` + chevron + `hh:mm AM`, older rows `hh:mm:ss AM`, reveal
  span present only on older rows, no permanent `Restore` button, no footer note.
- `reveals Restore on hover/focus and restores the chosen version` — hover and focus add
  `.is-revealed`; clicking a row calls `restoreStudioProjectVersion("p1", "v2")`.
- `lists saved versions with their labels` / `renders version history as a dated side panel` —
  updated for the timestamp-first row name, dot anatomy and period-less subtitle.

Results on the branch:

- `npm run typecheck` — clean.
- `npx vitest run` — 52 files, 392 tests passed.
- `npm run check:ui` — compliant.
