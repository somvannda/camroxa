# 2026-08-23 — Desktop paid gate + website pricing match

Sandbox only. Production not touched.

## Desktop studio is paid-only

Free ($0) accounts can still use Web Create. They cannot sign into the desktop studio.

- Desktop login/refresh sends `X-Camxora-Client: desktop`.
- API returns `403 DESKTOP_PLAN_REQUIRED` unless the user has an active paid license or paid web subscription (`price_cents > 0`). Hidden $79 and Starter / Creator / Studio all qualify.
- `POST /generation/draft` and `POST /generation/suno` also require paid access, so an old desktop build cannot generate on a Free account.

## Website pricing matches music web

`sandbox.camxora.com/pricing` now uses the same purple/pink cards, monthly/yearly toggle, credit numbers, song hint (`floor(credits / 10)`), bullets, and CutLuy footer copy as `music.sandbox.camxora.com/pricing`. Checkout still happens on music web.

Free cards no longer advertise Desktop studio. Paid cards keep Web Create, Desktop studio, Dual channels, Top-up packs.
