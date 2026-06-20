# Dashboard (Design)

## Goal
Provide a single “at-a-glance” page that answers:
- What is happening right now in the pipeline (Music → Image → Converter → Merge → YouTube)?
- What is failing and where?
- How many outputs were produced (today / last 7 days / this month)?
- How much cost was spent (credits/money) per provider and per day.

## Layout (One Page)

### A) Top Summary Bar
Row of compact KPI cards:
- Active Batches (in progress)
- Failed Items (today)
- Songs Generated (today)
- Images Generated (today)
- MP4 Converted (today)
- Merged Videos (today)
- YouTube Uploaded (today)
- Credits Remaining (Suno)

## Navigation
- Dashboard is the Home landing page (left-nav item `Dashboard`, internal page key `home`).

### B) Cost + Usage Panel (Left)
Two stacked cards:
1) Cost Today / Cost 7D
   - Total
   - By provider: Suno / SLAI / DeepSeek / Other
2) Usage Breakdown
   - Suno: credits used, credits remaining
   - SLAI: images generated, retries
   - LLM: calls (DeepSeek/SLAI text), failures

### C) Pipeline Health Panel (Right)
Two stacked cards:
1) Current Pipeline Stage
   - Progress bar per stage (Music/Image/Converter/Merge/Upload)
   - “Top blocker” list (e.g., invalid key, missing ffmpeg, missing template mapping)
2) Recent Failures (table)
   - Timestamp, Batch, Channel, Stage, Error summary
   - Right-click: retry stage / open folder

### D) Recent Activity (Bottom Full Width)
Table or timeline-like list:
- Last 50 events (generated song, queued image, image ready, export done, merge done, upload done)
- Filters: date range, profile, stage, status

## UX Rules
- Keep numbers stable and readable; avoid overly dense charts.
- Clicking a KPI card jumps to the relevant filtered view (e.g., Failed Items opens Progress page filtered).
- Costs must be transparent: show how values are computed (hover tooltip or “Info” dialog).
