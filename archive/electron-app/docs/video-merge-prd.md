# Video Merge (Multi-Folder) — Requirements (Draft)

## Goal
Add a new feature in the main screen (in the Background panel area, using the unused bottom space under image generation) that lets you:
1) Select multiple directories (folders)
2) Click **Merge Videos**
3) Produce merged MP4 outputs using FFmpeg with configurable video export settings

## Non-Goals (v1)
- Manual drag-and-drop ordering of clips (requested “manual later”)
- Editing/previewing clips in-app
- Transitions/effects between clips
- Audio mixing across clips beyond FFmpeg default behavior

## Key Decisions (confirmed)
- Output: **1 merged MP4 per selected directory**
- Input scope: **top-level files only** (no recursion)
- Save location: create a `merged` subfolder inside each selected directory
- Ordering: **manual later**; for v1 we will use a deterministic default ordering (see Ordering section)

## User Stories
1) As a user, I can select many folders and see the chosen list persist in the app.
2) As a user, I can configure video export settings (resolution, FPS, etc.).
3) As a user, I can merge each folder into a single MP4 and see progress per folder.
4) As a user, I can re-run merges without re-selecting folders.

## Placement (UI)
- Location: the **bottom area of the Background panel** (below the existing background image generation controls), using the empty vertical space.
- The Background panel should keep the same overall size; the new area can scroll internally if needed.

## Data Model / Persistence
Persist in app settings (and DB if Postgres mode is enabled, like other settings):
- `videoMergeDirectories: string[]`
- `videoExport`: export settings object (see below)

## Select Directories
### Behavior
- Button: **Select directories**
- Multi-select folders via OS folder picker (repeatable to add more)
- The selected list is shown in the main app immediately

### Directory List UI
For each directory:
- Shows full path (truncated with tooltip on hover)
- Remove button (removes from list)
Optional:
- “Clear all” action

## Merge Videos
### Behavior
- Button: **Merge Videos**
- Starts immediately (no additional modal required)
- Merges folders sequentially (v1) so progress is simple and FFmpeg usage is predictable
- Produces one output file per folder:
  - Output folder: `<selectedDir>\merged\`
  - Output name: `merged_<YYYY-MM-DD_HH-mm-ss>.mp4` (or a simple consistent name like `merged.mp4` with overwrite confirmation)

### Ordering (v1)
Because “manual later” is requested, v1 will default to:
- Sort by filename A→Z (natural sort if filenames contain numbers)

### Input File Types (v1)
- Include common video extensions: `.mp4`, `.mov`, `.mkv`, `.webm`
- Ignore non-video files
- If a folder has 0 valid videos, mark it failed with a clear message

### FFmpeg Requirements
- Uses the existing configured `ffmpegPath` setting.
- If `ffmpegPath` is not configured or invalid, show a clear error and do not start.

### Handling Different Resolutions/FPS/Codecs
To be robust, v1 should **re-encode** the output to the chosen export settings (slower, but works with mixed inputs).
Optional (nice-to-have):
- “Fast concat (no re-encode)” mode only when inputs are compatible (same codec/resolution/FPS).

## Video Export Settings (v1)
These appear in the new panel as “Video export settings”.

### Required Settings
- Resolution: e.g. `1920×1080`, `1080×1920`, `1280×720`
- FPS: e.g. `24`, `30`, `60`

### Recommended Settings (optional but useful)
- Codec: `H.264 (libx264)` (v1)
- Preset: `fast | medium | slow`
- Quality: CRF (e.g. 18–28)
- Audio: `AAC`, bitrate (e.g. 192k)

Defaults should be safe:
- H.264, preset=fast, CRF=20, AAC 192k, FPS=30

## Progress / Status
Show a compact progress bar and per-directory status list:
- Overall: `Merged X / N directories`
- Per directory row:
  - status: pending / running / done / failed
  - message: “Found 12 videos”, “Encoding…”, “Saved to …”, or error details

## Errors / Edge Cases
- Missing ffmpeg path
- Folder not accessible
- No videos found
- FFmpeg failure on a specific folder (continue to next folder, but show failure)
- Output file exists (either overwrite with confirmation or auto timestamp filename)

## Acceptance Criteria
- Selected directories persist after restart.
- Clicking Merge Videos produces one MP4 per folder in `<folder>\merged\`.
- Export settings affect the output resolution/FPS.
- UI shows progress and does not freeze the app.

## Open Questions (to confirm before implementation)
1) Output filename rule: always overwrite `merged.mp4`, or timestamped per run?
2) Should we “stop on first error” or “continue merging remaining folders” (recommended continue)?
3) Do you want an optional “include subfolders” toggle later?

