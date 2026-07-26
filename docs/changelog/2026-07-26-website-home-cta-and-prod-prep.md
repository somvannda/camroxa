# Website home CTA polish + production cutover prep

**Date:** 2026-07-26  
**Status:** implemented (sandbox website deploy)

## Summary

Kept the marketing homepage (do not replace with `/compare`). Tightened home hero CTAs so Create account and Download stay primary, with Why Camxora / pricing as secondary text links. Bundled production cutover docs, desktop 1.0.0 stamp (production API), export hang diagnostics (0.4.2/0.4.3), and B2 two-key migration scripts for the next production pull.

## Product impact

- **Before:** Home hero showed four equal-weight buttons (Create account, Download, Why Camxora, View pricing).
- **After:** Primary CTAs are Create account + Download; Compare and pricing are secondary text links. `/compare` remains available as a conversion page.

## Technical impact

- Website: `website/src/app/page.tsx` hero CTA layout only.
- Desktop: version stamps at 1.0.0 targeting production API; export diagnostics and analyzing-audio mitigations remain in tree (GPU follow-up held).
- Docs: `docs/PRODUCTION_CUTOVER.md`, GPU follow-ups, sandbox/deployment guide updates.
- Scripts: B2 sandbox→prod two-key copy helpers (no credentials committed).

## Files touched

- `website/src/app/page.tsx`, `website/CHANGELOG.md`
- `docs/PRODUCTION_CUTOVER.md`, `docs/FOLLOWUPS_DESKTOP_GPU_EXPORT.md`
- `docs/DEPLOYMENT_OPERATIONS.md`, `docs/SANDBOX_DEPLOYMENT_GUIDE.md`
- `docs/changelog/2026-07-25-*.md`, `docs/changelog/2026-07-26-website-home-cta-and-prod-prep.md`
- `camxora_python/` version + export/audio analysis changes
- `scripts/deploy/migrate_b2_song_storage_two_key.py`, `scripts/deploy/fetch_sandbox_b2_creds.py`
- `CHANGELOG.md`, `.deploy/secrets.env.example`

## Migration / deploy

1. Push branch; pull on production when ready.
2. Sandbox: `python scripts/deploy/deploy_website_portal_sandbox.py`
3. Production VPS deploy still blocked on filled `PRODUCTION_VPS_*` in `.deploy/secrets.env`.

## Tests

- Website: manual CTA layout review (no automated suite).
- Desktop export fixes: existing unit tests updated (`test_app_version`, `test_export_gpu_tier`, `test_export_failure_log`, `test_audio_analyzer_progress`).

## Follow-ups

- Production cutover: DB import (local plans + scrubbed sandbox config + streaming catalog with placeholder owner); point Admin Streaming at `productions-camxora-song`.
- Build `CamxoraSetup-1.0.0.exe`.
- Validate 0.4.3 analyzing-audio fix on GTX 1050 Ti (held).
- Rotate B2 application keys used for media copy.
