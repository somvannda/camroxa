# Worker Concurrency (Python App) — design

## Product Goals
- Make long runs complete faster by safely increasing parallelism where it matters.
- Keep UX predictable:
  - clear “busy” indicators
  - no duplicate jobs
  - no random freezes from excessive concurrency

## UX Placement
Centralized under **Settings → Performance** (Boss preference).

### Performance Tab Layout
**Section: Workers**
- Music Workers (1–5)
  - Description: “How many batches can generate in parallel.”
- Image Workers (1–8)
  - Description: “How many image jobs can run in parallel.”
- Export Workers (1–10)
  - Description: “How many video exports can run in parallel (GPU + ffmpeg).”
- Merge Workers (1–2)
  - Description: “How many merges can run in parallel (disk + CPU).”
- YouTube Upload Workers (1–5)
  - Description: “How many uploads can run in parallel (network + disk).”

### User Feedback States
- When the user increases workers, show a small hint row:
  - “Higher workers = faster but higher load.”
  - If Export Workers > 3: show warning text (“May overload GPU/VRAM on some systems.”)

### Consistency / Sync
- Video page already has “Workers” for export; it must stay in sync with the same setting.

## Guardrails (Balanced defaults)
- Music Workers: 1
- Image Workers: 4
- Export Workers: 2
- Merge Workers: 1
- YouTube Upload Workers: 1

## Non-goals (for this iteration)
- Automatic dynamic tuning based on GPU/CPU utilization.
- Distributed workers across multiple machines.
