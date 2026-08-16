# Desktop dashboard: used/quota meters + scaled add-on caps

**Date:** 2026-08-16  
**Surfaces:** `camxora_python`  
**Branch:** `feature/desktop-dashboard-used-quota`

## Summary

Dashboard **Usage This Month** and Profile **Membership** now show
**used / allowance** (for example `200 / 300`) instead of remaining
(`0 / 300` or `467 remaining` when the cap is exhausted or scaled).

Suno and image caps prefer `/quota-status`, which already scales for profile
add-on channels. A 2-channel plan with 8 add-on slots (10 channels) now reads
against **1,500** Suno packages and **600** images, not the unscaled 2-channel
`300` / `120`. The footer profile count uses effective allowance (`10 / 10`)
instead of the base plan (`10 / 2`).

## Why

- Remaining `0 / 300` looked like the meter was not counting.
- `/licenses/validate` still returns the base-plan song/image limit; the
  dashboard was using that as the denominator.

## Tests

- `pytest camxora_python/tests/test_dashboard_view.py camxora_python/tests/test_profile_view.py -q`
