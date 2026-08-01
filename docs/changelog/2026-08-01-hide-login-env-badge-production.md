# Login screen leaked a "Production API" badge in production installers

**Date:** 2026-08-01
**Status:** implemented (fix built into desktop v1.0.13, pending user install)

## Summary

The main app shell (`app/application.py`) already correctly hid the API
environment badge for production builds via
`build_config.should_show_api_environment_badge()`. The **login screen**
(`AuthView`), however, had its own fallback that unconditionally computed
and displayed a label — including the literal text **"Production API"** —
whenever `footer_environment_badge()` returned nothing, which is exactly
the case in production. So every end user running a production installer
saw a "Production API" badge on the login screen, even though it was
correctly hidden everywhere else in the app.

## Product impact

**Before:** Opening a production installer showed a "Production API" badge
(with a tooltip revealing the live API hostname) on the login screen, before
the user even signed in — an internal implementation detail leaking to
end users, and inconsistent with the rest of the app which never shows it.

**After:** Production installers never show any environment badge on the
login screen (or anywhere else). Sandbox/dev/local builds are unaffected —
internal testers still see "Sandbox API" / "Dev API" / "Local API" labels
there, same as before.

## Technical impact

`AuthView._refresh_login_footer_badges()` now short-circuits to hide the
footer's environment badge outright when `build_environment() == "production"`,
before ever computing a fallback label. The sandbox/dev/local code path
(computing `Sandbox API` / `Local API` / `Dev API` labels when
`footer_environment_badge()` returns nothing) is unchanged. No change was
needed in `shared/services/build_config.py` — `should_show_api_environment_badge()`
/ `footer_environment_badge()` were already correct; the bug was only in
`AuthView`'s intentional-but-too-broad override of that behavior.

## Files touched

- `camxora_python/features/account/views/auth_view.py` —
  `_refresh_login_footer_badges()` now hides the badge unconditionally for
  production builds instead of falling back to a synthesized "Production API"
  label.
- `camxora_python/tests/test_auth_view_env_badge.py` — new tests:
  `test_login_footer_badge_hidden_for_production_build` and
  `test_login_footer_badge_still_shown_for_non_production_builds`.
- `camxora_python/pyproject.toml`, `camxora_python/resources/app-version.txt`,
  `camxora_python/tests/test_app_version.py` — version bump to 1.0.13.
- `CHANGELOG.md` (root, desktop) — `[1.0.13]` entry.

## Migration / deploy

Desktop-only UI fix; no platform_api or database changes. Ships in the
v1.0.13 production installer. No sandbox/production backend deploy needed.

## Tests

- `pytest camxora_python/tests/test_auth_view_env_badge.py -v` — 3 passed (new).
- `pytest camxora_python/tests/test_build_config.py -v` — unaffected;
  `should_show_api_environment_badge()` / `footer_environment_badge()` were
  already correct and untouched.

## Follow-ups

- None — `AuthView` was the only place with a login-specific override of the
  shared badge-hiding logic; the main app shell already delegated directly to
  `build_config.footer_environment_badge()`.
