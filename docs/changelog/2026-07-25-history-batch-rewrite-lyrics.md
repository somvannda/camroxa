# History batch Rewrite lyrics context menu

**Date:** 2026-07-25  
**Status:** implemented (desktop restart)

## Summary

History right-click only offered Retry batch (blind Suno/draft retry). Added **Rewrite lyrics (N songs)** so failed songs in a batch can be polish→Suno in one action, skipping corrupt/empty lyrics.

## Product impact

**Before**
- Rewrite was one song at a time via the song card.
- Retry batch resubmitted Suno without rewriting.

**After**
- Right-click a History row/batch → **Rewrite lyrics (N songs)** for rewrite-eligible failures.
- When multiple songs qualify, **Rewrite this song** rewrites only the clicked row.
- Corrupt lyrics are not included in N.

## Technical impact

- `collect_batch_rewrite_targets` forces `suno_rewrite` for usable failed songs.
- `HistoryCard.rewrite_batch_requested` → `MusicView._rewrite_history_batch` via `PipelineRecoveryWorker`.

## Files touched

- `camxora_python/features/music/lib/pipeline_recovery.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_pipeline_recovery.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-history-batch-rewrite-lyrics.md`

## Migration / deploy

Restart desktop app.

## Tests

- `pytest camxora_python/tests/test_pipeline_recovery.py -q`

## Follow-ups

- Cap concurrent batch rewrites / show per-song progress dialog for large N.
