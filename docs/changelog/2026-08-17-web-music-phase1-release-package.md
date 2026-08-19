# Web Music Phase 1 — complete release package

**Date:** 2026-08-17  
**Surfaces:** `platform_api`, `music_web`, `admin_portal`  
**Branch:** `feature/web-music-credits-hardening`

## Summary

Commits the remaining Phase 1 web music work that was sandbox-only on disk: migrations 085–100, CutLuy/Turnstile shared services, subscription/pricing UI, playlists, workspaces, and admin plan management.

## Production Turnstile note

Reuse existing production `CLOUDFLARE_TURNSTILE_SITE_KEY` / `SECRET_KEY` in `platform_api/.env`. Add `music.camxora.com` to `CLOUDFLARE_TURNSTILE_HOSTNAMES` and pass the site key into `music_web` build as `NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY` (see `scripts/deploy/add_turnstile_hostnames_production.py`).

CutLuy, B2 streaming keys, TLS, and Suno callbacks reuse existing production configuration.
