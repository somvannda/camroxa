# DistroKid add-on scaffold ($5/mo) + Music checkbox rename

**Date:** 2026-07-27  
**Status:** implemented (Phase 4 WAV conversion + upload history; DistroKid partner API upload pending)

## Summary

Framed WAV conversion under a **DistroKid** monthly add-on ($5) instead of a standalone WAV SKU. Scaffold includes license entitlement, CutLuy checkout, portal purchase panel, desktop DistroKid sidebar page, Music DistroKid checkbox (gated), and dropped the “Auto” prefix on Music automation labels (Reel → Short).

## Product impact

- Before: no DistroKid product; Music checkboxes labeled Auto-*.
- After:
  - Users can buy **DistroKid ($5/mo)** on portal Billing (requires active subscription).
  - Desktop shows **DistroKid** sidebar + Music **DistroKid** checkbox (enabled only when add-on active).
  - Music toggles: Gen Image, GSuno, Video, Merge, Short, Upload, DistroKid.
  - Add-on includes **600 WAV/mo** entitlement (Primary + Secondary full burn); DistroKid upload integration TBD when API project is shared.

## Technical impact

- `licenses.distrokid_enabled` + `distrokid_expires_at`
- Billing `product_type=distrokid_addon`; fulfill enables license flag for 30 days (capped by subscription end)
- Exposed on `/users/me`, `/licenses/validate`, `/billing/distrokid/status`
- Seed `suno` / `wav` credit pricing (list 1 cr, COGS $0.002)

## Files touched

- `platform_api/migrations/versions/075_distrokid_addon.py`
- `platform_api/services/distrokid_entitlement_service.py`
- `platform_api/models/domain.py`, `repositories/license_repo.py`
- `platform_api/routers/billing.py`, `licenses.py`, `users.py`
- `platform_api/tests/test_distrokid_entitlement.py`
- `camxora_python/shared/constants/navigation.py`, icons, models
- `camxora_python/features/music/widgets/automation_card.py`, `music_settings.py`, `music_view.py`
- `camxora_python/features/distrokid/views/distrokid_view.py`, `app/router.py`
- `user_portal/src/components/dashboard/distrokid-panel.tsx`, billing page + lib

## Migration / deploy

```bash
# platform_api
alembic upgrade head   # 075_distrokid_addon
# restart camxora-api; rebuild user_portal + desktop as needed
```

## Tests

- `pytest platform_api/tests/test_distrokid_entitlement.py`

## Follow-ups

- Wire the DistroKid partner API (user will share integration project); history only records successful client-side uploads for now.
- Confirm sunoapi.org WAV credit = 0.4–0.5 on live billing.
- Optional Electron shell nav parity.

## Phase 4 — WAV conversion and upload history

### Summary
Added the authenticated platform API path from a completed Suno clip to a provider WAV conversion request. The service checks the DistroKid add-on, atomically reserves one of 600 UTC-calendar-month conversions, charges the existing `suno/wav` price, and refunds both the credit charge and meter reservation when submission fails.

### Product impact
- Before: the DistroKid add-on advertised WAV capacity but did not expose a conversion API or upload duplicate protection.
- After: entitled users can start and poll WAV jobs, view monthly usage, check an album’s tracks against prior WAV fingerprints, and persist successful DistroKid upload history.

### Technical impact
- Migration `076_distrokid_wav` adds WAV job, monthly usage, and upload-history tables with ownership/fingerprint indexes.
- `SunoClient` supports `/api/v1/wav/generate` and `/api/v1/wav/record-info`; public Suno WAV callbacks are accepted and logged while job reads reconcile provider state.
- `/api/v1/distrokid/*` uses JWT auth, entitlement checks, existing `CreditService.execute_with_credits`, and the Suno key-pool wrapper.

### Files touched
- API: `platform_api/clients/suno_client.py`, `services/distrokid_service.py`, `routers/distrokid.py`, `routers/callbacks.py`, `dependencies.py`, `wire_dependencies.py`, `main.py`
- DB/tests: `platform_api/migrations/versions/076_distrokid_wav.py`, `platform_api/tests/test_distrokid_wav.py`
- Changelogs: this file and `platform_api/CHANGELOG.md`

### Migration / deploy
- Run `alembic upgrade head` locally, then deploy the affected Platform API to sandbox and smoke test authenticated routes.
- No production action is included.

### Tests
- `pytest platform_api/tests/test_distrokid_wav.py`

### Follow-ups
- Wire the future partner-upload action to call `POST /distrokid/history` only after DistroKid confirms a successful upload.
