# Music History UI Redesign — Tasks

## Goal
- Improve Music → History table readability and usability:
  - Suno status uses a dot indicator (no words).
  - Full Suno error/status displays in footer when selecting a row.
  - Split Channel into OK Channel and ALT Channel columns, each with an open-folder button.
  - Show both Run Date (requested batch date) and Generated Date (record created timestamp).

## Scope
- Python app only (`python_app/`).
- Affects History table UI rendering and related DB query enrichment (profile names).

## Tasks

### 1) Inspect & Plan
- [completed] Inspect current table definition in `python_app/views/music_view.py`.
- [completed] Inspect current row rendering in `python_app/main.py::_refresh_music_history_table`.
- [completed] Inspect footer status plumbing in `python_app/main.py::_set_music_suno_status` and `_refresh_footer_status`.
- [pending] Confirm desired meaning of “separate by batch date then generated date” (columns vs visual group headers).

### 2) Data Layer Updates
- [pending] Enrich `list_songs_for_history()` to return:
  - `profileOkName`, `profileAltName` (join `profiles` table).
  - Keep existing `runDate` and `createdAt`.

### 3) UI Updates (History Table)
- [pending] Update column layout:
  - Add `Run Date`
  - Split `Channel` into `OK Channel` and `ALT Channel`
  - Rename `Created` → `Generated`
- [pending] Replace Suno text label with a colored dot widget:
  - Green = READY
  - Yellow = PENDING / SUBMITTED / SUCCESS (no audio yet)
  - Red = ERR / FAILED
- [pending] Reduce Retry button size so it remains fully visible.
- [pending] Move “Open folder” action out of Suno column:
  - Add open-folder icon inside OK Channel and ALT Channel cells.

### 4) Footer Error Display
- [pending] On History row selection:
  - Show full latest Suno task status string in footer (and set tooltip to preserve the full string if clipped).

### 5) Verification
- [pending] Manual smoke checks:
  - History loads with DB enabled
  - Dot colors match expected statuses
  - Retry button works
  - OK/ALT open-folder buttons open correct directories (when present)
  - From/To filtering still works and uses Run Date when available

### 6) Documentation
- [pending] Append an entry to `python_app/DEVELOPMENT_LOG.md` with:
  - What/Why
  - Affected files
  - Known limitations

