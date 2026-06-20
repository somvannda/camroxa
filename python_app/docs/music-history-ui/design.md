# Music History UI Redesign — Design

## Product Goals
- Make the History list scannable at a glance.
- Reduce text clutter in Suno status while still surfacing full failure details when needed.
- Make it easy to open the correct output folder per channel (OK vs ALT) from the list.
- Make it obvious which “date” is being viewed:
  - Run Date = the requested batch date the generation was for
  - Generated Date = the timestamp when the record was created

## User Flow
1) User opens Music page.
2) User uses History From/To and Last batch filters.
3) User scans Suno status by dot color.
4) User selects a song row:
   - Song is loaded into the editor.
   - Footer shows the full Suno status/error for the selected song.
5) User clicks open-folder icon in:
   - OK Channel cell → opens OK output directory for that song (if known)
   - ALT Channel cell → opens ALT output directory for that song (if known)
6) User clicks retry icon in Suno column to resubmit/retry that song.

## Table Layout

### Columns (proposed)
- No
- Run Date
- Album
- Title
- Desc
- Struct
- OK Channel
- ALT Channel
- Suno
- Generated

### Cell Behaviors
- OK Channel / ALT Channel:
  - Left: channel name (profile name preferred)
  - Right: open-folder icon button
  - Button disabled if directory is not known yet
- Suno:
  - Colored dot only (no text)
  - Retry icon button next to dot

## States
- Suno Dot Colors:
  - Green: READY (both OK + ALT audio URLs exist)
  - Yellow: PENDING / SUBMITTED / SUCCESS (not fully ready)
  - Red: ERR / FAILED (failure status)
- Folder Buttons:
  - Enabled when output directory exists on disk
  - Disabled when directory is empty/unknown or missing on disk

## Accessibility & UX Notes
- Dot uses tooltip with full status text.
- Footer also shows the selected row Suno status text; if too long, footer label tooltip should preserve full text.

