# Workflow Timeline (Design)

## Goals
- Provide a single “pipeline timeline” overview per selected Batch × Channel (OK/ALT).
- Make the current blocking step instantly obvious.
- Keep the screen scannable and professional: icon-first, minimal text, meaningful numbers.
- Ensure live progress is reflected (especially YouTube upload %).

## Page Layout
### Header
- Title: Workflow
- Controls (right side):
  - From / To date filters (same pattern as Dashboard/Progress)
  - “Active only” toggle
  - Refresh button

### Body
- Two-column layout:
  - Left: “Runs” list (Batch + Channel OK/ALT + Stage + Status)
  - Right: “Timeline” panel (large step circles + connectors + per-step details)

## Timeline Visual Language
- Each step renders as a circular node:
  - Center: lucide icon (e.g., music/image/video/youtube)
  - Under icon (inside the circle): percentage text (e.g., 62%)
  - Under the circle: step title + 1–2 lines of compact metrics
- Connector line between steps:
  - Active steps: brighter line
  - Not started: muted line

## Steps (v1)
1) Music Generation
2) Background + Thumbnail (Image)
3) Convert (MP4)
4) Merge (Final MP4)
5) YouTube Upload

## Status + Colors
- Not started / inactive: light gray ring
- In progress: primary blue ring
- Done: success green ring
- Failed: danger red ring
- Cancelled: muted gray + “Cancelled”

## Details Under Each Step (Examples)
- Music: `10/20 songs` and `Waiting / Generating / Done`
- Image: `BG READY · TH RUNNING` (or `100%` when both READY)
- Convert: `MP4 18/20` (primary metric) and optional `MP3 20/20`
- Merge: `Waiting to merge` or `Merged: myfile.mp4`
- YouTube: `Queued / Uploading 42% / Done` and optional URL indicator

## UX Behaviors
- When selection changes on the left list:
  - Timeline updates immediately
  - If the selected item disappears (date filter changes), auto-select the first visible item.
- Auto-refresh:
  - Refresh every ~2 seconds while the Workflow page is visible.
  - Avoid UI blocking: data fetch in background thread, apply model in UI thread.

## Accessibility
- Icons have tooltips matching step titles.
- Percent text remains readable at small sizes.
- All key info is duplicated in text (color is not the only indicator).
