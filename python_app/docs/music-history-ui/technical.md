# Music History UI Redesign — Technical

## Existing Implementation (Code-Based)
- Table definition and column headers:
  - `python_app/views/music_view.py` builds `self.music_history_table` with 8 columns.
- Row rendering:
  - `python_app/main.py::_refresh_music_history_table()` populates rows and embeds a custom widget inside the `Suno` column (status label + retry + open-folder).
- Footer:
  - `python_app/views/core_view.py::_build_global_footer()` creates `footer_left_label`, `footer_center_label`, `footer_right_label`.
  - `python_app/main.py::_set_music_suno_status()` and `_refresh_footer_status()` drive left footer text.
- DB sourcing:
  - `python_app/database/music_db.py::list_songs_for_history()` returns `runDate`, `createdAt`, `profileOkId`, `profileAltId`.
  - It does not currently return `profileOkName/profileAltName` (needs join to `profiles`).
- Suno latest task:
  - `python_app/database/music_db.py::list_latest_suno_tasks_by_song_uids()` returns latest status + output dirs + audio URLs.

## Planned Changes

### 1) DB Query Enrichment (Profile Names)
- Update `list_songs_for_history()` to LEFT JOIN:
  - `profiles p_ok on p_ok.uid = songs.profile_ok_id`
  - `profiles p_alt on p_alt.uid = songs.profile_alt_id`
- Return new fields:
  - `profileOkName`, `profileAltName`

### 2) History Table Column Changes
- Update `python_app/views/music_view.py`:
  - column count from `8` to `10`
  - header labels to new layout:
    - `Run Date`, `OK Channel`, `ALT Channel`, `Generated`
- Update `python_app/main.py::_refresh_music_history_table()`:
  - Build values matching the new columns.
  - Render channel cells as a composite widget: label + open-folder button.
  - Render Suno cell as dot widget + retry button.

### 3) Footer Suno Status on Selection
- Update `python_app/main.py::_on_music_history_row_selected()`:
  - Determine selected song id.
  - Find latest Suno row for that song from a cached mapping created during table refresh.
  - Call `_set_music_suno_status(<full status string>)`
  - Also set tooltip on `footer_left_label` to preserve full text even when clipped.

## Data Flow (After Change)
1) `_refresh_music_history_table()`
   - reads songs from DB via `list_songs_for_history()`
   - reads latest suno tasks via `list_latest_suno_tasks_by_song_uids()`
   - renders table cells (dot + buttons)
   - caches `song_uid -> latest suno row` mapping on `self`
2) User selects a row:
   - `_on_music_history_row_selected()` updates footer Suno message
   - controller loads song into editor (existing behavior)

## Risks / Edge Cases
- DB rows may have `profile_ok_id/profile_alt_id` but no matching `profiles` rows (deleted profile):
  - UI falls back to showing the id string.
- Output directory may be present in DB but missing on disk:
  - open button should disable or show a warning.
- Non-DB fallback path:
  - still supported, but may show fewer channel name details.

## Files to Modify
- `python_app/views/music_view.py`
- `python_app/main.py`
- `python_app/database/music_db.py`
- `python_app/DEVELOPMENT_LOG.md`

