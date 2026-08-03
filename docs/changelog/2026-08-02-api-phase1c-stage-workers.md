# 2026-08-02 — API phase 1c: priority fix + stage multi-workers

## Summary

- Raise `execute_batch` priority above draft/Suno so new batches fan out under load (no starvation).
- Run **stage-sharded** worker pools via systemd templates + `CAMXORA_WORKER_JOB_TYPES`:
  - **draft** ×4 — `execute_batch`, `draft`, `retry_song_draft` (album / title / lyrics via SLAI key pool)
  - **suno** ×2 — `suno_submit`, `retry_song_suno` (Suno key pool; submit only — MP3 download remains callback/desktop)
  - **images** ×2 — `run_image_jobs`, `run_youtube_uploads` (SLAI/fal image key pools; image runner still parallelizes up to 4–8 jobs inside one drain)
- Claim filter is applied in SQL (`job_type = ANY(...)`) with `FOR UPDATE SKIP LOCKED`, so stages never steal each other’s jobs.
- Key pools already share across processes (Postgres + Redis RR / cooldown). Concurrent workers pick active keys; on 429 the key is rate-limited and failover tries another key (up to 3 attempts).

## Priorities (DESC)

| Job | Priority |
|-----|----------|
| execute_batch | 25 |
| retries | 20 |
| suno_submit | 18 |
| draft (by song index) | 20→5 |
| run_image_jobs | 12 |
| run_youtube_uploads | 6 |

## Ops

Units: `camxora-worker-draft@{1..4}`, `camxora-worker-suno@{1..2}`, `camxora-worker-images@{1..2}` (8 workers; sized to current key pools).
Legacy `camxora-worker.service` disabled.

## Key pool sizing

Current inventory (matched worker counts): suno×2, slai×4, fal×1, openai×2, deepseek×2.
When keys grow, scale workers toward draft×6–8 / suno×3–4 / images×3–4 and raise key counts accordingly.
