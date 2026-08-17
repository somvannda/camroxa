# Music web: fix Create AI assist 422/502

**Date:** 2026-08-17  
**Branch:** `fix/music-web-generate-assist`

## Summary

Create-page lyric and style wands were failing in the browser as 422 and 502.

- **422** — `POST /web-music/generate-styles` rejected lyrics over 500 characters while the Create form allows 5000. Empty wand clicks also hit the API.
- **502** — LLM/provider failures from `generate-draft` and `generate-styles` surfaced as raw Bad Gateway. Credits were already refunded; the user-facing message was not.
- Production nginx for `music.camxora.com` was missing the `/api/` proxy that sandbox already has, so API calls could be sent to Next.js instead of `platform_api`.

The CSS preload warning for `/_next/static/chunks/*.css` is a Next.js/Chrome false positive (stylesheet is used after hydration). It is not a functional Create-page bug.

## Changes

- Accept full Create-form lyrics/description on `generate-styles` (5000 chars). The LLM prompt still uses a 400-character lyrics excerpt.
- Map lyric/style LLM failures to a retryable 502 with a clear “try again” message after refund.
- Create page validates style-wand input locally and sends a lyrics excerpt.
- Production nginx template now proxies `music.camxora.com/api/` to `platform_api` with 300s timeouts (same as sandbox). Not applied to production in this change.

## Surfaces

- `platform_api` — `WebMusicStyleRequest`, `generate_draft`, `generate_styles`
- `music_web` — Create page style wand, `web-music-api.ts`
- `scripts/deploy/nginx-camxora-production.conf` — repo template only
