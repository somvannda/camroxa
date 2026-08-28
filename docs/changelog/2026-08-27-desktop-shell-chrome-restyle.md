# 2026-08-27 — Desktop shell chrome restyle

Local desktop only. Sandbox and production were not deployed.

## Summary

The live `camxora_python` header, left sidebar, and footer now match the Create screenshot chrome: navy surfaces, purple selected nav, circular initials avatar, 40px Inter footer with vertical dividers.

Live notifications, software-update, credits, profiles, and logout stay wired. Help opens the user-portal Guides page.

## Product impact

- Header is 52px with a Help control next to min/max/close
- Sidebar is a 192px floating rounded card (avatar, solid purple selected item)
- Logout uses a purple outline instead of the old rose treatment
- Footer is 40px and spans the **full window width** under sidebar and workspace
- Footer type is Inter 12px; env/version badges are 22px pills (not full footer height)
- Footer uses `│` separators between status, env, version, credits, and profiles

## Technical impact

- Sidebar account card is now `#shell_account_card` so global `#account_card` panels on Music / Video / Settings are unchanged
- Shell QSS lives in `deep_blue.py` under `#window_title_bar`, `#shell_sidebar`, and `#shell_footer_bar`

## Files touched

- `camxora_python/shared/widgets/window_title_bar.py`
- `camxora_python/shared/widgets/sidebar_nav.py`
- `camxora_python/shared/widgets/shell_footer_bar.py`
- `camxora_python/shared/themes/deep_blue.py`
- `camxora_python/shared/icons/lucide_icons.py`
- `camxora_python/tests/test_shell_chrome.py`
