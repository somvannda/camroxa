# Web music Version 2 recovery for generations stranded by the first-clip bug

## Summary

The `parse_suno_generate_poll` fix (`docs/changelog/2026-10-08-version2-first-success-still-pending.md`)
stops **new** generations from being marked `SUCCESS` with `audio_url_alt` empty. It does
**not** touch generations already stranded by the old behaviour: those rows are already
`status = 'success'`, so `web_music_service._refresh_pending_from_suno` never polls them
again, and Version 2 stays on "Waiting"/"Loading…" forever.

This change adds an ops recovery that repairs those existing rows.

## Product impact

- Existing `success` generations whose Version 2 never became playable are refreshed from
  upstream `record-info`, their `audio_url_alt` is persisted, and the alt clip is ingested
  into B2 — which is what makes Version 2 playable.
- Production measurement before the run: **40** `success` tasks with alt not playable
  (38 with `audio_url_alt` empty), of which **38 were recoverable** from upstream and
  **2 were unrecoverable** (legacy provider task ids that now return 404).

## Technical impact

- `scripts/deploy/_web_music_alt_stranded_report_remote.py` +
  `run_web_music_alt_stranded_report_production.py` — read-only count/sample report.
- `scripts/deploy/_web_music_alt_recover_remote.py` +
  `run_web_music_alt_recover_production.py` — refreshes each stranded task via
  `refresh_suno_task_download_urls`, persists the refreshed URLs with
  `StreamingUploadService._persist_refreshed_audio_urls`, then runs
  `_run_web_music_b2_backfill(task_id, "alt")`. Default is a dry-run probe; `--apply`
  mutates. Idempotent and safe to re-run.
- The existing stuck-B2 backfill (`_web_music_b2_backfill_stuck_remote.py`) deliberately
  required `audio_url_alt <> ''`, so it skipped exactly these rows; this recovery does not.

## Files touched

- `scripts/deploy/_web_music_alt_stranded_report_remote.py` (new)
- `scripts/deploy/run_web_music_alt_stranded_report_production.py` (new)
- `scripts/deploy/_web_music_alt_recover_remote.py` (new)
- `scripts/deploy/run_web_music_alt_recover_production.py` (new)
- `docs/changelog/2026-10-08-web-music-alt-recovery.md` (this file)

## Migration / deploy

- No migration, no service restart. Ops-only scripts run against production over SSH.

## Follow-ups

- `pending`/`running` web-music tasks now self-heal when opened (the deployed poll fix
  waits for terminal `SUCCESS`); a forced reconcile pass can be added if needed.
- `failed` web-music tasks are genuine failures (refunded) and are intentionally left alone.
