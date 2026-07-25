# Pipeline helper: smarter Suno recovery

**Date:** 2026-07-25  
**Status:** implemented (desktop restart)

## Summary

The background pipeline helper was classifying almost every `suno_failed` song as a plain Suno retry (`rewrite 0, Suno N`), including corrupt/oversized lyrics with no provider error. That raced manual rewrite and burned retries on poison payloads. Helper now classifies by lyric health + failure type, skips corrupt lyrics, rewrites oversized/content-policy cases, and avoids songs busy with manual rewrite.

## Product impact

**Before**
- Helper repeatedly queued Suno with the same bad lyrics.
- Status looked like “recovered” even when only blind Suno retries ran.
- Manual rewrite and helper could hit the same song together.

**After**
- Corrupt lyrics → **skip** (needs fresh draft).
- Oversized / content-policy → **rewrite→Suno**.
- Transient errors with healthy lyrics → **Suno retry**.
- Same lyric hash after a Suno retry → escalate to rewrite, then skip.
- Manual rewrite marks the song busy so helper backs off.
- Status shows `skipped` and uses warning tone when nothing actionable ran.

## Technical impact

- `assess_lyrics_health` / `classify_suno_recovery_kind` in `pipeline_recovery.py`.
- Coordinator busy lock + same-hash escalation.
- `PipelineRecoveryScanResult.skipped`; workers honor `kind=skip`.

## Files touched

- `camxora_python/features/music/lib/pipeline_recovery.py`
- `camxora_python/shared/services/pipeline_recovery_coordinator.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_pipeline_recovery.py`
- `camxora_python/tests/test_pipeline_recovery_coordinator.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-pipeline-helper-smart-recovery.md`

## Migration / deploy

Restart desktop app. No API deploy required for this helper change.

## Tests

- `pytest camxora_python/tests/test_pipeline_recovery.py camxora_python/tests/test_pipeline_recovery_coordinator.py -q`

## Follow-ups

- Server-side reject of corrupt lyrics on Suno submit.
- Deploy mood-aligned rewrite API so rewrite path stops feeding description.
- Optional: auto `retry draft` when helper skips corrupt lyrics.
