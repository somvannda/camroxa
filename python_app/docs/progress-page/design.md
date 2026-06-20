# Progress Page (Design)

## Goals
- Provide a single, readable “end-to-end pipeline” view across Music → Image → Converter → Merge.
- Make it obvious what step is currently blocking and which channel (OK/ALT) is affected.
- Support quick scanning with consistent layout and minimal noise.

## Information Architecture
- Page title: Progress
- Controls:
  - Refresh button
  - Batch limit (e.g., last 10/25/50)
  - From / To date filters (optional, uses run date)
  - Optional “Active only” toggle (shows batches still in progress)
- Content:
  - Summary strip (latest status + last refresh timestamp)
  - Progress table (primary reporting surface)

## Table Layout (Per Batch × Channel)
Columns:
1) Batch
   - `batchId` (shortened)
   - Run date
2) Channel
   - Profile name
   - Role pill: OK / ALT
3) Music
   - `songs_saved / expected`
4) Image
   - BG: PENDING/RUNNING/READY/FAILED
   - TH: PENDING/RUNNING/READY/FAILED
5) Converter
   - MP3: `count / expected`
   - MP4: `count / expected`
6) Merge
   - Status: waiting / ready / missing
   - Output filename when present
7) Stage
   - Derived “current stage” label:
     - Music, Image, Converter, Merge, Done, Error
8) Notes
   - Compact error preview (e.g., last image job error, export error)

## Behavior Rules
- When expected count is known (active batch):
  - Converter and Merge must report against that number.
- When expected is unknown (older batch):
  - Use persisted song count as expected for display (informational mode).
- Progress should never claim “Done” unless:
  - MP4 count equals expected AND a MERGED file exists.

## Accessibility / Readability
- Use consistent labels and avoid long paragraphs inside cells.
- Use short status chips (READY / WAITING / FAILED).
- Keep the view stable across refreshes (no jumping columns/width).
