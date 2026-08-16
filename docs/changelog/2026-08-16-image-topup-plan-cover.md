# Admin image (quota) top-up ignored by plan coverage

**Date:** 2026-08-16  
**Status:** implemented  
**Branch:** `bugfix/image-allowance-topup-cover`

## Summary

Admin period quota top-ups raised the monthly meter in enforcement and in the
admin snapshot, but `subscription_covers_operation` / `subscription_covers_batch`
still used the base plan cap. After the included image allowance was used,
generation treated the extra units as wallet overage.

## Product impact

`sophay@camxora.com` had an image top-up of **+10** (effective 130) with **120**
used and **0** wallet. Admin showed remaining images; retries failed with
`Insufficient credits for this operation.` After this fix, remaining top-up
units bill as plan allowance.

The same hole applied to song/draft/video/merge top-ups.

## Technical impact

- `subscription_covers_operation` accepts `topup_extra`
- `subscription_covers_batch` accepts `topup_extras` (`quota_kind` → extra)
- Usage enforcement and batch preflight pass current-period extras from
  `QuotaTopupService`

Daily per-channel image caps are unchanged. Top-up is monthly only.

## Files touched

- `platform_api/services/billing_mode_service.py`
- `platform_api/services/usage_enforcement_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/services/quota_topup_service.py`
- `platform_api/tests/test_billing_mode_service.py`
- `platform_api/tests/test_quota_topup_service.py`
- `platform_api/CHANGELOG.md`

## Migration/deploy

No migration. Restart `camxora-api` and **image workers** so in-flight retries
pick up the coverage check.

Production still needs an explicit hotfix/deploy.

## Tests

- `test_subscription_covers_operation_includes_image_topup`
- `test_subscription_covers_batch_includes_image_topup`
- Existing after-reservation and add-on scaling tests unchanged

## Follow-ups

- Production API + image-worker restart so sophay can retry failed jobs
- If those 10 extra images are not enough for the stuck batch, top up again
