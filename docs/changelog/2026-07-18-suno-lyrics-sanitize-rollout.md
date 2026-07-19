# Suno lyrics sanitization rollout

**Date:** 2026-07-18  
**Status:** implemented (local)

## Summary

Unified Suno submit sanitization across batch auto-submit, retry, and direct API paths. Lyrics, title, and style are sanitized using the static blocklist plus terms learned from the latest failed Suno task. Desktop adds an Auto-fix control, replacement toasts, and title scanning. Failure metrics are logged with type classification.

## Product impact

- Before: only lyrics were partially sanitized on first submit; retries used learned terms but logic was duplicated.
- After: all Suno submits sanitize lyrics/title/style consistently, persist corrected drafts before submit, and surface replacements in desktop toasts and the lyrics-suno-check API.

## Technical impact

- API: `_sanitize_suno_payload` in batch service; `sanitize_text_for_suno_with_changes`; `classify_suno_failure_type`; `log_suno_failure_metric`; extended `LyricsSunoCheckResponse`.
- Desktop: Auto-fix button, title risk scan, replacement toasts on auto-fix and history load.
- Metrics: structured `suno_failure_metric` log events on submit and callback failures.

## Files touched

- `platform_api/services/suno_lyrics_sanitize.py`
- `platform_api/services/suno_status_messages.py`
- `platform_api/services/draft_progress_log.py`
- `platform_api/services/batch_service.py`
- `platform_api/services/generation_service.py`
- `platform_api/routers/generation.py`
- `platform_api/tests/test_suno_lyrics_sanitize.py`
- `platform_api/tests/test_suno_status_messages.py`
- `platform_api/tests/test_batch_service.py`
- `camxora_python/shared/lib/suno_lyrics_sanitize.py`
- `camxora_python/features/music/widgets/song_editor_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_suno_lyrics_sanitize.py`

## Migration / deploy

- No DB migrations. Deploy API + desktop together to keep sanitize logic aligned.

## Tests

- `platform_api`: sanitize replacements, failure classification, batch payload helper
- `camxora_python`: desktop mirror sanitize helpers

## Follow-ups

- Persist replacement metadata on songs for exact server-side change history without inference heuristics.
