# Pipeline recovery helper + auto rewrite on Suno reject

**Date:** 2026-07-20  
**Status:** implemented (API deploy + desktop)

## Summary

Suno `REJECTED` / content-policy failures now trigger an automatic lyric rewrite (LLM polish) + Suno resubmit on the server (up to 2 attempts). Music History gains a **Recover failed** button that scans loaded batches and recovers draft failures, content-policy rejects (rewrite→Suno), and other Suno failures (plain retry).

## Product impact

**Before**
- Sensitive-word auto-retry only sanitized/resubmitted once; `REJECTED` was not classified for auto-retry.
- Users manually polished each rejected song, then retried Suno.

**After**
- On Suno content-policy/reject callback: rewrite lyrics (if credits/routing allow) and resubmit automatically.
- History → **Recover failed** runs the same recovery across all loaded failed songs in one click.

## Technical impact

- `classify_suno_failure_type`: includes `REJECTED` + policy-ish error text.
- `BatchService._try_auto_retry_suno_after_failure`: up to 2 attempts; calls `_auto_rewrite_song_lyrics_for_suno_retry` (lyric quota via enforcement).
- Desktop: `collect_recovery_targets`, `PipelineRecoveryWorker`, History **Recover failed**.

## Files touched

- `platform_api/services/suno_status_messages.py`
- `platform_api/services/batch_service.py`
- `platform_api/tests/test_suno_sanitize_followups.py`
- `camxora_python/features/music/lib/pipeline_recovery.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/tests/test_pipeline_recovery.py`
- `CHANGELOG.md` / `platform_api/CHANGELOG.md`
- `docs/changelog/2026-07-20-pipeline-recovery-helper.md`

## Migration / deploy

1. Deploy `platform_api` to sandbox.
2. Restart desktop app for **Recover failed** button.

## Tests

- `pytest platform_api/tests/test_suno_sanitize_followups.py -q`
- `pytest camxora_python/tests/test_pipeline_recovery.py -q`

## Follow-ups

- Image/export failure recovery in the same helper.
- Settings toggle to disable background recovery / auto rewrite (credits).
- Surface helper activity on the Log page with song-level detail.

## Background watcher

Shell `PipelineRecoveryCoordinator` polls music history (~45s idle / ~20s when active), recovers up to 3 failed songs per cycle with a 15-minute per-song cooldown and max 2 attempts/song per app session.
