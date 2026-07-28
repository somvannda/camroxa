# Progress filters + Secondary album uniqueness

**Date:** 2026-07-28  
**Status:** implemented (desktop installer rebuild + API deploy pending)

## Summary

Progress page Limit / Active only filters did not match the selected row count or effective stage after OK/ALT expansion and desktop overlays. The Update column kept moving after Done because batch sync heartbeats were included in `updated_at`. Separately, Album 2 (Secondary / ALT) often matched Album 1 because pool text was used without AI polish, failures cleared `alt_album`, and several display/run-dir paths fell back to the Primary album.

## Product impact

- Progress Limit: 10 / 25 / 50 / 100 (default **10**); table shows that many rows.
- Active only: hides Done rows after local overlays (Stage filter behavior parity).
- Update column: once a row is Done, time freezes at YouTube completion (or last terminal activity).
- New batches with a Secondary channel get a distinct Album 2 (pool seed + AI polish, with deterministic suffix fallback). Existing duplicate rows are not rewritten automatically — use rewrite-album or regenerate.

## Technical impact

- `GET /progress`: over-fetches batches (`limit * 2`, cap 100), expands OK/ALT, applies `active_only`, then **slices to `limit` rows**.
- Progress no longer copies song/Primary album onto empty `alt_album`.
- Terminal stages exclude `batch.updated_at` from the Update timestamp (Done prefers `youtube.updated_at`).
- `_resolve_alt_channel_album`: content-pool claim is a **seed**; AI polish with retries (same spirit as rewrite-album); never persist empty ALT when Secondary profile exists.
- Run-dir / channel-label / image-workspace fallbacks no longer reuse Primary album for Secondary.

## Files touched

### Desktop (`camxora_python` / hotfix → v1.0.2)

- `features/progress/views/progress_view.py`
- `features/progress/widgets/operational_rows_card.py`
- `shared/lib/image_workspace.py`
- `pyproject.toml` (1.0.2)
- root `CHANGELOG.md`

### Platform API

- `platform_api/routers/progress.py`
- `platform_api/services/batch_service.py`
- `platform_api/tests/test_batch_service.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

- No DB migration.
- Deploy `platform_api` to **local**, then **sandbox**, then **production** (user requested all three).
- Rebuild desktop installer `CamxoraSetup-1.0.2.exe` from hotfix branch; user uploads manually (do not publish Software Updates unless asked).

## Tests

- Updated `test_orchestrate_drafts_persists_distinct_channel_albums` to expect polished Secondary album.
- Run: `pytest platform_api/tests/test_batch_service.py -k album` (and Progress-related desktop tests if present).

## Follow-ups

- Optional one-shot admin/script to backfill duplicate `alt_album` on historical batches.
- Consider billing clarity if Secondary polish always calls the album LLM slot after a pool claim.
