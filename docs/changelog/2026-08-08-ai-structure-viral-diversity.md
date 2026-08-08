# AI Structure — genre-aware viral layout diversity

**Date:** 2026-08-08  
**Surfaces:** `platform_api`

## Summary

AI Structure (`structure_mode=ai_free`) was converging on the same commercial-pop section sequence on production. The lyric path now steers variety with genre-aware viral layout seeds, prompt guardrails, and a batch avoid-list — still without dumping production description text into lyrics.

## Product impact

- AI Structure songs should vary section layouts more within a batch.
- Layout bias follows description **genres** (Pop / R&B / Hip Hop vs EDM/electronic).
- Production description content remains Suno style-only; lyrics stay mood/title-led.

## Technical impact

- New helper module: `platform_api/services/ai_structure_diversity.py`
- Soft preferred layout + avoid fingerprints on `DraftRequest`
- Batch draft orchestration / fan-out retry loads sibling structure fingerprints
- System/user prompts discourage the overused Verse→Pre-Chorus→…→Final Chorus template

## Files touched

- `platform_api/services/ai_structure_diversity.py` (new)
- `platform_api/ports/generation_port.py`
- `platform_api/services/generation_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/routers/generation.py`
- `platform_api/tests/test_ai_structure_diversity.py` (new)
- `platform_api/CHANGELOG.md`

## Migration / deploy

- No DB migration.
- Deploy/restart `platform_api` (sandbox first).

## Tests

- `pytest platform_api/tests/test_ai_structure_diversity.py`
- Existing `TestAiStructureLyrics` cases

## Follow-ups

- Optional: persist chosen seed on song metadata for admin analytics.
- Optional: tune family pools from production fingerprint histograms.

## Update — expanded seed pool

Seed catalog grown from 8 → 18 viral families (pop/urban/default + electronic-only drop/build variants). Still soft guides only; no DB persistence.

## Update — more EDM / electronic / dance seeds

Added 10 more electronic-only families (festival/hands-up/trance/club/eurodance styles) and broadened electronic genre token matching for Dance / Club / Hard Dance / etc. Dance Pop remains pop-leaning.
