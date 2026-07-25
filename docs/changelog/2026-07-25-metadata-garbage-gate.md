# Title / album metadata garbage rejection

**Date:** 2026-07-25  
**Status:** implemented (sandbox pending deploy)  
**Related:** Beattok song `#3` corrupt title (`Slow Cruisin'… MUTus必 провер…`) blocked Suno submit with 0 tasks.

## Summary

LLM draft titles/albums could pass the old length/word checks while containing mixed-script junk and glued keyword salad. Validation now requires Latin-script readable names, rejects script noise and glued tokens, and Suno submit refuses invalid titles so retries stop burning cycles on garbage.

## Product impact

**Before**
- Corrupt titles could be stored and retried forever (`retry-suno` 202 with no Suno task).
- Progress stayed Error on one bad track.

**After**
- Draft generation retries the title/album slot when output is garbage.
- Suno submit returns a clear validation error instead of a silent pre-task failure.
- Forced title/album values are validated the same way.

## Technical impact

- `platform_api/ai/purposes/metadata_text.py`: script-noise strip + glued-token / non-Latin checks.
- `GenerationService.submit_suno` + draft forced title/album paths call `is_valid_metadata_name`.

## Files touched

- `platform_api/ai/purposes/metadata_text.py`
- `platform_api/services/generation_service.py`
- `platform_api/tests/test_metadata_text.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-07-25-metadata-garbage-gate.md`

## Migration / deploy

Deploy `platform_api` / restart `camxora-api`. No DB migration.

For the existing Neon Coastal failed song: **retry-draft** (regenerate title) then Suno — do not keep `retry-suno` on the corrupt title.

## Tests

- `pytest platform_api/tests/test_metadata_text.py -q` (pass)

## Follow-ups

- Optional one-off admin/script to clear known corrupt titles in sandbox.
- Consider same gate on content-pool album seeds at ingest time.
