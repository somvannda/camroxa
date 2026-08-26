# Restore desktop Choose Your Plan popup after v3 (2026-08-25)

Desktop login used to open a native **Choose Your Plan** dialog when the account
was Free (not Starter / Creator / Studio). After the v3 desktop paid gate
landed, login returned `403 DESKTOP_PLAN_REQUIRED` and the client only showed
an error label — the popup disappeared.

## Product impact

- Sign in without Starter, Creator, or Studio → stay on login and open the
  native plans dialog (catalog from `/api/v3/subscriptions/plans`, fallback
  `/api/v3/plans/public`).
- Starter / Creator / Studio, paid `$79` license (`onboarding_paid`), or admin
  → enter the studio as before.
- Closing the dialog does not log the user in. CTAs open Music `/pricing` and
  the account portal onboarding page.

## Technical impact

- Restore `UpgradePlansDialog` and `user_can_use_desktop_studio`.
- `AuthWorker` maps v3 `403 DESKTOP_PLAN_REQUIRED` to a LOGIN bootstrap result
  so `_show_login` can open the dialog even when tokens were never issued.
- `run_bootstrap` also blocks unpaid sessions that somehow received tokens
  (local API without the header gate).

## Files touched

- `camxora_python/features/account/views/upgrade_plans_dialog.py`
- `camxora_python/features/account/views/auth_view.py`
- `camxora_python/app/root_window.py`
- `camxora_python/shared/lib/desktop_entitlement.py`
- `camxora_python/shared/services/session_service.py`
- `camxora_python/shared/services/platform_api.py`
- `camxora_python/shared/services/platform_client.py`
- `camxora_python/shared/services/build_config.py`
- `camxora_python/shared/workers/bootstrap_worker.py`
- `camxora_python/tests/test_desktop_entitlement.py`
- `camxora_python/tests/test_upgrade_plans_dialog.py`
- `camxora_python/tests/test_login_api.py`
- `camxora_python/tests/test_build_config.py`

## Migration / deploy

Desktop client only. No API or sandbox web rebuild. Production not touched.

## Tests

- Entitlement: Free blocked; Starter/Creator/Studio, `onboarding_paid`, admin allowed.
- Login: Free `get_me` → LOGIN + popup message; v3 403 on `get_me` → same.
- Catalog: `/subscriptions/plans` preferred; public catalog fallback skips Free.

## Follow-ups

Ship a desktop installer after this is on the v3 branch so sandbox testers
see the popup without a local build.
