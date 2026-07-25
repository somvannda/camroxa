# Lyric rewrite quality gate (stop garbage loops)

**Date:** 2026-07-25  
**Status:** implemented (sandbox API deploy)

## Summary

Manual rewrite was feeding already-corrupted, multi-thousand-character word-salad lyrics into the LLM, which produced the same (or worse) garbage every time. Polish now trims to coherent leading sections, asks for short singable lines, and rejects corrupted/oversized outputs.

## Product impact

**Before**
- Rewrite of poisoned lyrics returned more word salad / mixed-script junk.
- UI looked like “rewrite worked” while History still showed unusable text.

**After**
- Rewrite uses only the clean head of the lyrics (cuts at first word-salad/corrupt line).
- Bad model output is rejected (userable) instead of saved.
- Fully poisoned songs error with “regenerate a fresh draft” instead of looping.

## Technical impact

- `prepare_lyrics_for_rewrite`, `describe_lyric_rewrite_quality_failure`
- Stricter `_is_corrupt_lyric_line` (run-on lines, scripts, known garbage tokens)
- `polish_lyrics_text` max_tokens 2048; quality gate after sanitize

## Files touched

- `platform_api/services/generation_service.py`
- `platform_api/tests/test_generation_service.py`
- `platform_api/tests/test_suno_sanitize_followups.py`
- `platform_api/CHANGELOG.md`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-lyric-rewrite-quality-gate.md`

## Migration / deploy

Deploy `platform_api` to sandbox and restart API.

## Tests

- `pytest platform_api/tests/test_generation_service.py::TestTwoStepLyricPrompts platform_api/tests/test_suno_sanitize_followups.py::test_polish_lyrics_auto_fixes_remaining_block_terms platform_api/tests/test_generation_router.py::TestPolishLyrics -q`

## Follow-ups

- For songs already poisoned in DB: user should delete failed batch / retry draft rather than rewrite.
- Optional admin tool to bulk-clear corrupt lyrics.
