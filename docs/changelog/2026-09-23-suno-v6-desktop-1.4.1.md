# Suno V6 models + desktop 1.4.1

**Date:** 2026-09-23
**Branch:** `release/1.4.1` (merged into `main`)
**Surfaces:** platform_api, music_web, admin_portal, camxora_python (desktop)
**Status:** implemented; deployed to sandbox + production; desktop 1.4.1 published (mandatory)

## Summary

Adds support for Suno's current **V6 model series** — `V6` (default), `V6_MINI`
(faster) and `V6_WILD` (more experimental) — across the backend, music web,
desktop, and admin. `V5.5` / `V5` remain selectable and are marked
*discontinued* by the provider.

Desktop is bumped to **1.4.1** to re-issue the mandatory update and to ship the
restored `v5.5` / `v5` Settings options. The desktop build **excludes the Create
page** (music creation is web-only).

## Model support

- **Registry / validation:** `V6`, `V6_MINI`, `V6_WILD`, `V5_5`, `V5` accepted by
  the generate and web-music APIs. Default is `V6`. `SUNO_MODEL_PATTERN`,
  `DEFAULT_SUNO_MUSIC_MODEL`, and `resolve_suno_model_id()` live in
  `platform_api/ai/registry.py`.
- **Client:** V6 requests send the dedicated `lyrics` field (takes priority over
  `prompt` in custom mode). `negativeTags` cap raised to 1000 chars for V6.
- **Selectors:** web Create, desktop Create, desktop Settings default version,
  legacy desktop, and Electron settings all list
  `V6 / V6 Mini / V6 Wild / V5.5 / V5` with V6 default.
- **Admin:** Credits pricing dropdown and generated-song labels recognise the V6
  series; `V5` / `V5.5` remain listed as deprecated.

## Pricing

- Migration **`122_suno_v6_pricing`** seeds `V6`, `V6_MINI`, `V6_WILD` at the
  **same price as V5.5**, copying the existing V5.5/V5/provider-wide music price.
  Rows copied from an existing V5.5/V5 price are trusted (`needs_review=false`).

## Deploy / migration

- Backend (API + workers) deployed to sandbox and production; `alembic upgrade
  head` applied `122_suno_v6_pricing` on both.
- `music_web` and `admin_portal` rebuilt on both.
- Desktop `CamxoraSetup-1.4.1.exe` built without the Create page, uploaded, and
  published as a **mandatory** release
  (`https://api.camxora.com/api/v3/public/desktop-release`).
- The full one-shot deploy still fails on the pre-existing website `/blog` build
  error; targeted `sync_*_production.py` scripts were used instead.

## Follow-ups

- Fix the website `/blog` build so `deploy_production.py` completes end-to-end.
- Keep `platform_api/data/music_genre_catalog.py` on `main` (restored here; its
  absence broke every alembic run).
