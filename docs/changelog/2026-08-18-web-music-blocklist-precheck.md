# Web music: blocklist before Suno, no false 422 charges

**Date:** 2026-08-18  
**Surfaces:** platform_api  
**Sandbox:** yes (file-scoped API sync after tests)

## Summary

Free Music Create was charging 10 credits, then 422ing on the desktop Latin-only title gate (Khmer titles, `[Intro music]` auto-fill). Retries refunded, so admin **Burned** looked like >50 while net daily usage stayed at the cap.

Web Music now:

1. Validates title + **admin Suno blocklist** **before** charging.
2. Rejects lyrics/title/style/negative tags that still contain blocklist wording (does not silently submit replacements as the only gate).
3. Sanitizes as a last-mile strip so blocked tokens cannot reach Suno.
4. Uses a Unicode-safe title (Khmer allowed; section brackets stripped).
5. Still refunds 10 credits if Suno later callbacks `FAILED`/`REJECTED` (already on this branch).

## Product impact

- Create 422 for blocked wording happens **before** the daily 50 is touched.
- Khmer (and other non-Latin) titles are accepted.
- Auto-title from `[Intro music]` becomes `Intro music` instead of “Suno requires a valid song title.”
- If Suno still rejects after accept, the user gets the 10 credits back.

## Technical impact

- New `web_music_suno_guard` shared by `WebMusicService.generate` and `GenerationService.submit_suno` (`source=web_music`).
- Studio `submit_suno` still auto-replaces block terms (desktop behavior unchanged).

## Files touched

- `platform_api/services/web_music_suno_guard.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/generation_service.py`
- `platform_api/tests/test_web_music_suno_guard.py`
- `platform_api/tests/test_generation_service.py`
- `platform_api/CHANGELOG.md`

## Migration/deploy

No migration. Sync `platform_api` to sandbox and restart API.

## Tests

- `pytest platform_api/tests/test_web_music_suno_guard.py platform_api/tests/test_generation_service.py -k "web_music or suno_guard or SubmitSuno"`

## Follow-ups

- Production deploy only on request.
- Optional: surface blocked terms in the Create UI from `details.blocked_terms`.
