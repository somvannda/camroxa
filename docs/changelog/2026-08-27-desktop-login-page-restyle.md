# 2026-08-27 — Desktop login page restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` login screen now matches the studio login card: waveform backdrop, 570px navy card, icon fields, Remember me, Forgot password, and recent-account rows. Social login buttons are not included.

Real sign-in, register (when enabled), saved-account switch, upgrade popup, and the shared title bar / footer stay wired.

## Product impact

- Login card is centered over `resources/background_login.png` (bundled in the desktop build)
- Login type uses bundled Inter at the same pixel sizes as the title-bar lockup (15 / 9) and the screenshot scale for the rest of the card
- Email / password fields have mail, lock, and show-password controls
- Remember me stores the last email on this machine
- Forgot password opens the user portal login page
- Recent accounts use avatar cards; click restores the saved session, X removes it

## Files touched

- `camxora_python/features/account/views/auth_view.py`
- `camxora_python/features/account/auth_styles.py`
- `camxora_python/resources/background_login.png`
- `camxora_python/Camxora.spec`
- `camxora_python/features/account/widgets/`
- `camxora_python/shared/icons/lucide_icons.py`
- `camxora_python/tests/test_auth_login_ui.py`
