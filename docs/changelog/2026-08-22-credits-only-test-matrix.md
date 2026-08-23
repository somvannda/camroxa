# Credits-Only Test Matrix Documentation — Expanded Coverage

**Date:** 2026-08-22  
**Type:** Documentation  
**Surfaces:** All (test plan)

## Summary

Expanded comprehensive test plan for Camxora credits-only plan unification (v3) at `docs/credits-only-test-matrix.md` with additional test cases and scenarios to ensure end-to-end verification of credits-only behavior.

## Product Impact

Test matrix now covers all surfaces (platform_api, admin_portal, music_web, website, user_portal, desktop) with expanded coverage for critical gaps:
- Public plan visibility filtering (is_active AND is_public) + race condition tests
- Hidden $79 plan handling (3000 credits, never on public lists)
- Credits-only v3 API endpoints
- Free plan daily grant logic (from plan row, not system setting)
- Conversion from legacy song packages (expired license mint 0, confirm gate)
- Dual-channel profile pack (slots only, NO scale of song/draft/image/video/merge meters)
- Desktop app credits UI (Electron + Python main.py)
- Yearly vs monthly plans (same credit grant, cash discount only)
- Lyrics-only generation cost display and debit
- Admin portal wallet UI (no quota top-up)
- Portal onboarding after email confirm (no $79)
- Flag ON behavior (10 credits = 2 versions; 402 if wallet 0)
- Admin generate button copy (flag Off vs On)
- Production admin segregation (sandbox verdicts only)
- Duke Windows sign-in procedures

No code changes — documentation only.

## Technical Impact

- 200+ test cases across 13 categories (added Category J for yearly/monthly plans)
- Added Duke Windows sign-in note (Chrome default profile, correct sandbox URLs)
- Expanded coverage for:
  - Music web Free card daily_credits display (TC-L03)
  - Lyrics-only Create cost preview (TC-L04)
  - Admin user wallet + grant remaining (TC-B04)
  - Portal onboarding/upgrade hidden plan filtering (TC-A06)
  - Desktop credits vs plan quota (Electron TC-G04, Python TC-G05)
  - Flag ON explicit tests (TC-C03b)
  - Addon comprehensive wallet + meter verification (TC-H10)
  - Hidden $79 grant amount + public list exclusion (TC-I03)
  - Free daily grant source verification (TC-D03)
  - Yearly plan parity tests (TC-J01 through TC-J04)
  - Conversion expired license + confirm gate (TC-F04b)
  - Race condition for public list filtering (TC-A07)
  - Admin flag copy differences (TC-B06)
  - Sandbox-only testing requirement (TC-B07)
- Preconditions, steps, expected results, and failure meanings for each test
- "How to run each surface" guide for local and sandbox testing
- Risk assessment and test execution priority
- Product lock requirements documented

## Files Touched

- `docs/credits-only-test-matrix.md` (expanded)
- `docs/changelog/2026-08-22-credits-only-test-matrix.md` (this file, updated)

## Migration/Deploy

None. Documentation only.

## Tests

N/A — this is the test plan itself.

## Follow-Ups

- Execute expanded test cases before credits-only v3 production deploy
- Update test plan as implementation details finalized
- Automate critical API test cases (Categories C, D, F) with pytest
- Verify all Duke Windows sign-in procedures documented are current
